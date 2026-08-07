from fastapi import APIRouter

from schemas.interview import InterviewResponse
from services.interview_service import interview_reply

router = APIRouter(
    prefix="/api",
    tags=["Interview"]
)


@router.post("/interview", response_model=InterviewResponse)
def interview():
    return interview_reply()