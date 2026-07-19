import token

from flask import Blueprint, request, jsonify
from utils.db import candidates_collection, jobs_collection, pipeline_collection
from utils.auth_helper import jwt_required, get_current_company
from agents.email_sender import send_email, send_interview_link_email
from agents.answer_evaluator import evaluate_answers
from agents.ai_interview import start_interview, next_question, close_interview
from agents.scheduler import schedule_next_step
from datetime import datetime, timezone
from bson import ObjectId
import secrets
from datetime import datetime, timezone, timedelta
import os
from agents.email_sender import send_email, send_interview_link_email, send_shortlist_offline_email

pipeline_bp = Blueprint("pipeline", __name__)

# ── Utility: log agent run to pipeline collection ────────────────────────────
def log_pipeline(company_id, candidate_id, job_id, agent, status, result):
    pipeline_collection.insert_one({
        "company_id"  : company_id,
        "candidate_id": candidate_id,
        "job_id"      : job_id,
        "agent"       : agent,
        "status"      : status,
        "result"      : result,
        "ran_at"      : datetime.now(timezone.utc)
    })



# ── POST /api/pipeline/send-email/<candidate_id> — Agent 4 ───────────────────
@pipeline_bp.route("/send-email/<candidate_id>", methods=["POST"])
@jwt_required
def pipeline_send_email(candidate_id):
    company = get_current_company()
    body    = request.get_json() or {}

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404

        # Check if email already sent
        if candidate.get("email_sent"):
            return jsonify({"success": False, "error": "Email already sent to this candidate"}), 400

        result = send_interview_link_email(
            candidate_data=candidate,
            job_data=job,
            company_name=company["company_name"],
            from_email=body.get("from_email", os.getenv("BREVO_SENDER_EMAIL"))
        )

        if result["success"]:
            # Mark email as sent
            candidates_collection.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {
                    "email_sent" : True,
                    "status"     : "shortlisted",
                    "updated_at" : datetime.now(timezone.utc)
                }}
            )
            log_pipeline(company["company_id"], candidate_id,
                        candidate["job_id"], "email_sender", "success", result)

        return jsonify(result), 200 if result["success"] else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── POST /api/pipeline/evaluate/<candidate_id> — Agent 5 ─────────────────────
@pipeline_bp.route("/evaluate/<candidate_id>", methods=["POST"])
@jwt_required
def pipeline_evaluate(candidate_id):
    company = get_current_company()
    body    = request.get_json()

    if not body or "answer_type" not in body or "answers" not in body:
        return jsonify({"success": False, "error": "answer_type and answers are required"}), 400

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        result = evaluate_answers(
            candidate_data=candidate,
            job_data=job,
            answer_type=body["answer_type"],
            answers=body["answers"]
        )

        if result["success"]:
            candidates_collection.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {
                    "evaluation" : result["data"],
                    "status"     : "invited",
                    "updated_at" : datetime.now(timezone.utc)
                }}
            )
            log_pipeline(company["company_id"], candidate_id,
                        candidate["job_id"], "answer_evaluator", "success", result["data"])

        return jsonify(result), 200 if result["success"] else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── POST /api/pipeline/interview/start/<candidate_id> — Agent 6 Start ────────
@pipeline_bp.route("/interview/start/<candidate_id>", methods=["POST"])
@jwt_required
def pipeline_interview_start(candidate_id):
    company = get_current_company()

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        result = start_interview(
            candidate_data=candidate,
            job_data=job,
            company_name=company["company_name"],
            questions=candidate.get("interview_questions", {})
        )

        log_pipeline(company["company_id"], candidate_id,
                    candidate["job_id"], "ai_interviewer_start",
                    "success" if result["success"] else "failed", result)

        return jsonify(result), 200 if result["success"] else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── POST /api/pipeline/interview/next — Agent 6 Next ─────────────────────────
@pipeline_bp.route("/interview/next", methods=["POST"])
@jwt_required
def pipeline_interview_next():
    body = request.get_json()
    required = {"current_question", "candidate_answer"}
    if not body or not required.issubset(body.keys()):
        return jsonify({"success": False, "error": "current_question and candidate_answer required"}), 400

    result = next_question(
        current_question=body["current_question"],
        candidate_answer=body["candidate_answer"],
        next_q=body.get("next_question")
    )
    return jsonify(result), 200 if result["success"] else 500

# ── POST /api/pipeline/interview/close/<candidate_id> — Agent 6 Close ────────
@pipeline_bp.route("/interview/close/<candidate_id>", methods=["POST"])
@jwt_required
def pipeline_interview_close(candidate_id):
    company = get_current_company()

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        result = close_interview(
            candidate_data=candidate,
            job_data=job,
            company_name=company["company_name"],
            total_questions=request.get_json().get("total_questions", 8)
        )

        return jsonify(result), 200 if result["success"] else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── POST /api/pipeline/schedule/<candidate_id> — Agent 7 ─────────────────────
@pipeline_bp.route("/schedule/<candidate_id>", methods=["POST"])
@jwt_required
def pipeline_schedule(candidate_id):
    company = get_current_company()
    body    = request.get_json() or {}

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        eval_data  = candidate.get("evaluation", {})
        role_level = body.get("role_level", "mid")

        result = schedule_next_step(
            candidate_data=candidate,
            job_data=job,
            eval_data=eval_data,
            company_name=company["company_name"],
            role_level=role_level
        )

        if result["success"]:
            candidates_collection.update_one(
                {"_id": ObjectId(candidate_id)},
                {"$set": {
                    "schedule"  : result["data"],
                    "status"    : result["data"]["decision"],
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            log_pipeline(company["company_id"], candidate_id,
                        candidate["job_id"], "scheduler",
                        "success", result["data"])

        return jsonify(result), 200 if result["success"] else 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── GET /api/pipeline/logs/<candidate_id> — Get pipeline audit logs ───────────
@pipeline_bp.route("/logs/<candidate_id>", methods=["GET"])
@jwt_required
def get_pipeline_logs(candidate_id):
    company = get_current_company()

    logs = list(
        pipeline_collection
        .find({
            "candidate_id": candidate_id,
            "company_id"  : company["company_id"]
        })
        .sort("ran_at", -1)
    )

    for log in logs:
        log["_id"]    = str(log["_id"])
        log["ran_at"] = log["ran_at"].isoformat()

    return jsonify({
        "success": True,
        "logs"   : logs,
        "total"  : len(logs)
    }), 200

# ── POST /api/pipeline/interview/create/<candidate_id> ────────────────────────
@pipeline_bp.route("/interview/create/<candidate_id>", methods=["POST"])
@jwt_required
def create_interview_link(candidate_id):
    company = get_current_company()
    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        # Generate unique secure token
        token      = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=3)

        # Build a trimmed 4-question set: intro + top 3 JD-matched (technical) questions
        questions_dict   = candidate.get("interview_questions", {})
        technical_qs     = questions_dict.get("technical", [])[:3]

        intro_question = {
            "id"      : 1,
            "question": "To start, could you introduce yourself and walk me through your background and experience?"
        }

        final_questions = [intro_question]
        for i, q in enumerate(technical_qs, start=2):
            final_questions.append({"id": i, "question": q["question"]})

        candidates_collection.update_one(
            {"_id": ObjectId(candidate_id)},
            {"$set": {
                "interview_token"    : token,
                "interview_token_exp": expires_at,
                "interview_status"   : "pending",
                "status"             : "invited",
                "company_name"       : company["company_name"],
                "interview_questions_final": final_questions,
                "updated_at"         : datetime.now(timezone.utc)
            }}
        )

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        interview_url = f"{frontend_url}/interview/{token}"

        # Auto-send the interview invitation email to the candidate
        email_result = send_interview_link_email(
            candidate_data=candidate,
            job_data=job,
            company_name=company["company_name"],
            interview_url=interview_url,
            from_email=os.getenv("BREVO_SENDER_EMAIL"),
            matched_skills=candidate.get("matched_skills", [])
        )

        return jsonify({
            "success"      : True,
            "interview_url": interview_url,
            "token"        : token,
            "questions"    : final_questions,
            "message"      : "Interview link created",
            "email_sent"   : email_result.get("success", False),
            "email_error"  : email_result.get("error") if not email_result.get("success") else None
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
# ── GET /api/pipeline/interview/public/<token> — No auth needed ───────────────
@pipeline_bp.route("/interview/public/<token>", methods=["GET"])
def get_public_interview(token):
    try:
        candidate = candidates_collection.find_one({"interview_token": token})
        if not candidate:
            return jsonify({"success": False, "error": "Invalid or expired link"}), 404

        exp = candidate.get("interview_token_exp")
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                return jsonify({"success": False, "error": "Interview link expired"}), 400

        if candidate.get("interview_status") == "completed":
            return jsonify({"success": False, "error": "Interview already completed"}), 400

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        # Use the trimmed 4-question set (intro + top 3 JD-matched) saved at link creation.
        # Falls back to the full question set only if the trimmed set is missing
        # (e.g. for candidates whose link was created before this change).
        final_questions = candidate.get("interview_questions_final")
        if not final_questions:
            questions_dict  = candidate.get("interview_questions", {})
            final_questions = (
                questions_dict.get("technical",   []) +
                questions_dict.get("behavioral",  []) +
                questions_dict.get("gap_focused", [])
            )

        return jsonify({
            "success"       : True,
            "candidate_name": candidate["candidate_name"],
            "job_title"     : job["job_title"] if job else "",
            "company_name"  : candidate.get("company_name", "RecruitMate"),
            "questions"     : final_questions,
            "total"         : len(final_questions)
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
# ── POST /api/pipeline/interview/public/<token>/submit ────────────────────────
@pipeline_bp.route("/interview/public/<token>/submit", methods=["POST"])
def submit_public_interview(token):
    try:
        candidate = candidates_collection.find_one({"interview_token": token})
        if not candidate:
            return jsonify({"success": False, "error": "Invalid link"}), 404

        if candidate.get("interview_status") == "completed":
            return jsonify({"success": False, "error": "Already submitted"}), 400

        body     = request.get_json()
        qa_pairs = body.get("qa_pairs", [])

        if not qa_pairs:
            return jsonify({"success": False, "error": "No answers provided"}), 400

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        # ── Agent 5: Auto evaluate ────────────────────────────────────────────
        eval_result = evaluate_answers(
            candidate_data=candidate,
            job_data=job,
            answer_type="speech",
            answers={"qa_pairs": qa_pairs}
        )

        if not eval_result["success"]:
            return jsonify({"success": False, "error": eval_result["error"]}), 500

        eval_data     = eval_result["data"]
        overall_score = eval_data.get("overall_score", 0)

        # ── Agent 7: Auto schedule (kept for reference/next_step text) ────────
        schedule_result = schedule_next_step(
            candidate_data=candidate,
            job_data=job,
            eval_data=eval_data,
            company_name=candidate.get("company_name", "RecruitMate"),
            role_level="junior"
        )
        schedule_data = schedule_result.get("data", {})

        # ── Final auto-decision based on score threshold ──────────────────────
        SHORTLIST_THRESHOLD = 70
        if overall_score >= SHORTLIST_THRESHOLD:
            final_status    = "shortlisted"
            schedule_pending = True
        else:
            final_status    = "rejected"
            schedule_pending = False

        # ── Save everything ───────────────────────────────────────────────────
        candidates_collection.update_one(
            {"interview_token": token},
            {"$set": {
                "interview_status"  : "completed",
                "interview_answers" : qa_pairs,
                "evaluation"        : eval_data,
                "schedule"          : schedule_data,
                "status"            : final_status,
                "schedule_pending"  : schedule_pending,
                "updated_at"        : datetime.now(timezone.utc)
            }}
        )

        log_pipeline(
            candidate["company_id"],
            str(candidate["_id"]),
            candidate["job_id"],
            "voice_interview_complete",
            "success",
            {"score": overall_score, "decision": final_status}
        )

        return jsonify({
            "success"              : True,
            "overall_score"        : overall_score,
            "hiring_recommendation": eval_data.get("hiring_recommendation"),
            "next_step"            : schedule_data.get("next_step", ""),
            "decision"             : final_status,
            "summary"              : eval_data.get("summary", "")
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
# ── POST /api/pipeline/schedule-offline/<candidate_id> ────────────────────────
@pipeline_bp.route("/schedule-offline/<candidate_id>", methods=["POST"])
@jwt_required
def schedule_offline_interview(candidate_id):
    company = get_current_company()
    body    = request.get_json() or {}

    interview_date = body.get("interview_date")
    interview_time = body.get("interview_time")

    if not interview_date or not interview_time:
        return jsonify({"success": False, "error": "interview_date and interview_time are required"}), 400

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

        location = "Charan Solutions Office, Hyderabad"

        email_result = send_shortlist_offline_email(
            candidate_data=candidate,
            job_data=job,
            company_name=company["company_name"],
            interview_date=interview_date,
            interview_time=interview_time,
            location=location,
            from_email=os.getenv("BREVO_SENDER_EMAIL")
        )

        candidates_collection.update_one(
            {"_id": ObjectId(candidate_id)},
            {"$set": {
                "schedule_pending"     : False,
                "offline_interview"    : {
                    "date"    : interview_date,
                    "time"    : interview_time,
                    "location": location
                },
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        log_pipeline(company["company_id"], candidate_id,
                    candidate["job_id"], "offline_schedule", "success", email_result)

        return jsonify({
            "success"   : True,
            "message"   : "Offline interview scheduled and candidate notified",
            "email_sent": email_result.get("success", False),
            "email_error": email_result.get("error") if not email_result.get("success") else None
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500