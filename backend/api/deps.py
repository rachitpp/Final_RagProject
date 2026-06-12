"""Shared FastAPI dependencies."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.schemas import UserProfile
from api.security import InvalidToken, decode_token
from conversation.store import ConversationStore
from db.models import User
from db.session import SessionLocal
from pipelines.rag_pipeline import RAGPipeline

# auto_error=False so a *missing* Authorization header yields our own 401
# (consistent with bad/expired tokens) rather than HTTPBearer's default 403.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_pipeline(request: Request) -> RAGPipeline:
    """Return the single RAGPipeline built once at startup (see api/main.py lifespan)."""
    return request.app.state.pipeline


def get_sessions(request: Request) -> ConversationStore:
    """Return the process-wide per-conversation memory store."""
    return request.app.state.sessions


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserProfile:
    """Resolve the caller from the Bearer JWT.

    Decodes the token to an employee_id, then reads band/name/role from the DB —
    the band is always server-authoritative, never trusted from the token.
    Raises 401 on a missing/invalid/expired token or an unknown employee_id.

    Uses its own short-lived session (not the request-scoped get_db) and returns
    a detached UserProfile: the single lookup is done and the connection released
    immediately, instead of being pinned for the whole response — which on the
    streaming /chat endpoint would mean the entire stream's duration.
    """
    if creds is None:
        raise _UNAUTHORIZED
    try:
        employee_id = decode_token(creds.credentials)
    except InvalidToken:
        raise _UNAUTHORIZED

    with SessionLocal() as db:
        user = db.get(User, employee_id)
        if user is None:  # token valid but the roster row is gone
            raise _UNAUTHORIZED
        return UserProfile(
            employee_id=user.employee_id,
            name=user.name,
            band=user.band,
            role=user.role,
            date_of_joining=user.date_of_joining,
            leave_taken=user.leave_taken,
        )
