from typing import Any, Optional

from pydantic import BaseModel


class InterviewRequest(BaseModel):
    sessionId: str
    candidate: Optional[dict] = None
    message: Optional[str] = None


class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Optional[dict[str, Any]] = None