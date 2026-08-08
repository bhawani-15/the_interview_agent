import json
import uuid
from pathlib import Path

import requests
import streamlit as st


# =========================================================
# Configuration
# =========================================================

BACKEND_URL = "http://127.0.0.1:8000"
INTERVIEW_URL = f"{BACKEND_URL}/api/interview"

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATES_FILE = BASE_DIR / "backend" / "data" / "candidates.json"


# =========================================================
# Page configuration
# =========================================================

st.set_page_config(
    page_title="AI Interview Agent",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# =========================================================
# Styling
# =========================================================

st.markdown(
    """
    <style>
        .stApp {
            background: #f7f8fc;
        }

        .block-container {
            max-width: 900px;
            padding-top: 2.5rem;
            padding-bottom: 3rem;
        }

        .hero {
            padding: 2rem 2.2rem;
            border-radius: 20px;
            background: linear-gradient(135deg, #111827, #273449);
            color: white;
            margin-bottom: 1.5rem;
        }

        .hero h1 {
            margin: 0;
            font-size: 2.35rem;
            letter-spacing: -1px;
        }

        .hero p {
            margin: 0.7rem 0 0;
            color: #dbe3ef;
            font-size: 1.05rem;
        }

        .question-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1.5rem 1.6rem;
            margin: 1rem 0 1.2rem;
            box-shadow: 0 5px 18px rgba(15, 23, 42, 0.05);
        }

        .question-label {
            color: #667085;
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.6rem;
        }

        .question-text {
            color: #111827;
            font-size: 1.28rem;
            line-height: 1.6;
            font-weight: 600;
        }

        .score-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 5px 18px rgba(15, 23, 42, 0.05);
        }

        .score-value {
            font-size: 3rem;
            font-weight: 800;
            color: #111827;
        }

        .score-label {
            color: #667085;
            font-size: 0.9rem;
        }

        .feedback-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1.35rem 1.5rem;
            margin-top: 1rem;
        }

        .feedback-title {
            font-size: 1.05rem;
            font-weight: 750;
            color: #111827;
            margin-bottom: 0.7rem;
        }

        .history-answer {
            color: #667085;
            margin-top: 0.35rem;
            line-height: 1.5;
        }

        .small-muted {
            color: #667085;
            font-size: 0.9rem;
        }

        div[data-testid="stForm"] {
            border: none;
            padding: 0;
        }

        .stButton > button {
            border-radius: 10px;
            font-weight: 650;
            min-height: 2.7rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Data helpers
# =========================================================

@st.cache_data
def load_candidates():
    """Load candidates directly from the existing JSON file."""

    if not CANDIDATES_FILE.exists():
        return []

    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("candidates", data.get("data", []))
    else:
        records = []

    candidates = []

    for record in records:
        if not isinstance(record, dict):
            continue

        member = record.get("member", {})

        if not isinstance(member, dict):
            member = {}

        candidate = dict(member)
        candidate["missions"] = record.get("missions", [])

        candidates.append(candidate)

    return candidates


def candidate_label(candidate):
    name = candidate.get("name", "Candidate")
    candidate_id = candidate.get("id", "")

    role = candidate.get("jobRole", "")
    experience = candidate.get("yearsExperience")

    details = []

    if role:
        details.append(role)

    if experience is not None:
        details.append(
            f"{experience} year"
            + ("s" if experience != 1 else "")
        )

    suffix = " • ".join(details)

    if suffix:
        return f"{name} ({candidate_id}) — {suffix}"

    return f"{name} ({candidate_id})"


def get_eligible_days(candidate):
    """Return completed, non-skipped mission days."""

    days = []

    for mission in candidate.get("missions", []):
        if not isinstance(mission, dict):
            continue

        if (
            mission.get("passed") is True
            and mission.get("skipped") is not True
        ):
            day = mission.get("day")

            if day is not None:
                days.append(day)

    return sorted(
        set(str(day) for day in days),
        key=lambda value: int(value) if value.isdigit() else value,
    )


# =========================================================
# Backend helper
# =========================================================

def call_interview(payload):
    try:
        response = requests.post(
            INTERVIEW_URL,
            json=payload,
            timeout=90,
        )

        if response.status_code != 200:
            try:
                detail = response.json().get(
                    "detail",
                    response.text,
                )
            except ValueError:
                detail = response.text

            return None, (
                f"Backend returned HTTP {response.status_code}: "
                f"{detail}"
            )

        try:
            return response.json(), None
        except ValueError:
            return None, "Backend returned invalid JSON."

    except requests.exceptions.ConnectionError:
        return None, (
            "Could not connect to the FastAPI backend. "
            "Make sure it is running at "
            f"{BACKEND_URL}."
        )

    except requests.exceptions.Timeout:
        return None, (
            "The backend took too long to respond. "
            "Please try again."
        )

    except requests.exceptions.RequestException as error:
        return None, f"Request failed: {error}"


# =========================================================
# Session state
# =========================================================

def reset_interview():
    for key in (
        "screen",
        "session_id",
        "candidate",
        "current_question",
        "question_number",
        "history",
        "feedback",
        "covered_days",
    ):
        st.session_state.pop(key, None)


def initialize_home_state():
    if "screen" not in st.session_state:
        st.session_state.screen = "home"

    if "history" not in st.session_state:
        st.session_state.history = []

    if "question_number" not in st.session_state:
        st.session_state.question_number = 0

    if "covered_days" not in st.session_state:
        st.session_state.covered_days = []


# =========================================================
# Home screen
# =========================================================

def render_home():
    st.markdown(
        """
        <div class="hero">
            <h1>AI Interview Agent</h1>
            <p>
                Practice a personalized technical interview grounded
                in your completed curriculum.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    candidates = load_candidates()

    if not candidates:
        st.error(
            "No candidates could be loaded from "
            "backend/data/candidates.json."
        )
        st.info(
            "Make sure the frontend is being run from the project "
            "root and that the backend/data folder exists."
        )
        return

    st.subheader("Start your interview")

    selected_index = st.selectbox(
        "Select candidate",
        options=range(len(candidates)),
        format_func=lambda index: candidate_label(
            candidates[index]
        ),
    )

    candidate = candidates[selected_index]

    eligible_days = get_eligible_days(candidate)

    st.caption(
        f"{len(eligible_days)} completed curriculum day(s) "
        "available for interview questions."
    )

    st.markdown("")

    if st.button(
        "Start Interview",
        type="primary",
        use_container_width=True,
    ):
        session_id = str(uuid.uuid4())

        payload = {
            "sessionId": session_id,
            "candidate": {
                "id": candidate.get("id"),
            },
        }

        with st.spinner("Preparing your first question..."):
            data, error = call_interview(payload)

        if error:
            st.error(error)
            return

        reply = data.get("reply", "").strip()

        if not reply:
            st.error(
                "The backend did not return an interview question."
            )
            return

        st.session_state.screen = "interview"
        st.session_state.session_id = session_id
        st.session_state.candidate = candidate
        st.session_state.current_question = reply
        st.session_state.question_number = 1
        st.session_state.history = []
        st.session_state.feedback = None

        # The backend requires at least four curriculum days before
        # completion. The backend does not expose the exact covered-day
        # list in its current response contract, so we track the
        # guaranteed minimum on the final dashboard rather than
        # pretending to know the exact sequence.
        st.session_state.covered_days = []

        st.rerun()


# =========================================================
# Interview screen
# =========================================================

def render_interview():
    candidate = st.session_state.candidate

    name = candidate.get("name", "Candidate")

    st.markdown(
        """
        <div class="hero">
            <h1>Technical Interview</h1>
            <p>Take your time and explain your reasoning clearly.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"**Candidate:** {name}"
        )

    with col2:
        st.markdown(
            f"**Question {st.session_state.question_number} of 8+**"
        )

    st.markdown(
        f"""
        <div class="question-card">
            <div class="question-label">
                Question {st.session_state.question_number}
            </div>
            <div class="question-text">
                {st.session_state.current_question}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    answer = st.text_area(
        "Your answer",
        height=180,
        placeholder="Type your answer here...",
        key="answer_input",
    )

    if st.button(
        "Submit Answer",
        type="primary",
        use_container_width=True,
    ):
        if not answer.strip():
            st.warning("Please enter an answer before submitting.")
            return

        # Save visible conversation history before making the request.
        st.session_state.history.append({
            "question": st.session_state.current_question,
            "answer": answer.strip(),
        })

        payload = {
            "sessionId": st.session_state.session_id,
            "message": answer.strip(),
        }

        with st.spinner("Evaluating your answer..."):
            data, error = call_interview(payload)

        if error:
            # Remove the locally-added item so it can be retried.
            st.session_state.history.pop()
            st.error(error)
            return

        if data.get("done") is True:
            st.session_state.feedback = data.get(
                "feedback",
                {},
            )
            st.session_state.screen = "feedback"
            st.rerun()

        next_question = data.get(
            "reply",
            "",
        ).strip()

        if not next_question:
            st.error(
                "The backend did not return the next interview question."
            )
            return

        st.session_state.question_number += 1
        st.session_state.current_question = next_question

        st.rerun()

    # -----------------------------------------------------
    # Conversation history
    # -----------------------------------------------------

    if st.session_state.history:

        st.markdown("---")
        st.subheader("Conversation history")

        for index, item in enumerate(
            reversed(st.session_state.history),
            start=1,
        ):
            with st.expander(
                f"Previous exchange {len(st.session_state.history) - index + 1}",
                expanded=False,
            ):
                st.markdown(
                    f"**Question**  \n"
                    f"{item['question']}"
                )

                st.markdown(
                    f"<div class='history-answer'>"
                    f"<strong>Your answer</strong><br>"
                    f"{item['answer']}"
                    f"</div>",
                    unsafe_allow_html=True,
                )


# =========================================================
# Feedback screen
# =========================================================

def render_feedback():
    feedback = (
        st.session_state.get(
            "feedback"
        )
        or {}
    )

    st.markdown(
        """
        <div class="hero">
            <h1>Interview Complete</h1>
            <p>
                Here's your performance summary.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    overall_score = feedback.get(
        "overall_score",
        0,
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown(
            f"""
            <div class="score-card">
                <div class="score-label">
                    Overall Score
                </div>
                <div class="score-value">
                    {overall_score}/10
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="feedback-card">
                <div class="feedback-title">
                    Interview summary
                </div>
                <div class="small-muted">
                    Your interview included at least 8 questions
                    and covered at least 4 curriculum days before
                    completion.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    strengths = feedback.get(
        "strengths",
        [],
    )

    weaknesses = feedback.get(
        "weaknesses",
        [],
    )

    recommendations = feedback.get(
        "recommendations",
        [],
    )

    st.markdown(
        "<div class='feedback-card'>"
        "<div class='feedback-title'>Strengths</div>",
        unsafe_allow_html=True,
    )

    if strengths:
        for item in strengths:
            st.markdown(f"- {item}")
    else:
        st.markdown(
            "<div class='small-muted'>No strengths provided.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='feedback-card'>"
        "<div class='feedback-title'>Weaknesses</div>",
        unsafe_allow_html=True,
    )

    if weaknesses:
        for item in weaknesses:
            st.markdown(f"- {item}")
    else:
        st.markdown(
            "<div class='small-muted'>No weaknesses provided.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='feedback-card'>"
        "<div class='feedback-title'>Recommendations</div>",
        unsafe_allow_html=True,
    )

    if recommendations:
        for item in recommendations:
            st.markdown(f"- {item}")
    else:
        st.markdown(
            "<div class='small-muted'>No recommendations provided.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------------------------------
    # Curriculum coverage
    # -----------------------------------------------------

    st.markdown(
        "<div class='feedback-card'>"
        "<div class='feedback-title'>Curriculum coverage</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        The interview completion condition guarantees that
        at least **4 different completed curriculum days**
        were covered.
        """,
    )

    st.caption(
        "The current backend response does not expose the exact "
        "covered-day list, so the frontend does not invent one."
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("")

    if st.button(
        "Start New Interview",
        type="primary",
        use_container_width=True,
    ):
        reset_interview()
        st.session_state.screen = "home"
        st.rerun()


# =========================================================
# App
# =========================================================

initialize_home_state()

if st.session_state.screen == "home":
    render_home()

elif st.session_state.screen == "interview":
    render_interview()

elif st.session_state.screen == "feedback":
    render_feedback()
