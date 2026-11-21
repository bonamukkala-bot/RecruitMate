from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from bson import ObjectId
from utils.db import (
    candidates_collection,
    pipeline_collection,
    jobs_collection
)
from utils.auth_helper import (
    jwt_required,
    get_current_company,
    require_role,
    log_audit_event
)
from utils.retention import purge_expired_candidates

privacy_bp = Blueprint("privacy", __name__)

def _serialize_value(val):
    if isinstance(val, ObjectId):
        return str(val)
    elif isinstance(val, datetime):
        return val.isoformat()
    elif isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_serialize_value(item) for item in val]
    return val

# ── GET /api/privacy/candidates/<candidate_id>/export ─────────────────────────
@privacy_bp.route("/candidates/<candidate_id>/export", methods=["GET"])
@jwt_required
@require_role("admin")
def export_candidate_data(candidate_id: str):
    """
    Returns a comprehensive JSON export of all personal data, scores, interview
    records, consent, and pipeline logs stored for a specific candidate.
    Requires 'admin' role or higher.
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

    # Fetch associated job title
    job = None
    if candidate.get("job_id"):
        try:
            job = jobs_collection.find_one({"_id": ObjectId(candidate["job_id"])})
        except Exception:
            pass

    # Fetch pipeline execution logs
    pipeline_logs = list(pipeline_collection.find({
        "$or": [
            {"candidate_id": str(candidate_id)},
            {"candidate_id": cand_oid}
        ]
    }))

    # Construct clean, comprehensive bundle
    export_bundle = {
        "export_metadata": {
            "candidate_id"    : str(candidate["_id"]),
            "company_id"      : company_id,
            "company_name"    : company.get("company_name", ""),
            "exported_at"     : datetime.now(timezone.utc).isoformat(),
            "exported_by"     : company.get("email", "unknown")
        },
        "profile": {
            "candidate_name"  : candidate.get("candidate_name"),
            "name"            : candidate.get("candidate_name"),
            "candidate_email" : candidate.get("candidate_email"),
            "email"           : candidate.get("candidate_email"),
            "candidate_phone" : candidate.get("candidate_phone"),
            "phone"           : candidate.get("candidate_phone"),
            "status"          : candidate.get("status"),
            "job_id"          : str(candidate.get("job_id", "")),
            "job_title"       : (job.get("job_title") or job.get("title", "")) if job else candidate.get("job_title", ""),
            "created_at"      : _serialize_value(candidate.get("created_at")),
            "updated_at"      : _serialize_value(candidate.get("updated_at"))
        },
        "resume_parse": {
            "resume_text"     : candidate.get("resume_text"),
            "parsed_data"     : _serialize_value(candidate.get("resume_parsed_data")),
            "parsed_skills"   : candidate.get("parsed_skills") or candidate.get("skills", []),
            "experience_years": candidate.get("experience_years")
        },
        "evaluation": {
            "scores"          : _serialize_value(candidate.get("scores")),
            "evaluation"      : _serialize_value(candidate.get("evaluation")),
            "overall_score"   : candidate.get("overall_score"),
            "category_scores" : _serialize_value(candidate.get("category_scores")),
            "scoring_weights" : _serialize_value(candidate.get("scoring_weights_used"))
        },
        "scores": {
            "match_score"     : candidate.get("match_score"),
            "overall_score"   : candidate.get("overall_score")
        },
        "interview": {
            "interview_status": candidate.get("interview_status"),
            "interview_token_exp": _serialize_value(candidate.get("interview_token_exp")),
            "questions"       : candidate.get("interview_questions_final") or candidate.get("interview_questions"),
            "answers"         : _serialize_value(candidate.get("interview_answers")),
            "integrity_log"   : _serialize_value(candidate.get("integrity_log", [])),
            "terminated"      : candidate.get("terminated", False),
            "termination_reason": candidate.get("termination_reason")
        },
        "schedule": {
            "interview_date"  : candidate.get("interview_date"),
            "interview_time"  : candidate.get("interview_time"),
            "scheduled_at"    : _serialize_value(candidate.get("scheduled_at"))
        },
        "consent": {
            "consent_accepted": candidate.get("consent_accepted", False),
            "consented_at"    : _serialize_value(candidate.get("consented_at")),
            "consent_version" : candidate.get("consent_version") or candidate.get("consent_text")
        },
        "pipeline_logs": [_serialize_value(l) for l in pipeline_logs]
    }

    # Audit log access
    log_audit_event(
        company_id=company_id,
        action="privacy.candidate_export",
        target=str(candidate_id),
        candidate_id=str(candidate_id),
        details={"exported_candidate_id": str(candidate_id)}
    )

    return jsonify({
        "success": True,
        "export": export_bundle
    }), 200

# ── POST /api/privacy/purge-expired ───────────────────────────────────────────
@privacy_bp.route("/purge-expired", methods=["POST"])
@jwt_required
@require_role("owner")
def purge_expired_candidates_endpoint():
    """
    Manually triggers a retention purge of expired candidates for the current company.
    Requires 'owner' role.
    Accepts JSON body: {"execute": true} to perform permanent deletion.
    Defaults to dry-run (preview only).
    """
    company = get_current_company()
    company_id = company["company_id"]
    body = request.get_json(silent=True) or {}
    
    # Check both JSON body and query parameters for execute / dry_run
    dry_run_arg = request.args.get("dry_run")
    if dry_run_arg is not None:
        dry_run = dry_run_arg.lower() in ("true", "1")
        execute = not dry_run
    else:
        execute = bool(body.get("execute", False))
        if "dry_run" in body:
            execute = not bool(body.get("dry_run", True))

    res = purge_expired_candidates(company_id=company_id, execute=execute)

    return jsonify(res), 200
