import re
from datetime import datetime, timezone
from bson import ObjectId

from utils.db import candidates_collection

def derive_required_topics(job_data: dict, final_questions: list[dict]) -> list[str]:
    """
    Derives an ordered list of required skills and topics from the job description
    and the generated core questions for coverage tracking.
    """
    topics = []
    seen = set()

    def _add(t: str):
        cleaned = t.strip()
        if cleaned and len(cleaned) <= 60 and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            topics.append(cleaned)

    # 1. From job skills / requirements
    if job_data:
        skills = job_data.get("skills_required") or job_data.get("matched_skills") or []
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, str):
                    _add(s)

        # Requirements list
        reqs = job_data.get("requirements") or []
        if isinstance(reqs, list):
            for r in reqs[:5]:
                if isinstance(r, str):
                    _add(r)

    # 2. From core questions summary/keywords
    for q in final_questions:
        q_text = q.get("question", "")
        # Heuristic keywords from question text
        for kw in ["Python", "JavaScript", "React", "Node", "SQL", "MongoDB", "System Design", "Architecture", "Communication", "Leadership", "Teamwork"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", q_text, re.IGNORECASE):
                _add(kw)

    if not topics:
        topics = ["Technical Competence", "Problem Solving", "Communication", "Experience Alignment"]

    return topics

def initialize_interview_turns(candidate: dict, job: dict, interview_settings: dict) -> tuple[list[dict], dict]:
    """
    Initializes the interview_turns array and coverage tracker on a candidate record.
    Returns (turns, coverage).
    """
    final_questions = candidate.get("interview_questions_final") or []
    if not final_questions:
        # Fallback to category list if not yet built
        q_dict = candidate.get("interview_questions", {})
        all_qs = (
            q_dict.get("technical", []) +
            q_dict.get("behavioral", []) +
            q_dict.get("gap_focused", [])
        )
        final_questions = [{"id": i + 1, "question": q.get("question", "")} for i, q in enumerate(all_qs)]

    if not final_questions:
        final_questions = [{
            "id": 1,
            "question": "To start, could you introduce yourself and walk me through your background and experience?"
        }]

    now_utc = datetime.now(timezone.utc)
    topics = derive_required_topics(job or {}, final_questions)

    first_turn = {
        "turn_id": "turn_1",
        "parent_turn_id": None,
        "core_question_index": 0,
        "type": "core",
        "question": final_questions[0]["question"],
        "answer": None,
        "asked_at": now_utc,
        "answered_at": None,
        # Internal fields (never sent to candidate)
        "_verdict": None,
        "_score": None,
        "_gaps": [],
        "_decider_reason": "First core question initialized."
    }

    coverage = {
        "required_topics": topics,
        "covered_topics": [topics[0]] if topics else [],
        "current_core_index": 0,
        "follow_ups_on_current": 0,
        "restated_on_current": False,
        "interview_started_at": now_utc
    }

    return [first_turn], coverage

def sanitize_turn_for_candidate(turn: dict | None, progress: dict | None = None) -> dict | None:
    """
    Strips all internal fields (any key starting with '_') so scores, verdicts,
    and internal reasons are never exposed to candidate-facing responses.
    """
    if not turn:
        return None

    sanitized = {
        "turn_id": turn.get("turn_id"),
        "question": turn.get("question"),
        "type": turn.get("type", "core"),
        "parent_turn_id": turn.get("parent_turn_id"),
        "core_question_index": turn.get("core_question_index", 0),
        "asked_at": turn["asked_at"].isoformat() if isinstance(turn.get("asked_at"), datetime) else str(turn.get("asked_at", ""))
    }

    if progress:
        sanitized["progress"] = progress

    return sanitized

def get_active_turn(turns: list[dict]) -> dict | None:
    """
    Returns the first unanswered turn, or None if all turns are answered.
    """
    for t in turns:
        if t.get("answered_at") is None:
            return t
    return None

def process_turn_submission(
    candidate: dict,
    turn_id: str,
    answer: str,
    interview_settings: dict,
    job_data: dict | None = None
) -> tuple[bool, dict | None, dict | None, str | None]:
    """
    Processes an answer submission for a turn.
    Enforces server-side limits:
    - Duration limit (from interview_started_at against duration_minutes)
    - Code question bypass: strictly next_core (no follow-ups)
    - Max follow-ups per question cap (max_follow_ups_per_question)
    - At most 1 restate per question
    - Total core questions cap
    - Idempotency: resubmission of an already-answered turn returns existing next turn.

    Returns:
    (is_finished: bool, next_turn_sanitized: dict | None, progress: dict | None, error: str | None)
    """
    turns = candidate.get("interview_turns", [])
    coverage = candidate.get("interview_coverage") or {}
    final_questions = candidate.get("interview_questions_final") or []
    total_core = len(final_questions) if final_questions else 1

    # Find the target turn
    target_idx = None
    for i, t in enumerate(turns):
        if t.get("turn_id") == turn_id:
            target_idx = i
            break

    if target_idx is None:
        return False, None, None, f"Turn '{turn_id}' not found in interview session."

    target_turn = turns[target_idx]

    # ── Idempotency Check ─────────────────────────────────────────────────────
    if target_turn.get("answered_at") is not None:
        # Already answered. Find and return the subsequent turn if one exists.
        if target_idx + 1 < len(turns):
            next_existing = turns[target_idx + 1]
            active = sanitize_turn_for_candidate(next_existing)
            prog = {
                "current_core": next_existing.get("core_question_index", 0) + 1,
                "total_core": total_core,
                "turns_completed": target_idx + 1,
                "follow_ups_on_current": coverage.get("follow_ups_on_current", 0)
            }
            return False, active, prog, None
        else:
            # Interview finished
            prog = {
                "current_core": total_core,
                "total_core": total_core,
                "turns_completed": len(turns)
            }
            return True, None, prog, None

    now_utc = datetime.now(timezone.utc)

    # ── Server-side Duration Enforcement ──────────────────────────────────────
    started_at = coverage.get("interview_started_at")
    if started_at and isinstance(started_at, str):
        try:
            started_at = datetime.fromisoformat(started_at)
        except Exception:
            started_at = turns[0].get("asked_at")

    if started_at and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    duration_minutes = int(interview_settings.get("duration_minutes", 30))
    time_limit_seconds = duration_minutes * 60

    elapsed_seconds = (now_utc - started_at).total_seconds() if started_at else 0
    is_time_exhausted = elapsed_seconds >= time_limit_seconds

    # Record the answer on the current turn
    target_turn["answer"] = answer.strip() if answer else "(No answer provided)"
    target_turn["answered_at"] = now_utc

    # Update covered topics from current question
    current_core_idx = target_turn.get("core_question_index", 0)
    req_topics = coverage.get("required_topics", [])
    covered = coverage.get("covered_topics", [])
    if req_topics and current_core_idx < len(req_topics):
        topic = req_topics[current_core_idx]
        if topic not in covered:
            covered.append(topic)
    coverage["covered_topics"] = covered

    # Check if time is exhausted
    if is_time_exhausted:
        # Interview completed due to time limit
        candidates_collection.update_one(
            {"_id": candidate["_id"]},
            {"$set": {
                "interview_turns": turns,
                "interview_coverage": coverage,
                "updated_at": now_utc
            }}
        )
        prog = {
            "current_core": current_core_idx + 1,
            "total_core": total_core,
            "turns_completed": len(turns)
        }
        return True, None, prog, None

    # ── Determine Next Turn ───────────────────────────────────────────────────
    follow_up_mode = interview_settings.get("follow_up_mode", "off")
    max_fu_allowed = int(interview_settings.get("max_follow_ups_per_question", 2))
    probe_depth = interview_settings.get("probe_depth", "standard")

    # Decision #2: For code-type questions, bypass adaptive follow-ups and move directly to next_core
    is_code_question = (
        target_turn.get("type") == "code" or
        target_turn.get("question_type") == "code" or
        "code" in target_turn.get("question", "").lower()[:20]
    )

    follow_ups_used = coverage.get("follow_ups_on_current", 0)
    current_type = target_turn.get("type", "core")

    advance_to_next_core = False
    next_turn = None

    if current_type == "wrap_up":
        # Wrap up has been answered. The interview is finished.
        next_turn = None
    elif follow_up_mode == "off":
        advance_to_next_core = True
        target_turn["_decider_reason"] = "Follow-up mode off - advancing sequentially"
    elif is_code_question:
        advance_to_next_core = True
        target_turn["_decider_reason"] = "Code question - bypassed adaptive follow-up"
    elif follow_ups_used >= max_fu_allowed:
        advance_to_next_core = True
        target_turn["_decider_reason"] = f"Max follow-ups reached ({follow_ups_used}/{max_fu_allowed})"
    else:
        # Combined Evaluator + Decider (Phase C)
        from agents.adaptive_decider import evaluate_and_decide_turn

        has_restated = bool(coverage.get("restated_on_current", False))
        decider_res = evaluate_and_decide_turn(
            company_id=candidate.get("company_id"),
            job_data=job_data or {},
            current_question=target_turn.get("question", ""),
            candidate_answer=target_turn.get("answer", ""),
            current_core_index=current_core_idx,
            total_core_questions=total_core,
            follow_ups_used=follow_ups_used,
            max_follow_ups=max_fu_allowed,
            has_restated=has_restated,
            probe_depth=probe_depth,
            required_topics=req_topics,
            covered_topics=coverage.get("covered_topics", []),
            question_type=current_type
        )

        eval_data = decider_res.get("evaluation", {})
        dec_data = decider_res.get("decision", {})

        target_turn["_verdict"] = eval_data.get("verdict")
        target_turn["_score"] = eval_data.get("score")
        target_turn["_gaps"] = eval_data.get("missing", [])
        target_turn["_decider_reason"] = dec_data.get("reason", "")

        # Incorporate newly covered topics
        for cov in eval_data.get("covered", []):
            if cov and cov not in coverage.get("covered_topics", []):
                coverage["covered_topics"].append(cov)

        action = dec_data.get("action", "next_core")
        follow_up_q = dec_data.get("follow_up_question")

        if action in ("probe_deeper", "probe_gap", "easier"):
            coverage["follow_ups_on_current"] = follow_ups_used + 1
            next_turn = {
                "turn_id": f"turn_{len(turns) + 1}",
                "parent_turn_id": target_turn.get("turn_id"),
                "core_question_index": current_core_idx,
                "type": action,
                "question": follow_up_q,
                "answer": None,
                "asked_at": now_utc,
                "answered_at": None,
                "_verdict": None,
                "_score": None,
                "_gaps": [],
                "_decider_reason": dec_data.get("reason", "")
            }
        elif action == "restate":
            coverage["follow_ups_on_current"] = follow_ups_used + 1
            coverage["restated_on_current"] = True
            next_turn = {
                "turn_id": f"turn_{len(turns) + 1}",
                "parent_turn_id": target_turn.get("turn_id"),
                "core_question_index": current_core_idx,
                "type": "restate",
                "question": follow_up_q,
                "answer": None,
                "asked_at": now_utc,
                "answered_at": None,
                "_verdict": None,
                "_score": None,
                "_gaps": [],
                "_decider_reason": dec_data.get("reason", "")
            }
        else:
            # "next_core" or "wrap_up"
            advance_to_next_core = True

    if advance_to_next_core:
        next_core_idx = current_core_idx + 1
        if next_core_idx < total_core and next_core_idx < len(final_questions):
            # Advance to next core question
            coverage["current_core_index"] = next_core_idx
            coverage["follow_ups_on_current"] = 0
            coverage["restated_on_current"] = False

            next_q_text = final_questions[next_core_idx].get("question", "")
            next_turn = {
                "turn_id": f"turn_{len(turns) + 1}",
                "parent_turn_id": None,
                "core_question_index": next_core_idx,
                "type": "core",
                "question": next_q_text,
                "answer": None,
                "asked_at": now_utc,
                "answered_at": None,
                "_verdict": None,
                "_score": None,
                "_gaps": [],
                "_decider_reason": f"Advanced to core question #{next_core_idx + 1}"
            }
        else:
            # All core questions completed. Check wrap-up.
            if current_type != "wrap_up":
                wrap_up_turn = {
                    "turn_id": f"turn_{len(turns) + 1}",
                    "parent_turn_id": None,
                    "core_question_index": total_core - 1,
                    "type": "wrap_up",
                    "question": "Is there anything else you'd like to share or highlight about your background before we conclude?",
                    "answer": None,
                    "asked_at": now_utc,
                    "answered_at": None,
                    "_verdict": None,
                    "_score": None,
                    "_gaps": [],
                    "_decider_reason": "Wrap-up question"
                }
                next_turn = wrap_up_turn
            else:
                next_turn = None

    if next_turn:
        turns.append(next_turn)

    # Persist updated transcript and coverage to MongoDB
    candidates_collection.update_one(
        {"_id": candidate["_id"]},
        {"$set": {
            "interview_turns": turns,
            "interview_coverage": coverage,
            "updated_at": now_utc
        }}
    )

    is_finished = next_turn is None
    prog = {
        "current_core": (coverage.get("current_core_index", 0) + 1) if not is_finished else total_core,
        "total_core": total_core,
        "turns_completed": len([t for t in turns if t.get("answered_at") is not None]),
        "follow_ups_on_current": coverage.get("follow_ups_on_current", 0)
    }

    sanitized = sanitize_turn_for_candidate(next_turn, prog) if next_turn else None
    return is_finished, sanitized, prog, None
