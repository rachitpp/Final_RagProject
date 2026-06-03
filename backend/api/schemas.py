"""Request/response models for the API."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="The user's question.")
    conversation_id: str = Field(
        ..., min_length=1, description="Client-generated id scoping this chat's memory."
    )


class ResetRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
