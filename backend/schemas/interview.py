from pydantic import BaseModel


class InterviewResponse(BaseModel):
    reply: str
    done: bool