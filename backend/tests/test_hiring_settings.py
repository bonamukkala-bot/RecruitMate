import pytest
import os
import sys
from datetime import datetime, timezone
from bson import ObjectId

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.settings import validate_section, get_settings
from utils.db import (
    company_settings_collection,
    candidates_collection,
    jobs_collection,
    audit_logs_collection
)
from utils.auth_helper import generate_token
from agents.scheduler import _decide_next_step, schedule_next_step
from agents.resume_screener import _TEMPLATE

TEST_COMPANY_ID = "650000000000000000000002"

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers():
    test_company = {
        "_id": TEST_COMPANY_ID,
        "email": "test@local.dev",
        "company_name": "Test Company"
    }
    token = generate_token(test_company)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ── 1. Threshold Ordering and Bounds Validation ─────────────────────────────
def test_threshold_ordering_validation():
    """l2_score < hr_score must fail validation."""
    invalid_data = {
        "thresholds": {
            "senior": {"advance_score": 75, "l2_score": 50, "hr_score": 60},
            "mid":    {"advance_score": 70, "l2_score": 70, "hr_score": 50},
            "junior": {"advance_score": 65, "l2_score": 65, "hr_score": 45}
        }
    }
    valid, err = validate_section("hiring", invalid_data)
    assert not valid
    assert "l2_score (50) cannot be lower than hr_score (60)" in err

def test_threshold_bounds_validation():
    """Thresholds must be integers between 0 and 100."""
    invalid_data = {
        "thresholds": {
            "senior": {"advance_score": 105, "l2_score": 105, "hr_score": 55},
            "mid":    {"advance_score": 70, "l2_score": 70, "hr_score": 50},
            "junior": {"advance_score": 65, "l2_score": 65, "hr_score": 45}
        }
    }
    valid, err = validate_section("hiring", invalid_data)
    assert not valid
    assert "must be an integer between 0 and 100" in err

# ── 2. Scoring Weights Validation ───────────────────────────────────────────
def test_scoring_weights_sum_validation():
    """Weights summing to != 100 must fail."""
    invalid_data = {
        "scoring_weights": {
            "skills": 40,
            "experience": 30,
            "education": 15,
            "projects": 20  # sum = 105
        }
    }
    valid, err = validate_section("hiring", invalid_data)
    assert not valid
    assert "scoring_weights must sum to 100" in err

def test_scoring_weights_negative_validation():
    """Negative weights must fail."""
    invalid_data = {
        "scoring_weights": {
            "skills": 110,
            "experience": -10,
            "education": 0,
            "projects": 0
        }
    }
    valid, err = validate_section("hiring", invalid_data)
    assert not valid
    assert "must be an integer between 0 and 100" in err

def test_valid_hiring_settings():
    """Valid hiring settings pass validation."""
    valid_data = {
        "thresholds": {
            "senior": {"advance_score": 80, "l2_score": 80, "hr_score": 60},
            "mid":    {"advance_score": 70, "l2_score": 70, "hr_score": 50},
            "junior": {"advance_score": 60, "l2_score": 60, "hr_score": 40}
        },
        "scoring_weights": {
            "skills": 50,
            "experience": 25,
            "education": 15,
            "projects": 10
        },
        "approval_mode": {
            "auto_reject_requires_approval": True
        }
    }
    valid, sanitized = validate_section("hiring", valid_data)
    assert valid
    assert sanitized["thresholds"]["senior"]["l2_score"] == 80
    assert sanitized["scoring_weights"]["skills"] == 50
    assert sanitized["approval_mode"]["auto_reject_requires_approval"] is True

# ── 3. Scheduler Custom Thresholds ───────────────────────────────────────────
def test_scheduler_custom_thresholds():
    """Scheduler uses custom thresholds when provided."""
    custom_thresholds = {
        "senior": {"l2_score": 85, "hr_score": 65},
        "mid":    {"l2_score": 75, "hr_score": 55},
        "junior": {"l2_score": 65, "hr_score": 45}
    }

    # Score 80 with 'recommend' would pass default senior L2 (default 75),
    # but fails custom senior L2 (85), passing custom HR (65)
    decision_custom = _decide_next_step(80, "senior", "recommend", thresholds=custom_thresholds)
    assert decision_custom["decision"] == "advance"
    assert decision_custom["next_step"] == "HR Round"

    # Score 86 passes custom senior L2
    decision_l2 = _decide_next_step(86, "senior", "recommend", thresholds=custom_thresholds)
    assert decision_l2["decision"] == "advance"
    assert decision_l2["next_step"] == "L2 Technical Round"

    # Score 60 fails custom senior HR (65)
    decision_reject = _decide_next_step(60, "senior", "recommend", thresholds=custom_thresholds)
    assert decision_reject["decision"] == "reject"
    assert decision_reject["next_step"] == "Rejected"

# ── 4. Screener Template Rubric with Weights ─────────────────────────────────
def test_screener_weights_rubric():
    """Weights are formatted in template rubric when provided."""
    weights = {"skills": 50, "experience": 30, "education": 10, "projects": 10}
    weights_section = (
        f"SCORING WEIGHTS TO FACTOR IN:\n"
        f"- Skills match: {weights['skills']}%\n"
        f"- Experience match: {weights['experience']}%\n"
        f"- Education match: {weights['education']}%\n"
        f"- Projects: {weights['projects']}%\n"
    )
    formatted = _TEMPLATE.format(
        job_title="Software Engineer",
        required_skills="Python, SQL",
        experience_required="3+ years",
        weights_section=weights_section,
        resume_text="Experienced Python Developer"
    )
    assert "Skills match: 50%" in formatted
    assert "Projects: 10%" in formatted

# ── 5. Pipeline Schedule Missing Evaluation Guard ────────────────────────────
def test_pipeline_schedule_missing_evaluation(client, auth_headers):
    """Scheduling candidate with no evaluation returns 400 'Evaluate answers before scheduling'."""
    cand_doc = {
        "company_id": TEST_COMPANY_ID,
        "job_id": "650000000000000000000099",
        "candidate_name": "No Eval Candidate",
        "candidate_email": "noeval@test.com",
        "status": "invited",
        "evaluation": None
    }
    inserted = candidates_collection.insert_one(cand_doc)
    cid = str(inserted.inserted_id)

    # Insert corresponding job
    jobs_collection.insert_one({
        "_id": ObjectId("650000000000000000000099"),
        "company_id": TEST_COMPANY_ID,
        "job_title": "Software Engineer"
    })

    try:
        res = client.post(f"/api/pipeline/schedule/{cid}", headers=auth_headers, json={})
        assert res.status_code == 400
        assert "Evaluate answers before scheduling" in res.get_json()["error"]
    finally:
        candidates_collection.delete_one({"_id": inserted.inserted_id})
        jobs_collection.delete_one({"_id": ObjectId("650000000000000000000099")})

# ── 6. Candidate Review Endpoints (Approve & Override) ───────────────────────
def test_candidate_review_approve_and_audit(client, auth_headers):
    """Approving a pending review candidate sets status to 'rejected' and writes an audit log."""
    cand_doc = {
        "company_id": TEST_COMPANY_ID,
        "job_id": "650000000000000000000088",
        "candidate_name": "Review Candidate",
        "candidate_email": "review@test.com",
        "status": "pending_review",
        "recommended_decision": "reject",
        "created_at": datetime.now(timezone.utc)
    }
    inserted = candidates_collection.insert_one(cand_doc)
    cid = str(inserted.inserted_id)

    try:
        res = client.post(f"/api/candidates/detail/{cid}/review/approve", headers=auth_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["candidate"]["status"] == "rejected"

        # Verify DB status
        cand_in_db = candidates_collection.find_one({"_id": inserted.inserted_id})
        assert cand_in_db["status"] == "rejected"

        # Verify audit log entry
        audit_entry = audit_logs_collection.find_one({
            "company_id": TEST_COMPANY_ID,
            "candidate_id": cid,
            "action": "candidate_review_approve"
        })
        assert audit_entry is not None
        assert audit_entry["details"]["new_status"] == "rejected"
    finally:
        candidates_collection.delete_one({"_id": inserted.inserted_id})
        audit_logs_collection.delete_many({"candidate_id": cid})

def test_candidate_review_override_and_audit(client, auth_headers):
    """Overriding a pending review candidate sets custom status and writes an audit log."""
    cand_doc = {
        "company_id": TEST_COMPANY_ID,
        "job_id": "650000000000000000000088",
        "candidate_name": "Override Candidate",
        "candidate_email": "override@test.com",
        "status": "pending_review",
        "recommended_decision": "reject",
        "created_at": datetime.now(timezone.utc)
    }
    inserted = candidates_collection.insert_one(cand_doc)
    cid = str(inserted.inserted_id)

    try:
        res = client.post(
            f"/api/candidates/detail/{cid}/review/override",
            headers=auth_headers,
            json={"status": "shortlisted", "reason": "Exceptional portfolio project"}
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["candidate"]["status"] == "shortlisted"

        # Verify DB status
        cand_in_db = candidates_collection.find_one({"_id": inserted.inserted_id})
        assert cand_in_db["status"] == "shortlisted"
        assert cand_in_db["override_reason"] == "Exceptional portfolio project"

        # Verify audit log entry
        audit_entry = audit_logs_collection.find_one({
            "company_id": TEST_COMPANY_ID,
            "candidate_id": cid,
            "action": "candidate_review_override"
        })
        assert audit_entry is not None
        assert audit_entry["details"]["new_status"] == "shortlisted"
        assert audit_entry["details"]["reason"] == "Exceptional portfolio project"
    finally:
        candidates_collection.delete_one({"_id": inserted.inserted_id})
        audit_logs_collection.delete_many({"candidate_id": cid})
