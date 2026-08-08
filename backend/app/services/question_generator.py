import os
from pathlib import Path
import json

from dotenv import load_dotenv
from google import genai


# Load local .env when running locally
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")

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

    return (
        f"Can you explain the main idea behind "
        f"{title}?"
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
    Generate exactly one clear, practical technical interview question
    for one curriculum day.
    """

    previous_questions = previous_questions or []
    # Select one objective instead of passing the entire
    # curriculum objective list to the model.
    objectives = str(
        selected_day.get("objectives", "")
    ).strip()

    objective_list = [
        objective.strip()
        for objective in objectives.split(";")
        if objective.strip()
    ]

    if objective_list:
        objective_index = (
            len(previous_questions)
            % len(objective_list)
        )

        selected_objective = objective_list[
            objective_index
        ]
    else:
        selected_objective = (
            selected_day.get("title", "")
        )

    previous_text = "\n".join(
        f"- {question}"
        for question in previous_questions
    )

    if not previous_text:
        previous_text = "None"

    if follow_up:
        question_type = """
Ask ONE natural follow-up question based on the
candidate's previous discussion.

The follow-up must stay on the same topic and should
help the interviewer understand the candidate's
knowledge more deeply.
"""
    else:
        question_type = """
Ask ONE realistic technical interview question.

Prefer questions that are commonly useful in
software engineering interviews, such as:
- explaining a core concept
- comparing two concepts
- explaining how something works
- solving a practical problem
- explaining a real-world use case
- debugging or reasoning about a situation
"""

    prompt = f"""
You are a professional technical interviewer conducting
a realistic software engineering interview.

Your goal is to ask a question that a real interviewer
could naturally ask a candidate.

CANDIDATE:
Name: {name}
Job Role: {job_role}
Years of Experience: {years_experience}

CURRENT CURRICULUM DAY:

Day:
{selected_day.get("day", "")}

Title:
{selected_day.get("title", "")}

Selected Objective:
{selected_objective}

PREVIOUS QUESTIONS:
{previous_text}

QUESTION REQUIREMENTS:

{question_type}

IMPORTANT STYLE RULES:

1. Use simple, clear and direct English.

2. The candidate should understand the question
   immediately after reading it once.

3. Do NOT make the question unnecessarily difficult.

4. Do NOT use complicated academic language.

5. Do NOT use unnecessary words or long scenarios.

6. Prefer natural interview wording such as:
   "What is...?"
   "How does...?"
   "Why do we use...?"
   "What is the difference between...?"
   "How would you...?"
   "Can you explain...?"
   "What happens if...?"

7. The question should test understanding and reasoning,
   not the candidate's ability to understand a complicated
   question.

8. The question should feel like something a real
   software engineering interviewer would ask.

9. Difficulty should be appropriate for the candidate's
   experience level.

10. For an experienced candidate, prefer practical
    application and reasoning over very basic definitions.

11. Do not turn a straightforward concept into an
    unnecessarily advanced or theoretical question.

STRICT CURRICULUM RULES:

12. The question MUST clearly relate to the current
    curriculum day.

13. You may ONLY use concepts explicitly supported by
    the SELECTED OBJECTIVE above.

14. Focus on this ONE objective only.

15. Do not combine multiple objectives into one question.

16. Do not mention the objective itself in the question.

17. Do not copy the objective wording into the question.

18. If a concept is not explicitly present in the
    title or objectives, DO NOT ask about it.

19. Do NOT introduce unrelated technical concepts.

20. Do NOT use concepts from other curriculum days.

21. Do NOT repeat any previous question.

OUTPUT RULES:

22. Return exactly ONE question.

23. Return ONLY the question.

24. Do not provide an answer.

25. Do not provide an explanation.

26. Do not add numbering or headings.

27. Do not use phrases such as:
    "Consider the following scenario..."
    unless a short scenario is genuinely necessary.

28. Keep the question concise.
29. Start the question with exactly the words "INTERVIEW TEST:".

Remember:

A good interview question is NOT necessarily a difficult
question.

It should be clear, relevant, practical and capable of
revealing how well the candidate understands the topic.
"""

    question = ""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        question = extract_response_text(response)

    except Exception as error:
        print(f"Question generation failed: {error}")

    # Retry only for errors other than quota/rate-limit errors.
    if not question:
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )

            question = extract_response_text(response)

        except Exception as error:
            print(f"Question retry failed: {error}")

    # Final fallback
    if not question:
        question = fallback_question(selected_day)

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
    # =====================================================
# GENERATE QUESTION FOR A SPECIFIC CURRICULUM DAY
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
    Generate exactly one clear, practical technical interview question
    for one curriculum day.
    """

    previous_questions = previous_questions or []

    print(">>> NEW QUESTION GENERATOR IS RUNNING <<<")

    previous_text = "\n".join(
        f"- {question}"
        for question in previous_questions
    )

    if not previous_text:
        previous_text = "None"

    if follow_up:
        question_type = """
Ask ONE natural follow-up question based on the
candidate's previous discussion.

The follow-up must stay on the same topic and help
the interviewer understand the candidate's knowledge
more deeply.
"""
    else:
        question_type = """
Ask ONE realistic technical interview question.

Prefer questions that are commonly useful in
software engineering interviews, such as:
- explaining a core concept
- comparing two concepts
- explaining how something works
- solving a practical problem
- explaining a real-world use case
- debugging or reasoning about a situation
"""

    prompt = f"""
You are a professional technical interviewer conducting
a realistic software engineering interview.

Your goal is to ask a question that a real interviewer
could naturally ask a candidate.

CANDIDATE:
Name: {name}
Job Role: {job_role}
Years of Experience: {years_experience}

CURRENT CURRICULUM DAY:

Day:
{selected_day.get("day", "")}

Title:
{selected_day.get("title", "")}

Objectives:
{selected_day.get("objectives", "")}

PREVIOUS QUESTIONS:
{previous_text}

QUESTION REQUIREMENTS:

{question_type}

IMPORTANT STYLE RULES:

1. Use simple, clear and direct English.

2. The candidate should understand the question
   immediately after reading it once.

3. Do NOT make the question unnecessarily difficult.

4. Do NOT use complicated academic language.

5. Do NOT use unnecessary words or long scenarios.

6. Prefer natural interview wording such as:
   "What is...?"
   "How does...?"
   "Why do we use...?"
   "What is the difference between...?"
   "How would you...?"
   "Can you explain...?"
   "What happens if...?"

7. The question should test understanding and reasoning,
   not the candidate's ability to understand a complicated
   question.

8. The question should feel like something a real
   software engineering interviewer would ask.

9. Difficulty should be appropriate for the candidate's
   experience level.

10. For an experienced candidate, prefer practical
    application and reasoning over very basic definitions.

11. Do not turn a straightforward concept into an
    unnecessarily advanced or theoretical question.

STRICT CURRICULUM RULES:

12. The question MUST clearly relate to the current
    curriculum day.

13. You may ONLY use concepts explicitly supported by
    the curriculum TITLE and OBJECTIVES above.

14. If a concept is not explicitly present in the
    title or objectives, DO NOT ask about it.

15. Do NOT introduce unrelated technical concepts.

16. Do NOT use concepts from other curriculum days.

17. Do NOT repeat any previous question.

OUTPUT RULES:

18. Return exactly ONE question.

19. Return ONLY the question.

20. Do not provide an answer.

21. Do not provide an explanation.

22. Do not add numbering or headings.

23. Do not use phrases such as:
    "Consider the following scenario..."
    unless a short scenario is genuinely necessary.

24. Keep the question concise.

A good interview question is NOT necessarily a difficult
question.

It should be clear, relevant, practical and capable of
revealing how well the candidate understands the topic.
"""

    question = ""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        question = extract_response_text(response)

    except Exception as error:
        print(f"Question generation failed: {error}")

    # Retry once
    if not question:
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )

            question = extract_response_text(response)

        except Exception as error:
            print(f"Question retry failed: {error}")

    # Final fallback
    if not question:
        question = fallback_question(selected_day)

    return question


# =====================================================
# EVALUATE CANDIDATE ANSWER
# =====================================================

def evaluate_answer(
    question,
    answer,
    curriculum_day,
):
    prompt = f"""
Evaluate this technical interview answer.

Curriculum day:
{curriculum_day}

Question:
{question}

Candidate answer:
{answer}

Return ONLY valid JSON:

{{
    "score": 0,
    "needs_clarification": false,
    "reason": ""
}}

Rules:
- score must be from 0 to 10.
- needs_clarification is true if the answer is
  weak, incomplete, vague, or incorrect.
- needs_clarification is false if the answer
  adequately addresses the question.
- Evaluate only against the question and curriculum topic.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        text = extract_response_text(response)

        if text:
            text = (
                text
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

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
                    result.get("reason", "")
                ),
            }

    except Exception as error:
        print(
            f"Answer evaluation failed: {error}"
        )

    # Safe fallback
    if len(answer.strip()) < 20:
        return {
            "score": 3,
            "needs_clarification": True,
            "reason": "Answer is too short or incomplete."
        }

    return {
        "score": 6,
        "needs_clarification": False,
        "reason": "Answer appears sufficiently detailed."
    }


# =====================================================
# GENERATE FINAL FEEDBACK
# =====================================================

def generate_feedback(
    candidate,
    history,
):
    history_text = ""

    for item in history:
        history_text += f"""
Question: {item.get("question", "")}
Answer: {item.get("answer", "")}
Curriculum Day: {item.get("day", "")}
Score: {item.get("score", 0)}
Evaluation: {item.get("evaluation", "")}

---
"""

    prompt = f"""
Generate final technical interview feedback.

Candidate:
Name: {candidate.get("name", "Candidate")}
Role: {candidate.get("jobRole", "Technical")}
Experience: {candidate.get("yearsExperience", 0)} years

COMPLETE INTERVIEW HISTORY:

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
- strengths must be a list of strings.
- weaknesses must be a list of strings.
- recommendations must be a list of strings.
- Base feedback only on the interview history.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        text = extract_response_text(response)

        if text:
            text = (
                text
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

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
        "Completed the technical interview."
    ],
    "weaknesses": [
        "Detailed feedback generation was unavailable."
    ],
    "recommendations": [
        "Continue practicing the topics covered in the interview."
    ],
}