from flask import Blueprint, request, jsonify
from utils.db import jobs_collection
from utils.auth_helper import jwt_required, get_current_company
from utils.file_extractor import extract_text_from_file
from agents.jd_parser import parse_jd
from datetime import datetime, timezone
from bson import ObjectId

jobs_bp = Blueprint("jobs", __name__)

# ── Utility ───────────────────────────────────────────────────────────────────
def serialize_job(job: dict) -> dict:
    job["_id"] = str(job["_id"])
    if isinstance(job.get("created_at"), datetime):
        job["created_at"] = job["created_at"].isoformat()
    if isinstance(job.get("updated_at"), datetime):
        job["updated_at"] = job["updated_at"].isoformat()
    return job

# ── POST /api/jobs/ — Create job (text OR file upload) ───────────────────────
@jobs_bp.route("/", methods=["POST"])
@jwt_required
def create_job():
    company = get_current_company()
    jd_text = None

    # ── Handle file upload (PDF or Word) ─────────────────────────────────────
    if request.content_type and "multipart/form-data" in request.content_type:
        if "jd_file" in request.files:
            file       = request.files["jd_file"]
            extraction = extract_text_from_file(file)
            if not extraction["success"]:
                return jsonify({"success": False, "error": extraction["error"]}), 400
            jd_text = extraction["text"]
        else:
            jd_text = request.form.get("jd_text", "").strip()

    # ── Handle raw JSON ───────────────────────────────────────────────────────
    elif request.is_json:
        body    = request.get_json()
        jd_text = body.get("jd_text", "").strip()

    if not jd_text:
        return jsonify({"success": False, "error": "Provide jd_text or upload a PDF/Word file"}), 400

    # ── Agent 1: Parse JD ─────────────────────────────────────────────────────
    result = parse_jd(jd_text)
    if not result["success"]:
        return jsonify({"success": False, "error": result["error"]}), 500

    now = datetime.now(timezone.utc)

    job_doc = {
        **result["data"],
        "company_id"      : company["company_id"],
        "company_name"    : company["company_name"],
        "raw_jd_text"     : jd_text,
        "status"          : "active",
        "candidates_count": 0,
        "created_at"      : now,
        "updated_at"      : now
    }

    inserted       = jobs_collection.insert_one(job_doc)
    job_doc["_id"] = str(inserted.inserted_id)
    job_doc["created_at"] = now.isoformat()
    job_doc["updated_at"] = now.isoformat()

    return jsonify({
        "success": True,
        "message": "Job created successfully",
        "job_id" : str(inserted.inserted_id),
        "job"    : job_doc
    }), 201

# ── GET /api/jobs/ — List all jobs ───────────────────────────────────────────
@jobs_bp.route("/", methods=["GET"])
@jwt_required
def get_jobs():
    company = get_current_company()
    jobs    = list(
        jobs_collection
        .find({"company_id": company["company_id"]})
        .sort("created_at", -1)
    )
    return jsonify({
        "success": True,
        "jobs"   : [serialize_job(j) for j in jobs],
        "total"  : len(jobs)
    }), 200

# ── GET /api/jobs/<job_id> — Get single job ───────────────────────────────────
@jobs_bp.route("/<job_id>", methods=["GET"])
@jwt_required
def get_job(job_id):
    company = get_current_company()
    try:
        job = jobs_collection.find_one({
            "_id"       : ObjectId(job_id),
            "company_id": company["company_id"]
        })
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404
        return jsonify({"success": True, "job": serialize_job(job)}), 200
    except Exception:
        return jsonify({"success": False, "error": "Invalid job ID"}), 400

# ── PATCH /api/jobs/<job_id>/status — Update job status ──────────────────────
@jobs_bp.route("/<job_id>/status", methods=["PATCH"])
@jwt_required
def update_job_status(job_id):
    company = get_current_company()
    body    = request.get_json()
    status  = body.get("status", "").strip()

    if status not in {"active", "closed"}:
        return jsonify({"success": False, "error": "Status must be 'active' or 'closed'"}), 400

    try:
        result = jobs_collection.update_one(
            {"_id": ObjectId(job_id), "company_id": company["company_id"]},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Job not found"}), 404
        return jsonify({"success": True, "message": f"Job status updated to '{status}'"}), 200
    except Exception:
        return jsonify({"success": False, "error": "Invalid job ID"}), 400

# ── DELETE /api/jobs/<job_id> — Delete job ────────────────────────────────────
@jobs_bp.route("/<job_id>", methods=["DELETE"])
@jwt_required
def delete_job(job_id):
    company = get_current_company()
    try:
        result = jobs_collection.delete_one({
            "_id"       : ObjectId(job_id),
            "company_id": company["company_id"]
        })
        if result.deleted_count == 0:
            return jsonify({"success": False, "error": "Job not found"}), 404
        return jsonify({"success": True, "message": "Job deleted"}), 200
    except Exception:
        return jsonify({"success": False, "error": "Invalid job ID"}), 400
# ── POST /api/jobs/generate-jd — AI generates JD from one line ───────────────
@jobs_bp.route("/generate-jd", methods=["POST"])
@jwt_required
def generate_jd():
    body  = request.get_json()
    brief = body.get("brief", "").strip()

    if not brief:
        return jsonify({"success": False, "error": "Brief description is required"}), 400

    from langchain_groq import ChatGroq
    import os

    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.3-70b-versatile",
        temperature=0.7
    )

    prompt = f"""You are an expert HR professional. Generate a complete, professional job description based on this brief:

BRIEF: {brief}

Write a detailed JD that includes:
- Job title
- Company overview (generic, professional)
- Role overview  
- Key responsibilities (6-8 points)
- Required skills (5-7 skills)
- Nice to have skills
- Experience required
- Qualifications
- What we offer
- Job type and location if mentioned

Make it sound like a real company's JD. Professional, engaging, and detailed.
Return ONLY the job description text, no extra commentary."""

    try:
        response = llm.invoke([
            {"role": "system", "content": "You are an expert HR professional who writes compelling job descriptions."},
            {"role": "user",   "content": prompt}
        ])
        return jsonify({
            "success": True,
            "jd_text": response.content
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
# ── GET /api/jobs/analytics — Dashboard analytics ─────────────────────────────
@jobs_bp.route("/analytics", methods=["GET"])
@jwt_required
def get_analytics():
    company    = get_current_company()
    company_id = company["company_id"]

    from utils.db import candidates_collection, pipeline_collection

    # Jobs stats
    jobs       = list(jobs_collection.find({"company_id": company_id}))
    total_jobs = len(jobs)
    active_jobs= sum(1 for j in jobs if j.get("status") == "active")

    # Candidates stats
    candidates      = list(candidates_collection.find({"company_id": company_id}))
    total_candidates= len(candidates)

    # Pipeline funnel — all counted off the single "status" field, which is the
    # candidate's current pipeline stage (this is the source of truth used
    # everywhere else below too, so every number on this dashboard agrees).
    funnel = {
        "screened"   : sum(1 for c in candidates if c.get("status") == "screened"),
        "shortlisted": sum(1 for c in candidates if c.get("status") == "shortlisted"),
        "invited"    : sum(1 for c in candidates if c.get("status") == "invited"),
        "advance"    : sum(1 for c in candidates if c.get("status") == "advance"),
        "hired"      : sum(1 for c in candidates if c.get("status") == "hired"),
        "rejected"   : sum(1 for c in candidates if c.get("status") == "rejected"),
    }

    # Average match score — check "is not None" rather than truthy, so a
    # candidate who genuinely scored 0 is still counted instead of silently
    # dropped (previously `if c.get("match_score")` treated 0 as "missing").
    scores    = [c.get("match_score", 0) for c in candidates if c.get("match_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Score distribution
    score_dist = {
        "90-100": sum(1 for s in scores if s >= 90),
        "70-89" : sum(1 for s in scores if 70 <= s < 90),
        "50-69" : sum(1 for s in scores if 50 <= s < 70),
        "0-49"  : sum(1 for s in scores if s < 50)
    }

    # Per job stats
    job_stats = []
    for job in jobs:
        job_candidates = [c for c in candidates if c.get("job_id") == str(job["_id"])]
        job_scores     = [c.get("match_score", 0) for c in job_candidates if c.get("match_score") is not None]
        job_stats.append({
            "job_title"      : job.get("job_title", ""),
            "total_candidates": len(job_candidates),
            "avg_score"      : round(sum(job_scores) / len(job_scores), 1) if job_scores else 0,
            # Uses "status" (current pipeline stage) — same field as the funnel
            # above — instead of "recommendation" (the resume screener's
            # initial verdict), so this number can never disagree with the
            # top-level funnel's shortlisted count for the same candidates.
            "shortlisted"    : sum(1 for c in job_candidates if c.get("status") == "shortlisted"),
        })

    # Top skills in demand
    all_skills = []
    for job in jobs:
        all_skills.extend(job.get("required_skills", []))
    skill_count = {}
    for skill in all_skills:
        skill_count[skill] = skill_count.get(skill, 0) + 1
    top_skills = sorted(skill_count.items(), key=lambda x: x[1], reverse=True)[:8]

    # Interview completion rate
    interviewed = sum(1 for c in candidates if c.get("interview_status") == "completed")

    return jsonify({
        "success"         : True,
        "total_jobs"      : total_jobs,
        "active_jobs"     : active_jobs,
        "total_candidates": total_candidates,
        "avg_score"       : avg_score,
        "funnel"          : funnel,
        "score_dist"      : score_dist,
        "job_stats"       : job_stats,
        "top_skills"      : top_skills,
        "interviewed"     : interviewed,
        "pass_rate"       : round((funnel["advance"] + funnel["hired"]) / total_candidates * 100, 1) if total_candidates else 0
    }), 200