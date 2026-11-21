from flask import Blueprint, request, jsonify
from utils.db import candidates_collection, jobs_collection, audit_logs_collection, pipeline_collection
from utils.auth_helper import jwt_required, get_current_company, require_role, log_audit_event
from utils.file_extractor import extract_text_from_file
from agents.resume_screener import screen_resume
from agents.question_generator import generate_questions
from agents.email_sender import send_rejection_email, send_owner_notification
from agents.candidate_comparator import compare_candidates
from utils.webhook_dispatcher import dispatch_webhook_event
from utils.slack import send_slack_notification
from datetime import datetime, timezone
from bson import ObjectId
import os
import csv
import io
from flask import Response

candidates_bp = Blueprint("candidates", __name__)

# ── Score threshold used at the resume-screening stage ────────────────────────
SCREEN_REJECT_THRESHOLD = 70

# ── Utility: serialize MongoDB doc ───────────────────────────────────────────
def serialize_candidate(candidate: dict) -> dict:
    candidate["_id"]        = str(candidate["_id"])
    candidate["job_id"]     = str(candidate.get("job_id", ""))
    candidate["company_id"] = str(candidate.get("company_id", ""))
    if isinstance(candidate.get("created_at"), datetime):
        candidate["created_at"] = candidate["created_at"].isoformat()
    if isinstance(candidate.get("updated_at"), datetime):
        candidate["updated_at"] = candidate["updated_at"].isoformat()
    if "interview_turns" in candidate and isinstance(candidate["interview_turns"], list):
        for turn in candidate["interview_turns"]:
            if isinstance(turn.get("asked_at"), datetime):
                turn["asked_at"] = turn["asked_at"].isoformat()
            if isinstance(turn.get("answered_at"), datetime):
                turn["answered_at"] = turn["answered_at"].isoformat()
    return candidate

# ── GET /api/candidates/ — Get ALL candidates for company ─────────────────────
@candidates_bp.route("/", methods=["GET"])
@jwt_required
def get_all_candidates():
    company = get_current_company()

    candidates = list(
        candidates_collection
        .find({"company_id": company["company_id"]})
        .sort("created_at", -1)
    )

    # Attach job title to each candidate
    for c in candidates:
        try:
            job = jobs_collection.find_one({"_id": ObjectId(c["job_id"])})
            c["job_title"] = job["job_title"] if job else "Unknown"
        except:
            c["job_title"] = "Unknown"

    return jsonify({
        "success"   : True,
        "candidates": [serialize_candidate(c) for c in candidates],
        "total"     : len(candidates)
    }), 200

# ── POST /api/candidates/<job_id>/screen — Screen via text ───────────────────
@candidates_bp.route("/<job_id>/screen", methods=["POST"])
@jwt_required
@require_role("recruiter")
def screen_candidate(job_id):
    company = get_current_company()

    try:
        job = jobs_collection.find_one({
            "_id"       : ObjectId(job_id),
            "company_id": company["company_id"]
        })
    except Exception:
        return jsonify({"success": False, "error": "Invalid job ID"}), 400

    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    # ── Handle file upload OR raw JSON ───────────────────────────────────────
    resume_text     = None
    candidate_name  = ""
    candidate_email = ""

    if request.content_type and "multipart/form-data" in request.content_type:
        candidate_name  = request.form.get("candidate_name", "").strip()
        candidate_email = request.form.get("candidate_email", "").strip()

        if "resume_file" in request.files:
            file       = request.files["resume_file"]
            extraction = extract_text_from_file(file)
            if not extraction["success"]:
                return jsonify({"success": False, "error": extraction["error"]}), 400
            resume_text = extraction["text"]
        else:
            resume_text = request.form.get("resume_text", "").strip()
    else:
        body            = request.get_json() or {}
        candidate_name  = body.get("candidate_name", "").strip()
        candidate_email = body.get("candidate_email", "").strip()
        resume_text     = body.get("resume_text", "").strip()

    if not resume_text:
        return jsonify({"success": False, "error": "Resume text or file is required"}), 400
    if not candidate_name:
        return jsonify({"success": False, "error": "candidate_name is required"}), 400

    # ── Agent 2: Screen resume ────────────────────────────────────────────────
    from utils.settings import get_settings
    hiring_settings = get_settings(company["company_id"]).get("hiring", {})

    # Per-job scoring_weights override:
    # If job has use_company_weights is False and job has scoring_weights, use job scoring_weights
    if job.get("use_company_weights") is False and job.get("scoring_weights"):
        scoring_weights = job.get("scoring_weights")
    else:
        scoring_weights = hiring_settings.get("scoring_weights")

    screen_result = screen_resume(resume_text, job, scoring_weights=scoring_weights)
    if not screen_result["success"]:
        return jsonify({"success": False, "error": screen_result["error"]}), 500

    screen_data  = screen_result["data"]
    match_score  = screen_data.get("match_score", 0)
    now          = datetime.now(timezone.utc)

    auto_reject_requires_approval = bool(
        hiring_settings.get("approval_mode", {}).get("auto_reject_requires_approval", False)
    )

    # ── Auto-reject at resume-screening stage if below threshold ──────────────
    if match_score < SCREEN_REJECT_THRESHOLD:
        status = "pending_review" if auto_reject_requires_approval else "rejected"
        candidate_doc = {
            "company_id"          : company["company_id"],
            "job_id"              : job_id,
            "job_title"           : job.get("job_title", ""),
            "candidate_name"      : candidate_name,
            "candidate_email"     : candidate_email,
            "match_score"         : match_score,
            "matched_skills"      : screen_data.get("matched_skills", []),
            "missing_skills"      : screen_data.get("missing_skills", []),
            "experience_match"    : screen_data.get("experience_match", False),
            "recommendation"      : screen_data.get("recommendation", ""),
            "reasoning"           : screen_data.get("reasoning", ""),
            "interview_questions" : {},
            "status"              : status,
            "recommended_decision": "reject",
            "review_reason"       : f"Resume screening score {match_score} is below threshold {SCREEN_REJECT_THRESHOLD}",
            "email_sent"          : False,
            "resume_text"         : resume_text,
            "evaluation"          : None,
            "schedule"            : None,
            "created_at"          : now,
            "updated_at"          : now
        }

        inserted = candidates_collection.insert_one(candidate_doc)

        jobs_collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$inc": {"candidates_count": 1}}
        )

        candidate_doc["_id"]        = str(inserted.inserted_id)
        candidate_doc["created_at"] = now.isoformat()
        candidate_doc["updated_at"] = now.isoformat()

        if auto_reject_requires_approval:
            send_owner_notification(company["company_id"], "pending_review", {
                "candidate_name": candidate_name,
                "job_title": job.get("job_title", ""),
                "reason": candidate_doc.get("review_reason", "")
            })
            send_slack_notification(company["company_id"], "pending_review", {
                "candidate_name": candidate_name,
                "job_title": job.get("job_title", "")
            })
            dispatch_webhook_event(company["company_id"], "candidate.pending_review", {
                "event": "candidate.pending_review",
                "candidate_id": str(inserted.inserted_id),
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "job_id": str(job["_id"]),
                "job_title": job.get("job_title", ""),
                "review_reason": candidate_doc.get("review_reason", "")
            })
            return jsonify({
                "success"       : True,
                "message"       : "Candidate requires review before rejection",
                "candidate_id"  : str(inserted.inserted_id),
                "candidate"     : candidate_doc,
                "pending_review": True
            }), 201

        email_result = send_rejection_email(
            candidate_data=candidate_doc,
            job_data=job,
            company_name=company["company_name"],
            from_email=os.getenv("BREVO_SENDER_EMAIL"),
            stage="resume screening"
        )

        candidates_collection.update_one(
            {"_id": inserted.inserted_id},
            {"$set": {"email_sent": email_result.get("success", False)}}
        )

        candidate_doc["email_sent"] = email_result.get("success", False)

        send_owner_notification(company["company_id"], "new_candidate", {
            "candidate_name": candidate_name,
            "job_title": job.get("job_title", ""),
            "match_score": match_score
        })
        send_slack_notification(company["company_id"], "new_candidate", {
            "candidate_name": candidate_name,
            "job_title": job.get("job_title", ""),
            "match_score": match_score
        })
        dispatch_webhook_event(company["company_id"], "candidate.created", {
            "event": "candidate.created",
            "candidate_id": str(inserted.inserted_id),
            "candidate_name": candidate_name,
            "candidate_email": candidate_email,
            "job_id": str(job["_id"]),
            "job_title": job.get("job_title", ""),
            "status": status,
            "match_score": match_score
        })

        return jsonify({
            "success"     : True,
            "message"     : "Candidate did not meet the match threshold — auto-rejected",
            "candidate_id": str(inserted.inserted_id),
            "candidate"   : candidate_doc,
            "email_sent"  : email_result.get("success", False),
            "email_error" : email_result.get("error") if not email_result.get("success") else None
        }), 201

    # ── Score >= threshold: continue existing flow (generate questions etc.) ──

    # ── Agent 3: Generate questions ───────────────────────────────────────────
    candidate_data   = {"candidate_name": candidate_name, "candidate_email": candidate_email}
    interview_settings = hiring_settings.get("interview") if "interview" in hiring_settings else get_settings(company["company_id"]).get("interview", {})

    if job.get("use_company_interview_settings") is False:
        q_count = job.get("question_count") or interview_settings.get("question_count", 8)
        diff    = job.get("difficulty") or interview_settings.get("difficulty", "medium")
    else:
        q_count = interview_settings.get("question_count", 8)
        diff    = interview_settings.get("difficulty", "medium")

    q_types = interview_settings.get("question_types", "mixed")

    questions_result = generate_questions(
        candidate_data=candidate_data,
        job_data=job,
        screen_data=screen_data,
        question_count=q_count,
        difficulty=diff,
        question_types=q_types
    )
    questions        = questions_result.get("data", {}).get("questions", {})

    candidate_doc = {
        "company_id"         : company["company_id"],
        "job_id"             : job_id,
        "job_title"          : job.get("job_title", ""),
        "candidate_name"     : candidate_name,
        "candidate_email"    : candidate_email,
        "match_score"        : match_score,
        "matched_skills"     : screen_data.get("matched_skills", []),
        "missing_skills"     : screen_data.get("missing_skills", []),
        "experience_match"   : screen_data.get("experience_match", False),
        "recommendation"     : screen_data.get("recommendation", ""),
        "reasoning"          : screen_data.get("reasoning", ""),
        "interview_questions": questions,
        "status"             : "screened",
        "email_sent"         : False,
        "resume_text"        : resume_text,
        "evaluation"         : None,
        "schedule"           : None,
        "created_at"         : now,
        "updated_at"         : now
    }

    inserted = candidates_collection.insert_one(candidate_doc)

    jobs_collection.update_one(
        {"_id": ObjectId(job_id)},
        {"$inc": {"candidates_count": 1}}
    )

    candidate_doc["_id"]        = str(inserted.inserted_id)
    candidate_doc["created_at"] = now.isoformat()
    candidate_doc["updated_at"] = now.isoformat()

    send_owner_notification(company["company_id"], "new_candidate", {
        "candidate_name": candidate_name,
        "job_title": job.get("job_title", ""),
        "match_score": match_score
    })

    return jsonify({
        "success"     : True,
        "message"     : "Candidate screened successfully",
        "candidate_id": str(inserted.inserted_id),
        "candidate"   : candidate_doc
    }), 201

# ── Utility: build a Mongo filter dict from query params ─────────────────────
def _build_search_filter(company_id, args):
    query = {"company_id": company_id}

    skill = args.get("skill", "").strip()
    if skill:
        # case-insensitive partial match against matched_skills array
        query["matched_skills"] = {"$regex": skill, "$options": "i"}

    status = args.get("status", "").strip()
    if status:
        query["status"] = status

    min_score = args.get("min_score", "").strip()
    max_score = args.get("max_score", "").strip()
    if min_score or max_score:
        score_filter = {}
        if min_score:
            try:
                score_filter["$gte"] = float(min_score)
            except ValueError:
                pass
        if max_score:
            try:
                score_filter["$lte"] = float(max_score)
            except ValueError:
                pass
        if score_filter:
            query["match_score"] = score_filter

    date_from = args.get("date_from", "").strip()
    date_to   = args.get("date_to", "").strip()
    if date_from or date_to:
        date_filter = {}
        if date_from:
            try:
                date_filter["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        if date_to:
            try:
                # include the whole day for date_to
                dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                date_filter["$lte"] = dt.replace(hour=23, minute=59, second=59)
            except ValueError:
                pass
        if date_filter:
            query["created_at"] = date_filter

    return query

# ── GET /api/candidates/search — Smart search with filters ───────────────────
@candidates_bp.route("/search", methods=["GET"])
@jwt_required
def search_candidates():
    company = get_current_company()
    query   = _build_search_filter(company["company_id"], request.args)

    candidates = list(
        candidates_collection
        .find(query)
        .sort("match_score", -1)
    )

    for c in candidates:
        try:
            job = jobs_collection.find_one({"_id": ObjectId(c["job_id"])})
            c["job_title"] = job["job_title"] if job else c.get("job_title", "Unknown")
        except Exception:
            c["job_title"] = c.get("job_title", "Unknown")

    return jsonify({
        "success"   : True,
        "candidates": [serialize_candidate(c) for c in candidates],
        "total"     : len(candidates)
    }), 200

# ── GET /api/candidates/export — CSV export with same filters ────────────────
@candidates_bp.route("/export", methods=["GET"])
@jwt_required
def export_candidates():
    company = get_current_company()
    query   = _build_search_filter(company["company_id"], request.args)

    candidates = list(
        candidates_collection
        .find(query)
        .sort("match_score", -1)
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Candidate Name", "Email", "Job Title", "Match Score",
        "Status", "Matched Skills", "Missing Skills", "Created At"
    ])

    for c in candidates:
        try:
            job = jobs_collection.find_one({"_id": ObjectId(c["job_id"])})
            job_title = job["job_title"] if job else c.get("job_title", "Unknown")
        except Exception:
            job_title = c.get("job_title", "Unknown")

        created_at = c.get("created_at")
        created_at_str = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")

        writer.writerow([
            c.get("candidate_name", ""),
            c.get("candidate_email", ""),
            job_title,
            c.get("match_score", 0),
            c.get("status", ""),
            "; ".join(c.get("matched_skills", [])),
            "; ".join(c.get("missing_skills", [])),
            created_at_str
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidates_export.csv"}
    )

# ── POST /api/candidates/compare — Candidate Comparison Tool ─────────────────
@candidates_bp.route("/compare", methods=["POST"])
@jwt_required
@require_role("recruiter")
def compare_candidates_route():
    company = get_current_company()
    body    = request.get_json() or {}

    candidate_ids = body.get("candidate_ids", [])

    if not isinstance(candidate_ids, list) or len(candidate_ids) < 2:
        return jsonify({"success": False, "error": "Provide at least 2 candidate_ids to compare"}), 400
    if len(candidate_ids) > 3:
        return jsonify({"success": False, "error": "A maximum of 3 candidates can be compared at once"}), 400

    try:
        candidates = []
        job_id     = None

        for cid in candidate_ids:
            candidate = candidates_collection.find_one({
                "_id"       : ObjectId(cid),
                "company_id": company["company_id"]
            })
            if not candidate:
                return jsonify({"success": False, "error": f"Candidate {cid} not found"}), 404

            candidate["_id"] = str(candidate["_id"])
            candidates.append(candidate)

            # All candidates being compared should be for the same job
            if job_id is None:
                job_id = candidate.get("job_id")
            elif candidate.get("job_id") != job_id:
                return jsonify({
                    "success": False,
                    "error"  : "All candidates being compared must be for the same job"
                }), 400

        job = jobs_collection.find_one({"_id": ObjectId(job_id)}) if job_id else {}

        result = compare_candidates(candidates, job or {})

        if not result["success"]:
            return jsonify(result), 500

        # Attach basic candidate summary info so the frontend doesn't need a second fetch
        summary = [
            {
                "_id"            : c["_id"],
                "candidate_name" : c.get("candidate_name"),
                "candidate_email": c.get("candidate_email"),
                "match_score"    : c.get("match_score", 0),
                "matched_skills" : c.get("matched_skills", []),
                "missing_skills" : c.get("missing_skills", []),
                "status"         : c.get("status"),
                "interview_score": (c.get("evaluation") or {}).get("overall_score")
            }
            for c in candidates
        ]

        return jsonify({
            "success"   : True,
            "job_title" : job.get("job_title", "") if job else "",
            "candidates": summary,
            "comparison": result["data"]
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── GET /api/candidates/<job_id> — List candidates for a job ─────────────────
@candidates_bp.route("/<job_id>", methods=["GET"])
@jwt_required
def get_candidates(job_id):
    company = get_current_company()

    candidates = list(
        candidates_collection
        .find({
            "job_id"    : job_id,
            "company_id": company["company_id"]
        })
        .sort("match_score", -1)
    )

    return jsonify({
        "success"   : True,
        "candidates": [serialize_candidate(c) for c in candidates],
        "total"     : len(candidates)
    }), 200

# ── GET /api/candidates/detail/<candidate_id> — Get single candidate ──────────
@candidates_bp.route("/detail/<candidate_id>", methods=["GET"])
@jwt_required
def get_candidate(candidate_id):
    company = get_current_company()
    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        return jsonify({"success": True, "candidate": serialize_candidate(candidate)}), 200
    except Exception:
        return jsonify({"success": False, "error": "Invalid candidate ID"}), 400

# ── PATCH /api/candidates/detail/<candidate_id>/status ───────────────────────
@candidates_bp.route("/detail/<candidate_id>/status", methods=["PATCH"])
@jwt_required
@require_role("recruiter")
def update_status(candidate_id):
    company = get_current_company()
    body    = request.get_json()
    status  = body.get("status", "").strip()

    valid_statuses = {"screened", "shortlisted", "invited", "hired", "rejected", "pending_review", "advance"}
    if status not in valid_statuses:
        return jsonify({"success": False, "error": f"Invalid status. Must be one of {valid_statuses}"}), 400

    try:
        candidate = candidates_collection.find_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if not candidate:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        result = candidates_collection.update_one(
            {"_id": ObjectId(candidate_id), "company_id": company["company_id"]},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        log_audit_event(
            company_id=company["company_id"],
            action="candidate.status_change",
            target=candidate_id,
            details={"status": status}
        )

        email_sent  = False
        email_error = None

        # ── Manual rejection: send rejection email too ────────────────────────
        if status == "rejected" and candidate.get("status") != "rejected":
            job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})

            # Was this candidate already interviewed, or just resume-screened?
            stage = "interview" if candidate.get("interview_status") == "completed" else "resume screening"

            email_result = send_rejection_email(
                candidate_data=candidate,
                job_data=job,
                company_name=company["company_name"],
                from_email=os.getenv("BREVO_SENDER_EMAIL"),
                stage=stage
            )
            email_sent  = email_result.get("success", False)
            email_error = email_result.get("error") if not email_sent else None

        return jsonify({
            "success"    : True,
            "message"    : f"Status updated to '{status}'",
            "email_sent" : email_sent,
            "email_error": email_error
        }), 200
    except Exception:
        return jsonify({"success": False, "error": "Invalid candidate ID"}), 400

# ── POST /api/candidates/detail/<candidate_id>/review/approve ─────────────────
@candidates_bp.route("/detail/<candidate_id>/review/approve", methods=["POST"])
@jwt_required
@require_role("admin")
def approve_candidate_review(candidate_id):
    company = get_current_company()
    try:
        cand_oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid candidate ID"}), 400

    candidate = candidates_collection.find_one({
        "_id"       : cand_oid,
        "company_id": company["company_id"]
    })
    if not candidate:
        return jsonify({"success": False, "error": "Candidate not found"}), 404

    now = datetime.now(timezone.utc)
    candidates_collection.update_one(
        {"_id": cand_oid},
        {"$set": {
            "status"     : "rejected",
            "reviewed_at": now,
            "reviewed_by": company.get("email"),
            "updated_at" : now
        }}
    )

    # Send rejection email
    job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])}) if candidate.get("job_id") else None
    stage = "interview" if candidate.get("interview_status") == "completed" else "resume screening"
    email_result = send_rejection_email(
        candidate_data=candidate,
        job_data=job,
        company_name=company["company_name"],
        from_email=os.getenv("BREVO_SENDER_EMAIL"),
        stage=stage
    )

    # Log audit entry
    log_audit_event(
        company_id=company["company_id"],
        action="candidate_review_approve",
        target=candidate_id,
        candidate_id=candidate_id,
        details={
            "previous_status": candidate.get("status"),
            "new_status"     : "rejected",
            "email_sent"     : email_result.get("success", False)
        }
    )

    updated_candidate = candidates_collection.find_one({"_id": cand_oid})
    return jsonify({
        "success"   : True,
        "message"   : "Candidate rejection approved",
        "candidate" : serialize_candidate(updated_candidate),
        "email_sent": email_result.get("success", False)
    }), 200

# ── POST /api/candidates/detail/<candidate_id>/review/override ────────────────
@candidates_bp.route("/detail/<candidate_id>/review/override", methods=["POST"])
@jwt_required
@require_role("admin")
def override_candidate_review(candidate_id):
    company = get_current_company()
    body    = request.get_json(silent=True) or {}
    try:
        cand_oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid candidate ID"}), 400

    candidate = candidates_collection.find_one({
        "_id"       : cand_oid,
        "company_id": company["company_id"]
    })
    if not candidate:
        return jsonify({"success": False, "error": "Candidate not found"}), 404

    target_status = body.get("status") or body.get("target_status") or "shortlisted"
    valid_statuses = {"screened", "shortlisted", "invited", "advance", "hired"}
    if target_status not in valid_statuses:
        target_status = "shortlisted"

    reason = (body.get("reason") or "").strip()
    now    = datetime.now(timezone.utc)

    candidates_collection.update_one(
        {"_id": cand_oid},
        {"$set": {
            "status"         : target_status,
            "reviewed_at"    : now,
            "reviewed_by"    : company.get("email"),
            "override_reason": reason,
            "updated_at"     : now
        }}
    )

    # Log audit entry
    log_audit_event(
        company_id=company["company_id"],
        action="candidate_review_override",
        target=candidate_id,
        candidate_id=candidate_id,
        details={
            "previous_status": candidate.get("status"),
            "new_status"     : target_status,
            "reason"         : reason
        }
    )

    updated_candidate = candidates_collection.find_one({"_id": cand_oid})
    return jsonify({
        "success"  : True,
        "message"  : f"Candidate rejection overridden to '{target_status}'",
        "candidate": serialize_candidate(updated_candidate)
    }), 200

# ── DELETE /api/candidates/detail/<candidate_id> ─────────────────────────────
@candidates_bp.route("/detail/<candidate_id>", methods=["DELETE"])
@jwt_required
@require_role("owner")
def delete_candidate(candidate_id):
    company = get_current_company()
    try:
        result = candidates_collection.delete_one({
            "_id"       : ObjectId(candidate_id),
            "company_id": company["company_id"]
        })
        if result.deleted_count == 0:
            return jsonify({"success": False, "error": "Candidate not found"}), 404

        log_audit_event(
            company_id=company["company_id"],
            action="candidate.delete",
            target=candidate_id
        )

        return jsonify({"success": True, "message": "Candidate deleted"}), 200
    except Exception:
        return jsonify({"success": False, "error": "Invalid candidate ID"}), 400

# ── DELETE /api/candidates/<candidate_id>/data — Hard delete all data ─────────
@candidates_bp.route("/<candidate_id>/data", methods=["DELETE"])
@candidates_bp.route("/detail/<candidate_id>/data", methods=["DELETE"])
@jwt_required
@require_role("admin")
def hard_delete_candidate_data(candidate_id: str):
    """
    Hard-deletes candidate and all related records (evaluations, interview events,
    schedule, files, pipeline logs).
    Owner/admin only.
    Audit-logged: stores only candidate_id and SHA-256 hash of email, not personal data.
    """
    company = get_current_company()
    company_id = company["company_id"]

    try:
        cand_oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid candidate ID"}), 400

    candidate = candidates_collection.find_one({
        "_id": cand_oid,
        "company_id": company_id
    })
    if not candidate:
        return jsonify({"success": False, "error": "Candidate not found"}), 404

    # Compute privacy-safe hash of email
    import hashlib
    raw_email = (candidate.get("candidate_email") or "").strip().lower()
    email_hash = hashlib.sha256(raw_email.encode("utf-8")).hexdigest() if raw_email else ""

    # Delete pipeline logs
    pipeline_collection.delete_many({
        "$or": [{"candidate_id": str(candidate_id)}, {"candidate_id": cand_oid}]
    })

    # Delete candidate record
    candidates_collection.delete_one({"_id": cand_oid})

    # Audit log entry storing ONLY candidate_id and email_hash (no raw PII)
    log_audit_event(
        company_id=company_id,
        action="candidate.hard_delete",
        target={
            "candidate_id": str(candidate_id),
            "email_hash": email_hash
        },
        candidate_id=str(candidate_id),
        email_hash=email_hash,
        details={"status": "hard_deleted", "email_hash": email_hash}
    )

    return jsonify({
        "success": True,
        "message": "Candidate and all associated data permanently deleted"
    }), 200
