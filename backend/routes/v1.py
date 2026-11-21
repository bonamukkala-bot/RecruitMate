from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
from bson import ObjectId

from utils.api_keys import api_key_required
from utils.db import jobs_collection, candidates_collection
from utils.webhook_dispatcher import dispatch_webhook_event
from utils.slack import send_slack_notification

v1_bp = Blueprint("v1", __name__)

# ── GET /api/v1/jobs — List jobs ──────────────────────────────────────────────
@v1_bp.route("/jobs", methods=["GET"])
@api_key_required(required_scope="write:jobs")
def v1_list_jobs():
    """List open jobs for the authenticated company."""
    company_id = g.company_id
    jobs = list(jobs_collection.find({"company_id": company_id}))

    results = []
    for j in jobs:
        results.append({
            "id": str(j["_id"]),
            "title": j.get("job_title") or j.get("title", ""),
            "department": j.get("department", ""),
            "location": j.get("location", ""),
            "status": j.get("status", "open"),
            "created_at": j.get("created_at").isoformat() if isinstance(j.get("created_at"), datetime) else str(j.get("created_at", ""))
        })

    return jsonify({"success": True, "jobs": results}), 200

# ── POST /api/v1/candidates — Ingest/Create candidate ─────────────────────────
@v1_bp.route("/candidates", methods=["POST"])
@api_key_required(required_scope="read:candidates")
def v1_create_candidate():
    """Create a new candidate application via public API."""
    company_id = g.company_id
    data = request.get_json(silent=True) or {}

    job_id = data.get("job_id")
    if not job_id:
        return jsonify({"success": False, "error": "job_id is required"}), 400

    try:
        job = jobs_collection.find_one({"_id": ObjectId(job_id), "company_id": company_id})
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404
    except Exception:
        return jsonify({"success": False, "error": "Invalid job_id"}), 400

    candidate_name = (data.get("candidate_name") or data.get("name") or "").strip()
    if not candidate_name:
        return jsonify({"success": False, "error": "candidate_name is required"}), 400

    candidate_email = (data.get("candidate_email") or data.get("email") or "").strip().lower()
    if not candidate_email or "@" not in candidate_email:
        return jsonify({"success": False, "error": "Valid candidate_email is required"}), 400

    candidate_phone = (data.get("candidate_phone") or data.get("phone") or "").strip()
    resume_text = data.get("resume_text", "")

    now_utc = datetime.now(timezone.utc)
    new_candidate = {
        "company_id": company_id,
        "job_id": str(job["_id"]),
        "job_title": job.get("job_title") or job.get("title", ""),
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "candidate_phone": candidate_phone,
        "resume_text": resume_text,
        "status": "applied",
        "created_at": now_utc,
        "source": "api_v1"
    }

    result = candidates_collection.insert_one(new_candidate)
    candidate_id = str(result.inserted_id)

    # Dispatch webhooks & Slack in non-blocking fashion
    webhook_payload = {
        "event": "candidate.created",
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "job_id": str(job["_id"]),
        "job_title": job.get("job_title") or job.get("title", ""),
        "created_at": now_utc.isoformat()
    }
    dispatch_webhook_event(company_id, "candidate.created", webhook_payload)
    send_slack_notification(company_id, "new_candidate", {
        "candidate_name": candidate_name,
        "job_title": job.get("job_title") or job.get("title", ""),
        "match_score": "Pending"
    })

    return jsonify({
        "success": True,
        "candidate_id": candidate_id,
        "message": "Candidate created successfully"
    }), 201
