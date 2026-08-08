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
    tags=["Interview"],
)


# =========================================================
# CANDIDATE HELPERS
# =========================================================

def get_candidates_list(candidates):
    """
    Support the actual candidates.json structure and
    common fallback structures.
    """

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
    """
    Candidate ID may exist directly on the candidate
    or inside candidate["member"].
    """

    if not isinstance(candidate, dict):
        return None

    # Direct ID
    for key in (
        "id",
        "candidateId",
        "candidate_id",
        "candidateID",
    ):

        value = candidate.get(key)

        if value is not None:
            return str(value)

    # Actual candidates.json structure:
    # candidate["member"]["id"]
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
    """
    Convert the actual candidate structure:

        {
            "member": {...},
            "missions": [...]
        }

    into:

        {
            "id": ...,
            "name": ...,
            "jobRole": ...,
            "yearsExperience": ...,
            "missions": [...]
        }
    """

    if not isinstance(candidate, dict):
        return None

    member = candidate.get("member")

    if isinstance(member, dict):

        normalized = dict(member)

        normalized["missions"] = candidate.get(
            "missions",
            [],
        )

        return normalized

    return candidate


def find_candidate_by_id(
    candidates,
    candidate_id,
):
    """
    Find the full candidate record from candidates.json.
    """

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
# MISSION HELPERS
# =========================================================

def get_missions(candidate):

    if not isinstance(candidate, dict):
        return []

    missions = candidate.get(
        "missions",
        [],
    )

    if isinstance(missions, list):
        return missions

    return []


def get_completed_missions(candidate):
    """
    Only missions satisfying:

        passed == true
        skipped != true
    """

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
# CURRICULUM HELPERS
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
    """
    Match only passed and non-skipped missions
    to their curriculum days.
    """

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
# SESSION HELPERS
# =========================================================

def initialize_session_state(session):
    """
    Make sure existing sessions have all fields required
    for the multi-turn interview.
    """

    session.setdefault(
        "question_count",
        0,
    )

    session.setdefault(
        "questions",
        [],
    )

    session.setdefault(
        "answers",
        [],
    )

    session.setdefault(
        "covered_days",
        [],
    )

    session.setdefault(
        "history",
        [],
    )

    session.setdefault(
        "evaluations",
        [],
    )

    session.setdefault(
        "current_question",
        None,
    )

    session.setdefault(
        "current_question_day",
        None,
    )

    session.setdefault(
        "feedback",
        None,
    )

    session.setdefault(
        "follow_up_used",
        False,
    )


def question_already_asked(
    session,
    question,
):
    """
    Prevent exact question repetition.
    """

    if not question:
        return True

    normalized = (
        question.strip().lower()
    )

    return any(
        existing.strip().lower()
        == normalized
        for existing in session.get(
            "questions",
            [],
        )
    )


def find_day_by_id(
    completed_days,
    day_id,
):
    for day in completed_days:

        if str(day.get("day")) == str(day_id):
            return day

    return None


def get_uncovered_day(
    completed_days,
    covered_days,
):
    """
    Prefer a curriculum day that has not yet
    been covered.
    """

    covered = {
        str(day)
        for day in covered_days
    }

    for day in completed_days:

        if str(day.get("day")) not in covered:
            return day

    return None


def get_next_available_day(
    completed_days,
    covered_days,
    question_count,
):
    """
    Once all days have been covered, choose a day
    again only when necessary to reach 8 questions.
    """

    if not completed_days:
        return None

    covered = {
        str(day)
        for day in covered_days
    }

    # Prefer uncovered days.
    for day in completed_days:

        if str(day.get("day")) not in covered:
            return day

    # All days have been covered.
    # Reuse a day only because reaching 8 questions
    # may require it.
    index = (
        question_count - 1
    ) % len(completed_days)

    return completed_days[index]


# =========================================================
# POST /api/interview
# =========================================================

@router.post(
    "/interview",
    response_model=InterviewResponse,
)
def interview(
    request: InterviewRequest,
):

    # =====================================================
    # NEW SESSION
    # =====================================================
    #
    # A request containing `candidate` starts an interview.
    #
    # This path happens BEFORE the existing-session lookup.
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
        # Try to find the complete candidate record
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
        # If lookup fails, use supplied candidate
        # -------------------------------------------------

        if candidate is None:

            candidate = normalize_candidate(
                supplied_candidate
            )

        # -------------------------------------------------
        # Create session BEFORE generating question
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
        # Candidate information
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
        # Generate FIRST question
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
        # Safety: never allow empty question
        # -------------------------------------------------

        if not question:

            selected_day_data = (
                find_day_by_id(
                    completed_days,
                    selected_day,
                )
            )

            if selected_day_data is not None:

                objective = (
                    selected_day_data.get(
                        "objectives"
                    )
                    or selected_day_data.get(
                        "title"
                    )
                    or "this curriculum topic"
                )

                question = (
                    f"Can you explain what you "
                    f"understood about {objective}?"
                )

            else:

                question = (
                    "Can you explain one of "
                    "the completed curriculum topics?"
                )

        # -------------------------------------------------
        # Store first question
        # -------------------------------------------------

        session["question_count"] = 1

        session["questions"].append(
            question
        )

        session["covered_days"] = [
            selected_day
        ]

        session["current_question"] = (
            question
        )

        session["current_question_day"] = (
            selected_day
        )

        session["follow_up_used"] = False

        # -------------------------------------------------
        # IMPORTANT:
        # Return the actual question.
        # Never reply="".
        # -------------------------------------------------

        return InterviewResponse(
            reply=question,
            done=False,
        )

    # =====================================================
    # EXISTING SESSION
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

    # -----------------------------------------------------
    # Candidate answer
    # -----------------------------------------------------

    answer = (
        request.message or ""
    ).strip()

    if not answer:

        return InterviewResponse(
            reply=(
                "Please provide an answer "
                "to the current question."
            ),
            done=False,
        )

    # -----------------------------------------------------
    # Get current question/day
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Save answer
    # -----------------------------------------------------

    session["answers"].append(
        answer
    )

    # =====================================================
    # LOAD CURRICULUM
    # =====================================================

    curriculum = load_curriculum()

    (
        completed_days,
        _,
    ) = find_completed_curriculum_days(
        session["candidate"],
        curriculum,
    )

    # =====================================================
    # EVALUATE ANSWER WITH GEMINI
    # =====================================================

    evaluation = evaluate_answer(
        question=current_question,
        answer=answer,
        curriculum_day=current_day,
    )

    # -----------------------------------------------------
    # Store evaluation
    # -----------------------------------------------------

    session["evaluations"].append(
        evaluation
    )

    # -----------------------------------------------------
    # Store complete history
    # -----------------------------------------------------

    session["history"].append({
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
    })

    # =====================================================
    # CHECK WHETHER INTERVIEW CAN END
    # =====================================================

    question_count = session[
        "question_count"
    ]

    covered_count = len(
        {
            str(day)
            for day in session[
                "covered_days"
            ]
        }
    )

    # Must have:
    #   >= 8 questions
    #   >= 4 curriculum days
    #
    # Only then is the interview complete.

    if (
        question_count >= 8
        and covered_count >= 4
    ):

        feedback = generate_feedback(
            candidate=session[
                "candidate"
            ],
            history=session[
                "history"
            ],
        )

        session["feedback"] = feedback

        return InterviewResponse(
            reply="Interview complete",
            done=True,
            feedback=feedback,
        )

    # =====================================================
    # CANDIDATE INFORMATION
    # =====================================================

    candidate = session[
        "candidate"
    ]

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

    # =====================================================
    # FOLLOW-UP LOGIC
    # =====================================================
    #
    # A weak/incomplete answer gets at most ONE follow-up
    # on the same curriculum day.
    # =====================================================

    needs_follow_up = evaluation.get(
        "needs_clarification",
        False,
    )

    if (
        needs_follow_up
        and not session.get(
            "follow_up_used",
            False,
        )
    ):

        same_day = find_day_by_id(
            completed_days,
            current_day,
        )

        if same_day is not None:

            follow_up = (
                generate_question_for_day(
                    name=name,
                    job_role=job_role,
                    years_experience=years_experience,
                    selected_day=same_day,
                    previous_questions=session[
                        "questions"
                    ],
                    follow_up=True,
                )
            )

            # Never repeat.
            if (
                follow_up
                and not question_already_asked(
                    session,
                    follow_up,
                )
            ):

                session[
                    "question_count"
                ] += 1

                session[
                    "questions"
                ].append(
                    follow_up
                )

                session[
                    "current_question"
                ] = follow_up

                session[
                    "current_question_day"
                ] = current_day

                session[
                    "follow_up_used"
                ] = True

                # IMPORTANT:
                # Return the actual follow-up question.
                return InterviewResponse(
                    reply=follow_up,
                    done=False,
                )

    # =====================================================
    # MOVE TO ANOTHER CURRICULUM DAY
    # =====================================================

    selected_day = get_uncovered_day(
        completed_days,
        session["covered_days"],
    )

    # -----------------------------------------------------
    # If all days have already been covered,
    # reuse a day only because we still need questions
    # to reach the minimum of 8.
    # -----------------------------------------------------

    if selected_day is None:

        selected_day = get_next_available_day(
            completed_days,
            session["covered_days"],
            session["question_count"],
        )

    if selected_day is None:

        # Extremely defensive fallback.
        feedback = generate_feedback(
            candidate=candidate,
            history=session["history"],
        )

        session["feedback"] = feedback

        return InterviewResponse(
            reply="Interview complete",
            done=True,
            feedback=feedback,
        )

    # =====================================================
    # GENERATE NEXT QUESTION
    # =====================================================

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
    # Never repeat a question
    # -----------------------------------------------------

    retry_count = 0

    while (
        question_already_asked(
            session,
            next_question,
        )
        and retry_count < 2
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

        retry_count += 1

    # -----------------------------------------------------
    # Absolute fallback if Gemini somehow gives nothing
    # -----------------------------------------------------

    if not next_question:

        objective = (
            selected_day.get(
                "objectives"
            )
            or selected_day.get(
                "title"
            )
            or "this curriculum topic"
        )

        next_question = (
            f"Can you explain what you "
            f"understood about {objective}?"
        )

    # -----------------------------------------------------
    # Store next question
    # -----------------------------------------------------

    session[
        "question_count"
    ] += 1

    session[
        "questions"
    ].append(
        next_question
    )

    day_id = selected_day.get(
        "day"
    )

    # Add day to coverage only once.
    if str(day_id) not in {
        str(day)
        for day in session[
            "covered_days"
        ]
    }:

        session[
            "covered_days"
        ].append(
            day_id
        )

    session[
        "current_question"
    ] = next_question

    session[
        "current_question_day"
    ] = day_id

    # A new curriculum day gets a fresh
    # follow-up opportunity.
    session[
        "follow_up_used"
    ] = False

    # =====================================================
    # NORMAL TURN
    # =====================================================
    #
    # Return the ACTUAL next question.
    # NEVER return reply="".
    # =====================================================

    return InterviewResponse(
        reply=next_question,
        done=False,
    )
    # =========================================================
# TEMPORARY LOCAL TEST HELPER
# =========================================================

def simulate_8_question_interview(
    candidate_id="CAND-003",
    session_id="TEST-SESSION-001",
):
    """
    Temporary local test helper.

    Simulates an interview by:
    1. Starting a new session.
    2. Sending candidate answers repeatedly.
    3. Printing each generated question.
    4. Verifying that the interview reaches done=True.
    5. Printing the final feedback.

    This is NOT a FastAPI endpoint.
    """

    print("\n" + "=" * 60)
    print("STARTING INTERVIEW SIMULATION")
    print("=" * 60)

    # -----------------------------------------------------
    # Start a new interview
    # -----------------------------------------------------

    start_request = InterviewRequest(
        sessionId=session_id,
        candidate={
            "id": candidate_id
        },
    )

    response = interview(start_request)

    print("\nQUESTION 1:")
    print(response.reply)

    if response.done:
        print("ERROR: Interview ended too early.")
        return response

    # -----------------------------------------------------
    # Simulated candidate answers
    # -----------------------------------------------------

    test_answers = [
        "I understand the concept and can explain how it works.",
        "I would apply this concept by following the approach covered in the curriculum.",
        "The main idea is to use the concepts from this topic to solve the given problem.",
        "I would consider the important steps and objectives covered in this curriculum day.",
        "The concept can be applied by following the process described in the topic.",
        "I understand the main principles and how they relate to the objective.",
        "I would use this knowledge when implementing the solution described by the curriculum.",
        "I can explain the concept and its practical application based on what I learned.",
    ]

    # -----------------------------------------------------
    # Send answers
    # -----------------------------------------------------

    for index, answer in enumerate(
        test_answers,
        start=1,
    ):

        print("\n" + "-" * 60)

        print(
            f"SENDING ANSWER {index}:"
        )

        print(answer)

        request = InterviewRequest(
            sessionId=session_id,
            message=answer,
        )

        response = interview(request)

        print(
            f"\nRESPONSE AFTER ANSWER {index}:"
        )

        print(
            f"reply: {response.reply}"
        )

        print(
            f"done: {response.done}"
        )

        # -------------------------------------------------
        # Stop when interview finishes
        # -------------------------------------------------

        if response.done:

            print("\n" + "=" * 60)
            print("INTERVIEW COMPLETED")
            print("=" * 60)

            print(
                "\nFINAL FEEDBACK:"
            )

            print(
                response.feedback
            )

            return response

    # -----------------------------------------------------
    # Verify completion
    # -----------------------------------------------------

    print("\n" + "=" * 60)

    if response.done:

        print(
            "TEST PASSED: done=True"
        )

    else:

        print(
            "TEST FAILED: Interview did not reach done=True."
        )

        session = session_manager.get_session(
            session_id
        )

        if session:

            print(
                f"Questions asked: "
                f"{session.get('question_count', 0)}"
            )

            print(
                f"Curriculum days covered: "
                f"{session.get('covered_days', [])}"
            )

    print("=" * 60)

    return response