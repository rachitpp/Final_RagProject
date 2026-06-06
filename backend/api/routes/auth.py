"""Authentication routes: first-time activation and login.

The roster (employee_id, email, band) is imported from the Excel sheet by
import_employees.py. Activation lets an employee claim their row by proving
identity (employee_id + the email already on file) and setting a password.
Login then exchanges id + password for a JWT whose only claim is `sub`
(the employee_id). Band/role are NEVER in the token — they're looked up
server-side per request (see api/deps.py, Step 7).
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from api.ratelimit import client_ip, login_limiter
from api.schemas import (
    ActivateRequest,
    LoginRequest,
    ProfileResponse,
    TokenResponse,
    UserProfile,
)
from api.security import (
    create_access_token,
    dummy_verify,
    hash_password,
    verify_password,
)
from db.models import User
from db.session import get_db

# Audit log. Uses standard logging (root configured at INFO in api/main.py) so
# these events surface alongside the server log. Never logs passwords.
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/activate", response_model=TokenResponse)
def activate(
    body: ActivateRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    """Set the password for a roster employee, after verifying their email.

    Returns a token so the user is logged in immediately on success.
    """
    employee_id = body.employee_id.strip()
    ip = client_ip(request)
    login_limiter.check(f"activate:{ip}:{employee_id.lower()}")
    user = db.get(User, employee_id)

    # Generic 400 whether the id is unknown OR the email doesn't match, so this
    # endpoint can't be used to enumerate which employee_ids/emails are valid.
    if user is None or user.email.strip().lower() != body.email.strip().lower():
        logger.warning("activation failed (id/email mismatch): id=%r ip=%s", employee_id, ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee ID and email do not match our records.",
        )

    if user.is_activated:
        logger.info("activation rejected (already active): id=%s ip=%s", employee_id, ip)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already activated. Please log in.",
        )

    user.password_hash = hash_password(body.password)
    user.activated_at = datetime.now(tz=timezone.utc)
    db.commit()

    logger.info("activation succeeded: id=%s ip=%s", employee_id, ip)
    return TokenResponse(access_token=create_access_token(user.employee_id))


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    """Exchange employee_id + password for a JWT."""
    employee_id = body.employee_id.strip()
    ip = client_ip(request)
    login_limiter.check(f"login:{ip}:{employee_id.lower()}")
    user = db.get(User, employee_id)

    # One generic 401 for "no such user", "not activated", and "wrong password"
    # alike — don't leak which employee_ids exist or which are activated. Run a
    # bcrypt verification on EVERY path (dummy_verify when there is no real hash)
    # so timing is identical whether or not the account exists.
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid employee ID or password.",
    )
    if user is None or not user.is_activated:
        dummy_verify(body.password)
        logger.warning("login failed (no/inactive account): id=%r ip=%s", employee_id, ip)
        raise invalid
    if not verify_password(body.password, user.password_hash):
        logger.warning("login failed (bad password): id=%s ip=%s", employee_id, ip)
        raise invalid

    logger.info("login succeeded: id=%s ip=%s", employee_id, ip)
    return TokenResponse(access_token=create_access_token(user.employee_id))


@router.get("/me", response_model=ProfileResponse)
def me(user: UserProfile = Depends(get_current_user)) -> ProfileResponse:
    """Return the signed-in user's own profile (for the UI to display)."""
    return ProfileResponse(
        employee_id=user.employee_id, name=user.name, band=user.band, role=user.role
    )
