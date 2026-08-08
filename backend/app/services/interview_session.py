class InterviewSessionManager:

    def __init__(self):
        self.sessions = {}

    def create_session(
        self,
        session_id,
        candidate
    ):
        session = {
            "sessionId": session_id,
            "candidate": candidate,

            "question_count": 0,

            "questions": [],
            "answers": [],

            "covered_days": [],

            "history": [],
            "evaluations": [],

            "current_question": None,
            "current_question_day": None,

            "follow_up_used": False,

            "feedback": None,
        }

        self.sessions[session_id] = session

        return session

    def get_session(self, session_id):
        return self.sessions.get(session_id)


session_manager = InterviewSessionManager()