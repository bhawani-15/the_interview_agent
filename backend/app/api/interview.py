from fastapi import APIRouter

from backend.app.schemas.interview import (
    InterviewRequest,
    InterviewResponse,
)

from backend.app.services.data_loader import (
    load_candidates,
    load_curriculum,
)

from backend.app.services.interview_session import (
    session_manager,
)

from backend.app.services.question_generator import (
    generate_first_question,
    generate_question_for_day,
    evaluate_answer,
    generate_feedback,
)


router = APIRouter(
    prefix="/api",
    tags=["Interview"]
)


# =========================================================
# Candidate helpers
# =========================================================

def get_candidates_list(candidates):

    if isinstance(candidates, list):
        return candidates

    if isinstance(candidates, dict):

        value = candidates.get("candidates")

        if isinstance(value, list):
            return value

        value = candidates.get("data")

        if isinstance(value, list):
            return value

    return []


def get_candidate_id(candidate):

    if not isinstance(candidate, dict):
        return None

    for key in (
        "id",
        "candidateId",
        "candidate_id",
        "candidateID",
    ):

        value = candidate.get(key)

        if value is not None:
            return str(value)

    member = candidate.get("member")

    if isinstance(member, dict):

        for key in (
            "id",
            "candidateId",
            "candidate_id",
            "candidateID",
        ):

            value = member.get(key)

            if value is not None:
                return str(value)

    return None


def normalize_candidate(candidate):

    if not isinstance(candidate, dict):
        return None

    member = candidate.get("member")

    if isinstance(member, dict):

        normalized = dict(member)

        normalized["missions"] = candidate.get(
            "missions",
            []
        )

        return normalized

    return candidate


def find_candidate_by_id(
    candidates,
    candidate_id,
):

    if candidate_id is None:
        return None

    candidate_id = str(candidate_id)

    for candidate in get_candidates_list(
        candidates
    ):

        if not isinstance(candidate, dict):
            continue

        stored_id = get_candidate_id(
            candidate
        )

        if stored_id == candidate_id:

            return normalize_candidate(
                candidate
            )

    return None


# =========================================================
# Mission helpers
# =========================================================

def get_missions(candidate):

    if not isinstance(candidate, dict):
        return []

    missions = candidate.get(
        "missions",
        []
    )

    return (
        missions
        if isinstance(missions, list)
        else []
    )


def get_completed_missions(candidate):

    return [
        mission
        for mission in get_missions(candidate)
        if (
            isinstance(mission, dict)
            and mission.get("passed") is True
            and mission.get("skipped") is not True
        )
    ]


def get_mission_day(mission):

    if not isinstance(mission, dict):
        return None

    for key in (
        "day",
        "dayId",
        "day_id",
        "curriculumDay",
        "curriculum_day",
        "missionDay",
        "mission_day",
    ):

        value = mission.get(key)

        if value is not None:
            return value

    return None


# =========================================================
# Curriculum helpers
# =========================================================

def get_curriculum_days(curriculum):

    if isinstance(curriculum, list):
        return curriculum

    if isinstance(curriculum, dict):

        for key in (
            "days",
            "curriculum",
            "data",
        ):

            value = curriculum.get(key)

            if isinstance(value, list):
                return value

    return []


def get_curriculum_day_id(day):

    if not isinstance(day, dict):
        return None

    for key in (
        "day",
        "id",
        "dayId",
        "day_id",
    ):

        value = day.get(key)

        if value is not None:
            return value

    return None


def get_day_title(day):

    if not isinstance(day, dict):
        return ""

    return str(
        day.get("title")
        or day.get("name")
        or ""
    ).strip()


def get_day_objectives(day):

    if not isinstance(day, dict):
        return ""

    objectives = (
        day.get("objectives")
        or day.get("objective")
        or ""
    )

    if isinstance(objectives, list):

        return "; ".join(
            str(item).strip()
            for item in objectives
            if item
        )

    return str(objectives).strip()


def find_completed_curriculum_days(
    candidate,
    curriculum,
):

    completed_missions = (
        get_completed_missions(candidate)
    )

    curriculum_days = (
        get_curriculum_days(curriculum)
    )

    completed_days = []
    matched_missions = []

    for mission in completed_missions:

        mission_day = get_mission_day(
            mission
        )

        if mission_day is None:
            continue

        for day in curriculum_days:

            if not isinstance(day, dict):
                continue

            curriculum_day_id = (
                get_curriculum_day_id(day)
            )

            if curriculum_day_id is None:
                continue

            if str(mission_day) != str(
                curriculum_day_id
            ):
                continue

            completed_days.append({
                "day": curriculum_day_id,
                "title": get_day_title(day),
                "objectives": get_day_objectives(day),
            })

            matched_missions.append(
                mission
            )

            break

    return (
        completed_days,
        matched_missions,
    )


# =========================================================
# Session helpers
# =========================================================

def initialize_session_state(session):

    session.setdefault(
        "question_count",
        0
    )

    session.setdefault(
        "questions",
        []
    )

    session.setdefault(
        "answers",
        []
    )

    session.setdefault(
        "covered_days",
        []
    )

    session.setdefault(
        "history",
        []
    )

    session.setdefault(
        "current_question_day",
        None
    )

    session.setdefault(
        "current_question",
        None
    )

    session.setdefault(
        "feedback",
        None
    )


def question_already_asked(
    session,
    question,
):

    normalized = question.strip().lower()

    return any(
        q.strip().lower() == normalized
        for q in session.get(
            "questions",
            []
        )
    )


def get_next_curriculum_day(
    completed_days,
    covered_days,
):

    covered = {
        str(day)
        for day in covered_days
    }

    # Prefer an entirely new curriculum day.
    for day in completed_days:

        day_id = day.get("day")

        if str(day_id) not in covered:
            return day

    # If all days have been covered,
    # return the first one. The question itself
    # will still be prevented from repeating.
    return (
        completed_days[0]
        if completed_days
        else None
    )


def get_different_day(
    completed_days,
    covered_days,
):

    covered = {
        str(day)
        for day in covered_days
    }

    for day in completed_days:

        if str(day.get("day")) not in covered:
            return day

    return None


# =========================================================
# POST /api/interview
# =========================================================

@router.post(
    "/interview",
    response_model=InterviewResponse,
)
def interview(request: InterviewRequest):

    # =====================================================
    # 1. NEW SESSION
    # =====================================================

    if request.candidate is not None:

        supplied_candidate = request.candidate

        if not isinstance(
            supplied_candidate,
            dict,
        ):

            return InterviewResponse(
                reply="Invalid candidate data",
                done=False,
            )

        # -------------------------------------------------
        # Find full candidate
        # -------------------------------------------------

        candidate_id = get_candidate_id(
            supplied_candidate
        )

        candidate = None

        if candidate_id is not None:

            candidates = load_candidates()

            candidate = find_candidate_by_id(
                candidates,
                candidate_id,
            )

        # -------------------------------------------------
        # Fallback
        # -------------------------------------------------

        if candidate is None:

            candidate = normalize_candidate(
                supplied_candidate
            )

        # -------------------------------------------------
        # Create session FIRST
        # -------------------------------------------------

        session = session_manager.create_session(
            request.sessionId,
            candidate,
        )

        initialize_session_state(
            session
        )

        # -------------------------------------------------
        # Load curriculum
        # -------------------------------------------------

        curriculum = load_curriculum()

        (
            completed_days,
            matched_missions,
        ) = find_completed_curriculum_days(
            candidate,
            curriculum,
        )

        if not completed_days:

            return InterviewResponse(
                reply=(
                    "No completed curriculum "
                    "days were found for this candidate."
                ),
                done=False,
            )

        # -------------------------------------------------
        # Candidate details
        # -------------------------------------------------

        name = candidate.get(
            "name",
            "Candidate",
        )

        job_role = candidate.get(
            "jobRole",
            "Technical",
        )

        years_experience = candidate.get(
            "yearsExperience",
            0,
        )

        # -------------------------------------------------
        # Mission attempts
        # -------------------------------------------------

        mission_attempts = []

        for mission in matched_missions:

            mission_name = (
                mission.get("name")
                or mission.get("mission")
                or mission.get("title")
                or ""
            )

            mission_attempts.append({
                "mission": str(
                    mission_name
                ),
                "attempts": mission.get(
                    "attempts",
                    0,
                ),
            })

        # -------------------------------------------------
        # Generate first question
        # -------------------------------------------------

        (
            question,
            selected_day,
        ) = generate_first_question(
            name=name,
            job_role=job_role,
            years_experience=years_experience,
            completed_days=completed_days,
            mission_attempts=mission_attempts,
        )

        # -------------------------------------------------
        # Store question
        # -------------------------------------------------

        session["question_count"] = 1

        session["questions"].append(
            question
        )

        session["covered_days"] = [
            selected_day
        ]

        session["current_question_day"] = (
            selected_day
        )

        session["current_question"] = (
            question
        )

        return InterviewResponse(
            reply=question,
            done=False,
        )

    # =====================================================
    # 2. EXISTING SESSION
    # =====================================================

    session = session_manager.get_session(
        request.sessionId
    )

    if session is None:

        return InterviewResponse(
            reply=(
                "Session not found. "
                "Start a new interview session first."
            ),
            done=False,
        )

    initialize_session_state(
        session
    )

    answer = (
        request.message or ""
    ).strip()

    if not answer:

        return InterviewResponse(
            reply="Please provide an answer.",
            done=False,
        )

    # =====================================================
    # SAVE ANSWER
    # =====================================================

    session["answers"].append(
        answer
    )

    current_question = (
        session.get(
            "current_question"
        )
        or (
            session["questions"][-1]
            if session["questions"]
            else ""
        )
    )

    current_day = session.get(
        "current_question_day"
    )

    # =====================================================
    # LOAD CURRICULUM AGAIN
    # =====================================================

    curriculum = load_curriculum()

    candidate = session.get(
        "candidate",
        {}
    )

    (
        completed_days,
        _,
    ) = find_completed_curriculum_days(
        candidate,
        curriculum,
    )

    # =====================================================
    # EVALUATE ANSWER
    # =====================================================

    evaluation = evaluate_answer(
        question=current_question,
        answer=answer,
        curriculum_day=current_day,
    )

    # =====================================================
    # ADD QUESTION + ANSWER TO HISTORY
    # =====================================================

    history_item = {
        "question": current_question,
        "answer": answer,
        "day": current_day,
        "score": evaluation.get(
            "score",
            0,
        ),
        "evaluation": evaluation.get(
            "reason",
            "",
        ),
    }

    session["history"].append(
        history_item
    )

    # =====================================================
    # CHECK WHETHER INTERVIEW IS FINISHED
    # =====================================================

    question_count = session[
        "question_count"
    ]

    covered_count = len(
        set(
            str(day)
            for day in session[
                "covered_days"
            ]
        )
    )

    # We can only finish after BOTH conditions:
    # - at least 8 questions
    # - at least 4 curriculum days
    #
    # Since the current answer belongs to the
    # current question, question_count already
    # represents the number of questions asked.

    if (
        question_count >= 8
        and covered_count >= 4
    ):

        feedback = generate_feedback(
            candidate=candidate,
            history=session["history"],
        )

        session["feedback"] = feedback

        return InterviewResponse(
            reply="Interview completed.",
            done=True,
            feedback=feedback,
        )

    # =====================================================
    # DECIDE NEXT QUESTION
    # =====================================================

    needs_follow_up = evaluation.get(
        "needs_clarification",
        False,
    )

    name = candidate.get(
        "name",
        "Candidate",
    )

    job_role = candidate.get(
        "jobRole",
        "Technical",
    )

    years_experience = candidate.get(
        "yearsExperience",
        0,
    )

    # -----------------------------------------------------
    # FOLLOW-UP
    # -----------------------------------------------------

    if needs_follow_up:

        selected_day = next(
            (
                day
                for day in completed_days
                if str(day.get("day"))
                == str(current_day)
            ),
            None,
        )

        if selected_day is not None:

            next_question = (
                generate_question_for_day(
                    name=name,
                    job_role=job_role,
                    years_experience=years_experience,
                    selected_day=selected_day,
                    previous_questions=session[
                        "questions"
                    ],
                    follow_up=True,
                )
            )

            # Never repeat a question.
            if not question_already_asked(
                session,
                next_question,
            ):

                session[
                    "question_count"
                ] += 1

                session[
                    "questions"
                ].append(
                    next_question
                )

                session[
                    "current_question"
                ] = next_question

                session[
                    "current_question_day"
                ] = selected_day.get(
                    "day"
                )

                return InterviewResponse(
                    reply=next_question,
                    done=False,
                )

    # =====================================================
    # MOVE TO DIFFERENT CURRICULUM DAY
    # =====================================================

    selected_day = get_different_day(
        completed_days,
        session["covered_days"],
    )

    # If there are no uncovered days left,
    # choose another completed day.
    if selected_day is None:

        selected_day = get_next_curriculum_day(
            completed_days,
            session["covered_days"],
        )

    if selected_day is None:

        return InterviewResponse(
            reply="Interview completed.",
            done=True,
            feedback=generate_feedback(
                candidate=candidate,
                history=session["history"],
            ),
        )

    # -----------------------------------------------------
    # Generate new-topic question
    # -----------------------------------------------------

    next_question = generate_question_for_day(
        name=name,
        job_role=job_role,
        years_experience=years_experience,
        selected_day=selected_day,
        previous_questions=session[
            "questions"
        ],
        follow_up=False,
    )

    # -----------------------------------------------------
    # Safety: never repeat
    # -----------------------------------------------------

    attempts = 0

    while (
        question_already_asked(
            session,
            next_question,
        )
        and attempts < 2
    ):

        next_question = generate_question_for_day(
            name=name,
            job_role=job_role,
            years_experience=years_experience,
            selected_day=selected_day,
            previous_questions=session[
                "questions"
            ],
            follow_up=False,
        )

        attempts += 1

    # -----------------------------------------------------
    # Store new question
    # -----------------------------------------------------

    session["question_count"] += 1

    session["questions"].append(
        next_question
    )

    day_id = selected_day.get(
        "day"
    )

    if day_id not in session[
        "covered_days"
    ]:

        session[
            "covered_days"
        ].append(
            day_id
        )

    session[
        "current_question_day"
    ] = day_id

    session[
        "current_question"
    ] = next_question

    return InterviewResponse(
        reply=next_question,
        done=False,
    )