# =============================================================
# Auth primitives shared by the routes and the get_current_user dependency:
#   - password hashing/verification (passlib + bcrypt)
#   - JWT create/decode (PyJWT, HS256)
#
# Framework-agnostic on purpose: these raise plain exceptions; the HTTP layer
# (routes / deps) translates them into status codes.
# =============================================================
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# A throwaway hash used to equalize login timing. Computed once at import so the
# "no such user" path can still run a full bcrypt verification (see dummy_verify)
# and therefore take the same time as a real wrong-password check — closing the
# timing side-channel that would otherwise reveal which accounts exist.
_DUMMY_HASH = pwd_context.hash("timing-equalizer")


class InvalidToken(Exception):
    """Raised when a JWT is missing, malformed, expired, or fails verification."""


# --- Passwords -------------------------------------------------------------

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def dummy_verify(plain: str) -> None:
    """Run a bcrypt verification against a throwaway hash and discard the result.

    Called on the login paths where there is no real hash to check (unknown or
    un-activated employee) so every login spends the same ~bcrypt time, leaving
    no timing oracle for account enumeration."""
    pwd_context.verify(plain, _DUMMY_HASH)


# --- JWT -------------------------------------------------------------------

def _require_secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError(
            "JWT_SECRET is not set. Add it to backend/.env before issuing tokens."
        )
    return settings.jwt_secret


def create_access_token(subject: str) -> str:
    """Mint a signed JWT whose `sub` is the employee_id. Carries no band/role —
    those are looked up server-side per request (see docs/AUTH_PERSONALIZATION_DESIGN.md)."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, _require_secret(), algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """Return the `sub` (employee_id) from a valid token, else raise InvalidToken."""
    try:
        payload = jwt.decode(
            token, _require_secret(), algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as e:
        raise InvalidToken(str(e)) from e
    sub = payload.get("sub")
    if not sub:
        raise InvalidToken("token missing 'sub' claim")
    return sub
