from fastapi import FastAPI

from backend.app.api.interview import router as interview_router

app = FastAPI(
    title="AI Interview Agent",
    version="1.0.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(interview_router)