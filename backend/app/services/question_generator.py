from pathlib import Path
import json

from dotenv import dotenv_values
from google import genai


# -----------------------------------------------------
# Load Gemini API key directly from backend/.env
# -----------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

env = dotenv_values(BASE_DIR / ".env")

api_key = env.get("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")

client = genai.Client(api_key=api_key)


# =====================================================
# RESPONSE EXTRACTION
# =====================================================

def extract_response_text(response):
    """
    Safely extract generated text from Gemini.
    """

    text = getattr(response, "text", None)

    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None)

    if not candidates:
        return ""

    for candidate in candidates:

        content = getattr(
            candidate,
            "content",
            None
        )

        if content is None:
            continue

        parts = getattr(
            content,
            "parts",
            None
        )

        if not parts:
            continue

        texts = []

        for part in parts:

            part_text = getattr(
                part,
                "text",
                None
            )

            if isinstance(
                part_text,
                str
            ) and part_text.strip():

                texts.append(
                    part_text.strip()
                )

        if texts:
            return " ".join(texts).strip()

    return ""


# =====================================================
# CURRICULUM
# =====================================================

def build_curriculum_text(completed_days):

    sections = []

    for day in completed_days:

        sections.append(
            f"""
Curriculum Day: {day.get("day", "")}
Title: {day.get("title", "")}
Objectives: {day.get("objectives", "")}
""".strip()
        )

    return "\n\n".join(sections)


# =====================================================
# FALLBACK QUESTION
# =====================================================

def fallback_question(selected_day):

    title = str(
        selected_day.get("title")
        or "this curriculum topic"
    ).strip()

    objective = str(
        selected_day.get("objectives")
        or ""
    ).strip()

    if objective:

        return (
            f"Based on the objective "
            f"'{objective}', can you explain "
            f"how you would apply what you learned "
            f"in {title}?"
        )

    return (
        f"Can you explain the key concepts "
        f"covered in {title}?"
    )


# =====================================================
# QUESTION GENERATION FOR A SPECIFIC DAY
# =====================================================

def generate_question_for_day(
    name,
    job_role,
    years_experience,
    selected_day,
    previous_questions=None,
    follow_up=False,
):
    """
    Generate exactly one question for one curriculum day.

    Gemini is strictly grounded in the supplied
    title and objectives.
    """

    previous_questions = previous_questions or []

    previous_text = "\n".join(
        f"- {question}"
        for question in previous_questions
    )

    if not previous_text:
        previous_text = "None"

    question_type = (
        "Ask ONE follow-up question about the same topic."
        if follow_up
        else "Ask ONE technical interview question."
    )

    prompt = f"""
You are conducting a technical interview.

Candidate:
Name: {name}
Job Role: {job_role}
Years of Experience: {years_experience}

CURRENT CURRICULUM DAY:

Day: {selected_day.get("day", "")}

Title:
{selected_day.get("title", "")}

Objectives:
{selected_day.get("objectives", "")}

PREVIOUS QUESTIONS:
{previous_text}

STRICT GROUNDING RULES:

1. {question_type}

2. The question MUST clearly relate to this
   specific curriculum day.

3. You may ONLY use information contained in
   the curriculum TITLE and OBJECTIVES provided above.

4. If a concept is not explicitly present in the
   title or objectives, DO NOT ask about it.

5. Do NOT introduce unrelated technical concepts.

6. Do NOT use concepts from other curriculum days.

7. Do NOT repeat any previous question.

8. Return exactly ONE question.

9. Return ONLY the question.

10. Do not provide an answer.

11. Do not provide an explanation.

12. Do not add numbering or headings.

You may ONLY use information contained in the
provided curriculum titles and objectives.
If a concept is not explicitly present there,
do not ask about it.
"""

    question = ""

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        question = extract_response_text(
            response
        )

    except Exception as error:

        print(
            f"Question generation failed: {error}"
        )

    # Retry once
    if not question:

        try:

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )

            question = extract_response_text(
                response
            )

        except Exception as error:

            print(
                f"Question retry failed: {error}"
            )

    # Final fallback
    if not question:

        question = fallback_question(
            selected_day
        )

    return question


# =====================================================
# FIRST QUESTION
# =====================================================

def generate_first_question(
    name: str,
    job_role: str,
    years_experience,
    completed_days: list,
    mission_attempts: list,
):

    if not completed_days:

        return (
            "Can you explain one of the technical "
            "concepts you completed in your curriculum?",
            None,
        )

    selected_day = completed_days[0]

    question = generate_question_for_day(
        name=name,
        job_role=job_role,
        years_experience=years_experience,
        selected_day=selected_day,
        previous_questions=[],
        follow_up=False,
    )

    return (
        question,
        selected_day.get("day"),
    )


# =====================================================
# ANSWER EVALUATION
# =====================================================

def evaluate_answer(
    question,
    answer,
    curriculum_day,
):
    """
    Ask Gemini whether the candidate's answer
    needs clarification.

    Returns a simple dictionary.
    """

    prompt = f"""
Evaluate a candidate's answer to a technical
interview question.

CURRICULUM DAY:
{curriculum_day}

QUESTION:
{question}

CANDIDATE ANSWER:
{answer}

Evaluate ONLY against the question and its
curriculum topic.

Return ONLY valid JSON:

{{
  "score": 0,
  "needs_clarification": false,
  "reason": "short explanation"
}}

Rules:

- score must be between 0 and 10.
- needs_clarification should be true if the answer
  is weak, incorrect, vague, incomplete, or needs
  clarification.
- needs_clarification should be false if the answer
  adequately addresses the question.
- Do not introduce concepts outside the question
  or curriculum topic.
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        text = extract_response_text(
            response
        )

        if text:

            # Remove accidental markdown fences
            text = text.replace(
                "```json",
                ""
            ).replace(
                "```",
                ""
            ).strip()

            result = json.loads(text)

            return {
                "score": int(
                    result.get("score", 0)
                ),
                "needs_clarification": bool(
                    result.get(
                        "needs_clarification",
                        False
                    )
                ),
                "reason": str(
                    result.get(
                        "reason",
                        ""
                    )
                ),
            }

    except Exception as error:

        print(
            f"Answer evaluation failed: {error}"
        )

    # Safe fallback
    weak = len(
        answer.strip()
    ) < 20

    return {
        "score": 3 if weak else 6,
        "needs_clarification": weak,
        "reason": (
            "Answer was too short to evaluate confidently."
            if weak
            else "Answer appears sufficiently detailed."
        ),
    }


# =====================================================
# FINAL FEEDBACK
# =====================================================

def generate_feedback(
    candidate,
    history,
):
    """
    Generate structured final interview feedback.
    """

    history_text = ""

    for item in history:

        history_text += f"""
Question:
{item.get("question", "")}

Answer:
{item.get("answer", "")}

Score:
{item.get("score", 0)}

Topic:
{item.get("day", "")}
---
"""

    prompt = f"""
Generate final technical interview feedback.

Candidate:
Name: {candidate.get("name", "Candidate")}
Job Role: {candidate.get("jobRole", "Technical")}
Years Experience: {candidate.get("yearsExperience", 0)}

INTERVIEW HISTORY:

{history_text}

Return ONLY valid JSON:

{{
  "overall_score": 0,
  "strengths": [],
  "weaknesses": [],
  "recommendations": []
}}

Rules:

- overall_score must be between 0 and 10.
- strengths must be a list of concise strings.
- weaknesses must be a list of concise strings.
- recommendations must be a list of concise strings.
- Base the feedback only on the interview history.
"""

    try:

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        text = extract_response_text(
            response
        )

        if text:

            text = text.replace(
                "```json",
                ""
            ).replace(
                "```",
                ""
            ).strip()

            result = json.loads(text)

            return {
                "overall_score": float(
                    result.get(
                        "overall_score",
                        0
                    )
                ),
                "strengths": result.get(
                    "strengths",
                    []
                ),
                "weaknesses": result.get(
                    "weaknesses",
                    []
                ),
                "recommendations": result.get(
                    "recommendations",
                    []
                ),
            }

    except Exception as error:

        print(
            f"Feedback generation failed: {error}"
        )

    # Fallback feedback
    scores = [
        item.get("score", 0)
        for item in history
    ]

    average = (
        sum(scores) / len(scores)
        if scores
        else 0
    )

    return {
        "overall_score": round(
            average,
            1
        ),
        "strengths": [
            "Completed the interview."
        ],
        "weaknesses": [
            "Detailed evaluation was unavailable."
        ],
        "recommendations": [
            "Continue practicing the completed curriculum topics."
        ],
    }