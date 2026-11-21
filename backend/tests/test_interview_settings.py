import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from bson import ObjectId

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.settings import (
    DEFAULT_SETTINGS,
    validate_section,
    get_settings
)
from utils.db import (
    company_settings_collection,
    candidates_collection,
    jobs_collection
)
from utils.auth_helper import generate_token
from agents.question_generator import (
    _get_category_distribution,
    _build_prompt,
    generate_questions
)

TEST_COMPANY_ID = "650000000000000000000003"

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

# ── 1. Validation Ranges ─────────────────────────────────────────────────────
def test_interview_duration_range_validation():
    """duration_minutes must be an integer between 5 and 120."""
    invalid_low = {"duration_minutes": 4}
    valid, err = validate_section("interview", invalid_low)
    assert not valid
    assert "duration_minutes must be an integer between 5 and 120" in err

    invalid_high = {"duration_minutes": 121}
    valid, err = validate_section("interview", invalid_high)
    assert not valid
    assert "duration_minutes must be an integer between 5 and 120" in err

    valid_res, sanitized = validate_section("interview", {"duration_minutes": 45})
    assert valid_res
    assert sanitized["duration_minutes"] == 45

def test_interview_question_count_range_validation():
    """question_count must be an integer between 3 and 20."""
    invalid_low = {"question_count": 2}
    valid, err = validate_section("interview", invalid_low)
    assert not valid
    assert "question_count must be an integer between 3 and 20" in err

    invalid_high = {"question_count": 21}
    valid, err = validate_section("interview", invalid_high)
    assert not valid
    assert "question_count must be an integer between 3 and 20" in err

    valid_res, sanitized = validate_section("interview", {"question_count": 12})
    assert valid_res
    assert sanitized["question_count"] == 12

def test_interview_difficulty_and_types_validation():
    """difficulty and question_types must be allowed enum values."""
    valid, err = validate_section("interview", {"difficulty": "impossible"})
    assert not valid
    assert "difficulty must be one of" in err

    valid, err = validate_section("interview", {"question_types": "random"})
    assert not valid
    assert "question_types must be one of" in err

    valid_res, sanitized = validate_section("interview", {
        "difficulty": "hard",
        "question_types": "technical"
    })
    assert valid_res
    assert sanitized["difficulty"] == "hard"
    assert sanitized["question_types"] == "technical"

def test_interview_proctoring_ranges_validation():
    """Proctoring rules must validate bounds and boolean types."""
    invalid_tab = {"proctoring": {"tab_switch_violations_allowed": 6}}
    valid, err = validate_section("interview", invalid_tab)
    assert not valid
    assert "tab_switch_violations_allowed must be an integer between 0 and 5" in err

    invalid_grace = {"proctoring": {"no_face_grace_seconds": 65}}
    valid, err = validate_section("interview", invalid_grace)
    assert not valid
    assert "no_face_grace_seconds must be an integer between 0 and 60" in err

    valid_res, sanitized = validate_section("interview", {
        "proctoring": {
            "enabled": True,
            "face_detection": True,
            "fullscreen_required": True,
            "tab_switch_violations_allowed": 2,
            "no_face_grace_seconds": 15,
            "terminate_on_violation": False
        }
    })
    assert valid_res
    assert sanitized["proctoring"]["tab_switch_violations_allowed"] == 2
    assert sanitized["proctoring"]["no_face_grace_seconds"] == 15
    assert sanitized["proctoring"]["terminate_on_violation"] is False

# ── 2. Defaults Match Existing Behavior ──────────────────────────────────────
def test_interview_defaults_match_existing_behavior():
    """Defaults in DEFAULT_SETTINGS['interview'] reproduce today's hardcoded behavior."""
    d = DEFAULT_SETTINGS["interview"]
    assert d["duration_minutes"] == 30
    assert d["question_count"] == 8
    assert d["difficulty"] == "medium"
    assert d["question_types"] == "mixed"
    assert d["proctoring"]["enabled"] is True
    assert d["proctoring"]["face_detection"] is True
    assert d["proctoring"]["fullscreen_required"] is True
    assert d["proctoring"]["tab_switch_violations_allowed"] == 1  # 2nd strike terminates
    assert d["proctoring"]["no_face_grace_seconds"] == 10
    assert d["proctoring"]["terminate_on_violation"] is True

# ── 3. Candidate Safe Subset Endpoint ────────────────────────────────────────
def test_candidate_public_interview_safe_subset(client):
    """GET /api/pipeline/interview/public/<token> returns ONLY the safe candidate subset."""
    token = "test_token_safe_subset_123"
    job_id = ObjectId()
    cand_id = ObjectId()

    # Create job
    jobs_collection.insert_one({
        "_id": job_id,
        "company_id": TEST_COMPANY_ID,
        "job_title": "Full Stack Engineer"
    })

    # Create candidate with interview token
    candidates_collection.insert_one({
        "_id": cand_id,
        "company_id": TEST_COMPANY_ID,
        "job_id": str(job_id),
        "candidate_name": "Jane Candidate",
        "interview_token": token,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "company_name": "Acme Corp",
        "interview_questions_final": [
            {"id": 1, "question": "Introduce yourself"},
            {"id": 2, "question": "Explain React hooks"}
        ]
    })

    try:
        res = client.get(f"/api/pipeline/interview/public/{token}")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["candidate_name"] == "Jane Candidate"
        assert data["job_title"] == "Full Stack Engineer"
        assert data["company_name"] == "Acme Corp"
        assert len(data["questions"]) == 2
        assert "duration_minutes" in data
        assert "proctoring" in data

        proctoring = data["proctoring"]
        assert "enabled" in proctoring
        assert "face_detection" in proctoring
        assert "fullscreen_required" in proctoring
        assert "tab_switch_violations_allowed" in proctoring
        assert "no_face_grace_seconds" in proctoring
        assert "terminate_on_violation" in proctoring

        # Verify NO secrets, auth tokens, database credentials, or full company settings are exposed
        forbidden_keys = {"company_id", "secret", "token_hash", "mongo_uri", "password", "email_templates", "integrations", "ai"}
        assert forbidden_keys.isdisjoint(set(data.keys()))
        assert forbidden_keys.isdisjoint(set(proctoring.keys()))

    finally:
        candidates_collection.delete_one({"_id": cand_id})
        jobs_collection.delete_one({"_id": job_id})

# ── 4. Regression Test: Config.DB_NAME == 'recruitmate' Returns 200 ──────────
def test_interview_settings_save_and_reset_production_db(client, auth_headers):
    """Saving and resetting interview settings returns 200 when Config.DB_NAME is 'recruitmate'."""
    original_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"

        # Update interview settings
        payload = {
            "duration_minutes": 45,
            "question_count": 10,
            "difficulty": "hard",
            "question_types": "mixed",
            "proctoring": {
                "enabled": True,
                "face_detection": True,
                "fullscreen_required": True,
                "tab_switch_violations_allowed": 2,
                "no_face_grace_seconds": 15,
                "terminate_on_violation": True
            }
        }
        put_res = client.put("/api/settings/interview", json=payload, headers=auth_headers)
        assert put_res.status_code == 200
        assert put_res.get_json()["success"] is True
        assert put_res.get_json()["data"]["duration_minutes"] == 45

        # Reset interview settings
        reset_res = client.post("/api/settings/interview/reset", headers=auth_headers)
        assert reset_res.status_code == 200
        assert reset_res.get_json()["success"] is True
        assert reset_res.get_json()["data"]["duration_minutes"] == DEFAULT_SETTINGS["interview"]["duration_minutes"]

    finally:
        Config.DB_NAME = original_db
        company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})

# ── 5. Question Generator Logic ──────────────────────────────────────────────
def test_question_generator_distribution_and_prompt():
    """Verify distribution calculation and prompt building."""
    dist_mixed_8 = _get_category_distribution(8, "mixed")
    assert sum(dist_mixed_8.values()) == 8
    assert dist_mixed_8["gap_focused"] == 2
    assert dist_mixed_8["technical"] == 3
    assert dist_mixed_8["behavioral"] == 3

    dist_tech = _get_category_distribution(10, "technical")
    assert dist_tech["technical"] == 10
    assert dist_tech["behavioral"] == 0

    dist_beh = _get_category_distribution(6, "behavioral")
    assert dist_beh["behavioral"] == 6
    assert dist_beh["technical"] == 0

    prompt = _build_prompt(
        candidate_name="Alice",
        job_title="Backend Developer",
        matched_skills="Python, Docker",
        missing_skills="Kubernetes",
        reasoning="Strong profile",
        question_count=12,
        difficulty="hard",
        question_types="mixed"
    )
    assert "Generate exactly 12 personalized interview questions" in prompt
    assert "INTERVIEW DIFFICULTY: hard" in prompt
    assert "QUESTION TYPES FOCUS: mixed" in prompt
