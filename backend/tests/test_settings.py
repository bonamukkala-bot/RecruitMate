import pytest
import os
import sys
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.settings import (
    DEFAULT_SETTINGS,
    VALID_SECTIONS,
    get_settings,
    validate_section,
    assert_safe_db
)
from utils.db import company_settings_collection
from utils.auth_helper import generate_token

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers():
    test_company = {
        "_id": "650000000000000000000001",
        "email": "test@local.dev",
        "company_name": "Test Company"
    }
    token = generate_token(test_company)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def test_safety_check():
    """Ensure safety guard prevents running operations against production db."""
    original_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_db()
        assert "production database" in str(exc_info.value)
    finally:
        Config.DB_NAME = original_db

def test_default_settings_structure():
    """Ensure DEFAULT_SETTINGS contains all required sections with expected structure."""
    expected_sections = {"hiring", "interview", "email", "ai", "company", "privacy", "integrations"}
    assert expected_sections == VALID_SECTIONS
    assert expected_sections.issubset(set(DEFAULT_SETTINGS.keys()))

    # Check key hiring defaults
    assert DEFAULT_SETTINGS["hiring"]["thresholds"]["senior"]["l2_score"] == 75
    assert sum(DEFAULT_SETTINGS["hiring"]["scoring_weights"].values()) == 100
    assert DEFAULT_SETTINGS["hiring"]["approval_mode"]["auto_reject_requires_approval"] is False

    # Check interview defaults
    assert DEFAULT_SETTINGS["interview"]["duration_minutes"] == 30
    assert DEFAULT_SETTINGS["interview"]["question_count"] == 8
    assert DEFAULT_SETTINGS["interview"]["proctoring"]["face_detection"] is True

def test_get_settings_fallback_to_defaults():
    """get_settings returns DEFAULT_SETTINGS when no settings doc exists."""
    non_existent_id = "999999999999999999999999"
    company_settings_collection.delete_many({"company_id": non_existent_id})

    settings = get_settings(non_existent_id)
    assert settings == DEFAULT_SETTINGS

    # Mutating returned settings must not alter DEFAULT_SETTINGS
    settings["interview"]["duration_minutes"] = 99
    assert DEFAULT_SETTINGS["interview"]["duration_minutes"] == 30

def test_get_settings_deep_merge():
    """get_settings deep-merges stored overrides over defaults."""
    test_company_id = "test_comp_merge_123"
    company_settings_collection.delete_many({"company_id": test_company_id})

    # Save partial custom setting
    company_settings_collection.insert_one({
        "company_id": test_company_id,
        "interview": {
            "duration_minutes": 45
        }
    })

    merged = get_settings(test_company_id)
    assert merged["interview"]["duration_minutes"] == 45
    # Non-overridden nested fields should remain at default values
    assert merged["interview"]["question_count"] == DEFAULT_SETTINGS["interview"]["question_count"]
    assert merged["interview"]["proctoring"]["face_detection"] is True
    assert merged["hiring"] == DEFAULT_SETTINGS["hiring"]

    company_settings_collection.delete_many({"company_id": test_company_id})

def test_validate_section_hiring():
    """Test validation of hiring section."""
    # Valid hiring section
    valid_data = {
        "thresholds": {
            "senior": {"advance_score": 80, "l2_score": 80, "hr_score": 60},
            "mid": {"advance_score": 70, "l2_score": 70, "hr_score": 50},
            "junior": {"advance_score": 60, "l2_score": 60, "hr_score": 40}
        },
        "scoring_weights": {
            "skills": 50,
            "experience": 30,
            "education": 10,
            "projects": 10
        },
        "approval_mode": {
            "auto_reject_requires_approval": True
        }
    }
    is_valid, res = validate_section("hiring", valid_data)
    assert is_valid is True

    # Invalid weights sum
    invalid_weights = copy_dict = dict(valid_data)
    invalid_weights["scoring_weights"] = {"skills": 40, "experience": 30, "education": 10, "projects": 10}
    is_valid, err = validate_section("hiring", invalid_weights)
    assert is_valid is False
    assert "must sum to 100" in err

    # Invalid thresholds ordering (l2 < hr)
    invalid_order = dict(valid_data)
    invalid_order["thresholds"] = {
        "senior": {"advance_score": 80, "l2_score": 50, "hr_score": 60},
        "mid": {"advance_score": 70, "l2_score": 70, "hr_score": 50},
        "junior": {"advance_score": 60, "l2_score": 60, "hr_score": 40}
    }
    is_valid, err = validate_section("hiring", invalid_order)
    assert is_valid is False
    assert "cannot be lower than" in err

def test_validate_section_interview():
    """Test validation of interview section."""
    valid_data = {
        "duration_minutes": 45,
        "question_count": 10,
        "difficulty": "hard",
        "question_types": "technical",
        "proctoring": {
            "enabled": True,
            "face_detection": False,
            "fullscreen_required": True,
            "tab_switch_violations_allowed": 2,
            "no_face_grace_seconds": 15,
            "terminate_on_violation": False
        }
    }
    is_valid, res = validate_section("interview", valid_data)
    assert is_valid is True

    # Invalid question count
    invalid_q = dict(valid_data, question_count=50)
    is_valid, err = validate_section("interview", invalid_q)
    assert is_valid is False
    assert "question_count" in err

    # Invalid difficulty
    invalid_diff = dict(valid_data, difficulty="impossible")
    is_valid, err = validate_section("interview", invalid_diff)
    assert is_valid is False
    assert "difficulty" in err

def test_api_get_settings_unauthorized(client):
    """GET /api/settings requires JWT."""
    res = client.get("/api/settings")
    assert res.status_code == 401

def test_api_get_settings_authorized(client, auth_headers):
    """GET /api/settings returns 200 with merged settings."""
    res = client.get("/api/settings", headers=auth_headers)
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert "settings" in json_data
    assert "hiring" in json_data["settings"]
    assert "interview" in json_data["settings"]

def test_api_put_and_reset_section(client, auth_headers):
    """PUT /api/settings/<section> updates section, and reset endpoint restores defaults."""
    test_comp_id = "650000000000000000000001"
    company_settings_collection.delete_many({"company_id": test_comp_id})

    # Update interview settings
    update_payload = {
        "duration_minutes": 50,
        "question_count": 12,
        "difficulty": "hard"
    }
    put_res = client.put("/api/settings/interview", json=update_payload, headers=auth_headers)
    assert put_res.status_code == 200
    put_json = put_res.get_json()
    assert put_json["success"] is True
    assert put_json["data"]["duration_minutes"] == 50
    assert put_json["data"]["question_count"] == 12

    # Verify persisted in database
    get_res = client.get("/api/settings", headers=auth_headers)
    assert get_res.get_json()["settings"]["interview"]["duration_minutes"] == 50

    # Reset interview settings
    reset_res = client.post("/api/settings/interview/reset", headers=auth_headers)
    assert reset_res.status_code == 200
    reset_json = reset_res.get_json()
    assert reset_json["success"] is True
    assert reset_json["data"]["duration_minutes"] == DEFAULT_SETTINGS["interview"]["duration_minutes"]

    # Verify reset persisted
    get_res_after = client.get("/api/settings", headers=auth_headers)
    assert get_res_after.get_json()["settings"]["interview"]["duration_minutes"] == DEFAULT_SETTINGS["interview"]["duration_minutes"]

    company_settings_collection.delete_many({"company_id": test_comp_id})

def test_api_put_invalid_section(client, auth_headers):
    """PUT /api/settings/<invalid> returns 400."""
    res = client.put("/api/settings/invalid_section_xyz", json={}, headers=auth_headers)
    assert res.status_code == 400
    assert "Invalid section" in res.get_json()["error"]

def test_settings_routes_allow_production_db_name(client, auth_headers):
    """
    Regression test: Calling settings GET, PUT, and reset endpoints with
    Config.DB_NAME patched to 'recruitmate' must succeed with 200, never 500.
    The assert_safe_db guard applies to standalone scripts only, not HTTP routes.
    """
    test_comp_id = "650000000000000000000001"
    original_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"

        # 1. GET /api/settings
        get_res = client.get("/api/settings", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.get_json()["success"] is True

        # 2. PUT /api/settings/hiring
        put_payload = {
            "thresholds": {
                "senior": {"advance_score": 75, "l2_score": 75, "hr_score": 55},
                "mid":    {"advance_score": 70, "l2_score": 70, "hr_score": 50},
                "junior": {"advance_score": 65, "l2_score": 65, "hr_score": 45}
            },
            "scoring_weights": {
                "skills": 40,
                "experience": 30,
                "education": 15,
                "projects": 15
            },
            "approval_mode": {
                "auto_reject_requires_approval": False
            }
        }
        put_res = client.put("/api/settings/hiring", json=put_payload, headers=auth_headers)
        assert put_res.status_code == 200
        assert put_res.get_json()["success"] is True

        # 3. POST /api/settings/hiring/reset
        reset_res = client.post("/api/settings/hiring/reset", headers=auth_headers)
        assert reset_res.status_code == 200
        assert reset_res.get_json()["success"] is True

    finally:
        Config.DB_NAME = original_db
        company_settings_collection.delete_many({"company_id": test_comp_id})
