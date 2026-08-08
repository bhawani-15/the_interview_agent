class InterviewSessionManager:
    def __init__(self):
        self.sessions = {}

    def create_session(self, session_id: str, candidate: dict):
        session = {
            "sessionId": session_id,
            "candidate": candidate,
            "question_count": 0,
            "questions": [],
            "answers": [],
            "covered_days": [],
        }

        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)


session_manager = InterviewSessionManager()