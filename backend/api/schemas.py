"""Request/response models for the API."""
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class UserProfile:
    """The authenticated caller, resolved server-side from the JWT's `sub`.

    Not a request/response model — an internal value object handed to the
    pipeline so answers can be scoped to this user's band and leave record.
    Everything here is read from the DB per request, never from the token
    (see api/deps.get_current_user).
    """
    employee_id: str
    name: str
    band: int
    role: str = "employee"
    # Leave personalization (None when unknown): joining date drives accrual;
    # leave_taken is days already deducted per policy type name (e.g. "CL").
    date_of_joining: date | None = None
    leave_taken: dict[str, float] | None = None


class ActivateRequest(BaseModel):
    """First-time activation: prove identity (id + roster email), set a password."""
    employee_id: str = Field(..., min_length=1, description="e.g. E101")
    email: str = Field(..., min_length=3, description="Must match the roster email for this employee.")
    password: str = Field(..., min_length=8, description="New password (>= 8 chars).")


class LoginRequest(BaseModel):
    employee_id: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    """The authenticated user's own profile, served by GET /auth/me so the
    frontend can show who's signed in. Band is the user's own (not a secret
    from them) — they just can't spoof it or see anyone else's."""
    employee_id: str
    name: str
    band: int
    role: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question.")
    conversation_id: str = Field(
        ..., min_length=1, description="Client-generated id scoping this chat's memory."
    )


class ResetRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
