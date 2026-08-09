import json
import textwrap
import uuid
from pathlib import Path

import requests
import streamlit as st


# =========================================================
# Configuration
# =========================================================
# Preserve the existing configuration mechanism exactly.
# Swap the comment/active line below to point at the deployed
# Render backend instead of the local FastAPI server.

BACKEND_URL = "https://the-interview-agent.onrender.com"
INTERVIEW_URL = f"{BACKEND_URL}/api/interview"

BASE_DIR = Path(__file__).resolve().parent.parent
CANDIDATES_FILE = BASE_DIR / "backend" / "data" / "candidates.json"

EXPECTED_MIN_QUESTIONS = 8   # Matches the backend's completion guarantee.
EXPECTED_MIN_DAYS = 4        # Matches the backend's curriculum-coverage guarantee.


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
# Small rendering helper
# =========================================================
# Streamlit's Markdown renderer treats 4+ leading spaces on a line as a
# fenced code block. Because HTML snippets below are written as indented
# Python string literals, textwrap.dedent() is used everywhere before
# handing text to st.markdown so the HTML is always interpreted as HTML
# instead of being printed literally on the page.

def html(markup: str) -> None:
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)


# =========================================================
# Styling (single centralized block)
# =========================================================

html("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ================================
   GLOBAL
   ================================ */

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp {
    background: #f5f7fb;
    color: #172033;
}

.block-container {
    max-width: 980px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}

[data-testid="stDecoration"] {
    display: none;
}

#MainMenu, footer {
    visibility: hidden;
}

/* ================================
   HERO
   ================================ */

.hero {
    padding: 2.6rem 2.8rem;
    border-radius: 22px;
    background: linear-gradient(135deg, #0b1220 0%, #111827 50%, #1e293b 100%);
    color: white;
    margin-bottom: 1.8rem;
    box-shadow: 0 16px 40px rgba(11, 18, 32, 0.22);
}

.hero-eyebrow {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #7dd3c0;
    margin-bottom: 0.7rem;
}

.hero h1 {
    margin: 0;
    font-size: 2.5rem;
    font-weight: 800;
    letter-spacing: -1.2px;
    line-height: 1.15;
    color: white;
}

.hero p {
    margin: 0.85rem 0 0;
    color: #b9c2d3;
    font-size: 1.02rem;
    line-height: 1.6;
    max-width: 620px;
}

/* ================================
   SECTION HEADINGS
   ================================ */

.section-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #172033;
    margin: 0.4rem 0 0.35rem;
}

.section-subtitle {
    color: #667085;
    font-size: 0.93rem;
    margin-bottom: 1.1rem;
}

/* ================================
   CARDS
   ================================ */

.card {
    background: white;
    border: 1px solid #e6eaf0;
    border-radius: 16px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.05);
    padding: 1.4rem 1.5rem;
    margin: 0.9rem 0;
}

.card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #172033;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.small-muted {
    color: #667085;
    font-size: 0.92rem;
    line-height: 1.6;
}

/* ================================
   CANDIDATE PROFILE CARD
   ================================ */

.profile-name {
    font-size: 1.2rem;
    font-weight: 700;
    color: #172033;
    margin-bottom: 0.25rem;
}

.profile-meta {
    color: #667085;
    font-size: 0.93rem;
}

.profile-stat {
    margin-top: 1rem;
    padding-top: 0.9rem;
    border-top: 1px solid #edf0f5;
    font-size: 0.93rem;
}

.profile-stat .stat-number {
    font-weight: 700;
    color: #0f766e;
}

/* ================================
   INTERVIEW META ROW
   ================================ */

.meta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.92rem;
    color: #475569;
    margin-bottom: 0.5rem;
}

.meta-row strong {
    color: #172033;
}

/* ================================
   QUESTION CARD
   ================================ */

.question-card {
    background: white;
    border: 1px solid #e6eaf0;
    border-radius: 18px;
    box-shadow: 0 6px 22px rgba(15, 23, 42, 0.06);
    padding: 1.9rem 2rem;
    margin: 0.6rem 0 1.3rem;
}

.question-label {
    color: #0f766e;
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.85rem;
}

.question-text {
    color: #111827;
    font-size: 1.3rem;
    line-height: 1.65;
    font-weight: 620;
}

/* ================================
   RESULTS SHELL (feedback screen)
   One continuous card containing every section, so the score, summary,
   strengths, weaknesses, recommendations, and curriculum coverage read
   as a single results document instead of separate floating cards.
   ================================ */

.results-shell {
    background: white;
    border: 1px solid #e6eaf0;
    border-radius: 20px;
    box-shadow: 0 8px 28px rgba(15, 23, 42, 0.07);
    overflow: hidden;
    margin: 0.4rem 0 1.2rem;
}

.results-top {
    display: flex;
    align-items: center;
    gap: 2rem;
    padding: 2rem 2.1rem;
    background: linear-gradient(135deg, #0b1220 0%, #14213a 100%);
    color: white;
}

.score-block {
    text-align: center;
    flex-shrink: 0;
}

.score-label {
    color: #9fb0c9;
    font-size: 0.82rem;
    font-weight: 600;
    margin-bottom: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.score-value {
    font-size: 3rem;
    line-height: 1.1;
    font-weight: 800;
    color: #5eead4;
}

.score-suffix {
    font-size: 1.2rem;
    font-weight: 600;
    color: #7d8ba3;
}

.summary-block {
    border-left: 1px solid rgba(255, 255, 255, 0.14);
    padding-left: 2rem;
}

.summary-block .section-heading {
    color: white;
}

.summary-block .small-muted {
    color: #b9c2d3;
}

.results-divider {
    height: 1px;
    background: #edf0f5;
    margin: 0;
}

.results-section {
    padding: 1.5rem 2.1rem;
}

.section-heading {
    font-size: 1rem;
    font-weight: 700;
    color: #172033;
    margin-bottom: 0.7rem;
}

.results-section .small-muted {
    margin: 0;
}

.results-section ul,
.results-section ol {
    margin: 0;
    padding-left: 1.2rem;
}

@media (max-width: 700px) {
    .results-top {
        flex-direction: column;
        align-items: flex-start;
        gap: 1.2rem;
        padding: 1.6rem 1.5rem;
    }

    .summary-block {
        border-left: none;
        border-top: 1px solid rgba(255, 255, 255, 0.14);
        padding-left: 0;
        padding-top: 1.2rem;
    }

    .results-section {
        padding: 1.3rem 1.5rem;
    }
}

/* ================================
   HISTORY
   ================================ */

.history-answer {
    background: #f8fafc;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
    margin-top: 0.5rem;
    font-size: 0.92rem;
    color: #334155;
    line-height: 1.55;
}

/* ================================
   INPUT / BUTTONS
   ================================ */

textarea {
    border-radius: 14px !important;
}

.stButton > button {
    min-height: 2.9rem;
    border-radius: 11px;
    font-weight: 700;
    font-size: 0.95rem;
    border: 1px solid #d9dee8;
    transition: all 0.15s ease;
}

.stButton > button:hover {
    border-color: #0f766e;
    transform: translateY(-1px);
}

.stButton > button[kind="primary"] {
    background: #0f766e;
    color: white;
    border: none;
}

.stButton > button[kind="primary"]:hover {
    background: #0c5f58;
    color: white;
}

div[data-baseweb="select"] > div {
    border-radius: 11px;
    border-color: #d9dee8;
    background: white;
}

div[data-testid="stForm"] {
    border: none;
    padding: 0;
    background: transparent;
}

div[data-testid="stAlert"] {
    border-radius: 12px;
}

div[data-testid="stProgressBar"] {
    margin: 0.3rem 0 1.1rem;
}

/* ================================
   MOBILE
   ================================ */

@media (max-width: 700px) {

    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    .hero {
        padding: 2rem 1.5rem;
        border-radius: 18px;
    }

    .hero h1 {
        font-size: 2rem;
    }

    .question-card {
        padding: 1.4rem;
    }

    .question-text {
        font-size: 1.12rem;
    }

    .score-value {
        font-size: 2.4rem;
    }
}

</style>
""")


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
        details.append(f"{experience} year" + ("s" if experience != 1 else ""))

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

        if mission.get("passed") is True and mission.get("skipped") is not True:
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
        response = requests.post(INTERVIEW_URL, json=payload, timeout=90)

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text

            return None, f"Backend returned HTTP {response.status_code}: {detail}"

        try:
            return response.json(), None
        except ValueError:
            return None, "Backend returned invalid JSON."

    except requests.exceptions.ConnectionError:
        return None, (
            "Could not connect to the FastAPI backend. "
            f"Make sure it is running at {BACKEND_URL}."
        )

    except requests.exceptions.Timeout:
        return None, "The backend took too long to respond. Please try again."

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


def initialize_state():
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
    html("""
    <div class="hero">
        <div class="hero-eyebrow">AI-Powered Technical Interview</div>
        <h1>AI Interview Agent</h1>
        <p>
            Practice a realistic technical interview generated from your
            completed curriculum, with instant, structured feedback at the end.
        </p>
    </div>
    """)

    candidates = load_candidates()

    if not candidates:
        st.error("No candidates could be loaded from backend/data/candidates.json.")
        st.info(
            "Make sure the frontend is being run from the project root and "
            "that the backend/data folder exists."
        )
        return

    html("""
    <div class="section-title">Start your interview</div>
    <div class="section-subtitle">
        Select a candidate to begin a personalized technical interview.
    </div>
    """)

    selected_index = st.selectbox(
        "Select candidate",
        options=range(len(candidates)),
        format_func=lambda index: candidate_label(candidates[index]),
        label_visibility="collapsed",
    )

    candidate = candidates[selected_index]
    eligible_days = get_eligible_days(candidate)

    html(f"""
    <div class="card">
        <div class="card-title">Candidate profile</div>
        <div class="profile-name">{candidate.get("name", "Candidate")}</div>
        <div class="profile-meta">
            {candidate.get("jobRole", "Technical Candidate")}
            &nbsp;•&nbsp;
            {candidate.get("yearsExperience", 0)} years experience
        </div>
        <div class="profile-stat">
            <span class="stat-number">✓ {len(eligible_days)}</span>
            <span class="small-muted">completed curriculum day(s) available</span>
        </div>
    </div>
    """)

    st.write("")

    if st.button("Start Interview  →", type="primary", use_container_width=True):
        session_id = str(uuid.uuid4())

        payload = {
            "sessionId": session_id,
            "candidate": {"id": candidate.get("id")},
        }

        with st.spinner("Preparing your first question..."):
            data, error = call_interview(payload)

        if error:
            st.error(error)
            return

        reply = data.get("reply", "").strip()

        if not reply:
            st.error("The backend did not return an interview question.")
            return

        st.session_state.screen = "interview"
        st.session_state.session_id = session_id
        st.session_state.candidate = candidate
        st.session_state.current_question = reply
        st.session_state.question_number = 1
        st.session_state.history = []
        st.session_state.feedback = None
        st.session_state.covered_days = []

        st.rerun()


# =========================================================
# Interview screen
# =========================================================

def render_interview():
    candidate = st.session_state.candidate
    name = candidate.get("name", "Candidate")
    question_number = st.session_state.question_number

    html("""
    <div class="hero">
        <h1>Technical Interview</h1>
        <p>Take your time and explain your reasoning clearly.</p>
    </div>
    """)

    html(f"""
    <div class="meta-row">
        <span><strong>Candidate:</strong> {name}</span>
        <span><strong>Question {question_number} of {EXPECTED_MIN_QUESTIONS}+</strong></span>
    </div>
    """)

    progress = min(question_number / EXPECTED_MIN_QUESTIONS, 1.0)
    st.progress(progress)

    html(f"""
    <div class="question-card">
        <div class="question-label">Question {question_number}</div>
        <div class="question-text">{st.session_state.current_question}</div>
    </div>
    """)

    # A key tied to the question number guarantees this widget is a fresh
    # widget for every new question, so the answer box is always empty when
    # a new question appears (rather than mutating session_state directly,
    # which Streamlit disallows once a widget has been instantiated).
    answer_key = f"answer_input_{question_number}"

    with st.form(key=f"answer_form_{question_number}", clear_on_submit=False):
        answer = st.text_area(
            "Your answer",
            height=180,
            placeholder="Type your answer here...",
            key=answer_key,
            label_visibility="collapsed",
        )

        submitted = st.form_submit_button(
            "Submit Answer",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not answer.strip():
            st.warning("Please enter an answer before submitting.")
            return

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
            st.session_state.history.pop()
            st.error(error)
            return

        if data.get("done") is True:
            st.session_state.feedback = data.get("feedback", {})
            st.session_state.screen = "feedback"
            st.rerun()

        next_question = data.get("reply", "").strip()

        if not next_question:
            st.error("The backend did not return the next interview question.")
            return

        st.session_state.question_number += 1
        st.session_state.current_question = next_question

        st.rerun()

    if st.session_state.history:
        st.write("")
        st.markdown("##### Conversation history")

        total = len(st.session_state.history)

        for index, item in enumerate(reversed(st.session_state.history), start=1):
            with st.expander(f"Previous exchange {total - index + 1}", expanded=False):
                st.markdown(f"**Question**  \n{item['question']}")
                html(f"""
                <div class="history-answer">
                    <strong>Your answer</strong><br>
                    {item['answer']}
                </div>
                """)


# =========================================================
# Feedback screen
# =========================================================

def render_feedback():
    feedback = st.session_state.get("feedback") or {}

    html("""
    <div class="hero">
        <h1>Interview Complete</h1>
        <p>Here's your performance summary.</p>
    </div>
    """)

    overall_score = feedback.get("overall_score", 0)

    # Everything below lives inside ONE results-shell element so the score,
    # summary, strengths, weaknesses, recommendations, and curriculum
    # coverage read as one continuous results document rather than a stack
    # of separate floating cards. The shell is opened here and only closed
    # at the very end of the function; bullet lists in between are rendered
    # with native st.markdown (which renders bullets more reliably than
    # hand-written HTML <ul> markup), and each section opens/closes its own
    # inner <div> around that native content.

    html(f"""
    <div class="results-shell">
        <div class="results-top">
            <div class="score-block">
                <div class="score-label">Overall Score</div>
                <div class="score-value">{overall_score}<span class="score-suffix">/10</span></div>
            </div>
            <div class="summary-block">
                <div class="section-heading">Interview summary</div>
                <div class="small-muted">
                    Your interview included at least {EXPECTED_MIN_QUESTIONS} questions
                    and covered at least {EXPECTED_MIN_DAYS} curriculum days before
                    completion.
                </div>
            </div>
        </div>
        <div class="results-divider"></div>
    """)

    def render_list_section(title, items, empty_message, divider_after=True):
        html(f'<div class="results-section"><div class="section-heading">{title}</div>')

        if items:
            for item in items:
                st.markdown(f"- {item}")
        else:
            html(f'<div class="small-muted">{empty_message}</div>')

        html("</div>")

        if divider_after:
            html('<div class="results-divider"></div>')

    render_list_section("Strengths", feedback.get("strengths", []), "No strengths provided.")
    render_list_section("Weaknesses", feedback.get("weaknesses", []), "No weaknesses provided.")
    render_list_section(
        "Recommendations",
        feedback.get("recommendations", []),
        "No recommendations provided.",
    )

    html(f"""
        <div class="results-section">
            <div class="section-heading">Curriculum coverage</div>
            <div class="small-muted">
                The interview completion condition guarantees that at least
                <strong>{EXPECTED_MIN_DAYS} different completed curriculum days</strong>
                were covered. The backend response does not expose the exact
                covered-day list, so this page does not invent one.
            </div>
        </div>
    </div>
    """)

    st.write("")

    if st.button("Start New Interview", type="primary", use_container_width=True):
        reset_interview()
        st.session_state.screen = "home"
        st.rerun()


# =========================================================
# App
# =========================================================

initialize_state()

if st.session_state.screen == "home":
    render_home()
elif st.session_state.screen == "interview":
    render_interview()
elif st.session_state.screen == "feedback":
    render_feedback()