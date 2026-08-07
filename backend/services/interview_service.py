from schemas.interview import InterviewResponse


def interview_reply() -> InterviewResponse:
    return InterviewResponse(
        reply="Interview endpoint working",
        done=False,
    )