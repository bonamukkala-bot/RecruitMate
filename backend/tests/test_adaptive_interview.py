import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from unittest.mock import patch

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
from utils.adaptive_interview import (
    derive_required_topics,
    initialize_interview_turns,
    sanitize_turn_for_candidate,
    get_active_turn,
    process_turn_submission
)

TEST_COMPANY_ID = "650000000000000000000003"
TEST_TOKEN = "test_adaptive_token_abc123"

@pytest.fixture(autouse=True)
def clean_db():
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    candidates_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    yield
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    candidates_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

@pytest.fixture
def auth_headers():
    token = generate_token({
        "_id": TEST_COMPANY_ID,
        "company_id": TEST_COMPANY_ID,
        "email": "test@local.dev",
        "company_name": "Test Company"
    })
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ─────────────────────────────────────────────────────────────────────────────
# 1. Interview Settings Validation & Defaults
# ─────────────────────────────────────────────────────────────────────────────

def test_adaptive_settings_defaults():
    interview_defaults = DEFAULT_SETTINGS["interview"]
    assert interview_defaults["follow_up_mode"] == "off"
    assert interview_defaults["max_follow_ups_per_question"] == 2
    assert interview_defaults["probe_depth"] == "standard"

def test_adaptive_settings_validation():
    # Valid adaptive config
    valid_data = {
        "follow_up_mode": "adaptive",
        "max_follow_ups_per_question": 3,
        "probe_depth": "deep"
    }
    is_valid, validated = validate_section("interview", valid_data)
    assert is_valid
    assert validated["follow_up_mode"] == "adaptive"
    assert validated["max_follow_ups_per_question"] == 3
    assert validated["probe_depth"] == "deep"

    # Invalid follow_up_mode
    is_valid, err = validate_section("interview", {"follow_up_mode": "unlimited"})
    assert not is_valid
    assert "follow_up_mode must be one of" in err

    # Invalid max_follow_ups (< 0 or > 3)
    is_valid, err = validate_section("interview", {"max_follow_ups_per_question": -1})
    assert not is_valid
    is_valid, err = validate_section("interview", {"max_follow_ups_per_question": 4})
    assert not is_valid

    # Invalid probe_depth
    is_valid, err = validate_section("interview", {"probe_depth": "extreme"})
    assert not is_valid
    assert "probe_depth must be one of" in err

# ─────────────────────────────────────────────────────────────────────────────
# 2. Coverage Tracking & Topic Derivation
# ─────────────────────────────────────────────────────────────────────────────

def test_derive_required_topics():
    job_data = {
        "job_title": "Backend Python Engineer",
        "skills_required": ["Python", "FastAPI", "MongoDB"],
        "requirements": ["Experience with microservices", "Strong unit testing"]
    }
    final_questions = [
        {"id": 1, "question": "Walk me through your background and experience."},
        {"id": 2, "question": "How do you design a scalable microservices architecture in Python?"}
    ]
    topics = derive_required_topics(job_data, final_questions)
    assert "Python" in topics
    assert "FastAPI" in topics
    assert "MongoDB" in topics

# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /interview/public/<token> Backward Compatibility & Adaptive Mode
# ─────────────────────────────────────────────────────────────────────────────

def test_public_interview_off_mode_backward_compatible(client):
    # Setup candidate with follow_up_mode "off"
    job_id = ObjectId()
    candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Alice Candidate",
        "job_id": str(job_id),
        "interview_token": TEST_TOKEN,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "interview_questions_final": [
            {"id": 1, "question": "Intro question"},
            {"id": 2, "question": "Python question"}
        ]
    })
    company_settings_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "interview": {"follow_up_mode": "off", "duration_minutes": 30}
    })

    res = client.get(f"/api/pipeline/interview/public/{TEST_TOKEN}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    # In 'off' mode: questions array is returned as today
    assert "questions" in data
    assert len(data["questions"]) == 2
    assert "active_turn" not in data

def test_public_interview_adaptive_mode_shape_and_sanitization(client):
    job_id = ObjectId()
    candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Bob Candidate",
        "job_id": str(job_id),
        "interview_token": TEST_TOKEN,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "interview_questions_final": [
            {"id": 1, "question": "Intro question"},
            {"id": 2, "question": "FastAPI question"}
        ]
    })
    company_settings_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "interview": {"follow_up_mode": "adaptive", "duration_minutes": 25}
    })

    res = client.get(f"/api/pipeline/interview/public/{TEST_TOKEN}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["follow_up_mode"] == "adaptive"
    # In adaptive mode: questions array is omitted, active_turn + progress returned
    assert "questions" not in data
    assert "active_turn" in data
    assert data["active_turn"]["turn_id"] == "turn_1"
    assert data["active_turn"]["question"] == "Intro question"
    assert "progress" in data
    assert data["progress"]["current_core"] == 1
    assert data["progress"]["total_core"] == 2

    # Sanitization check: No internal keys exposed
    assert "_score" not in data["active_turn"]
    assert "_verdict" not in data["active_turn"]
    assert "_decider_reason" not in data["active_turn"]

# ─────────────────────────────────────────────────────────────────────────────
# 4. Turn Submission & Limit Enforcement (Duration, Code Bypass, Idempotency)
# ─────────────────────────────────────────────────────────────────────────────

def test_turn_submission_progression_and_idempotency(client):
    job_id = ObjectId()
    cand_id = candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Carol Candidate",
        "job_id": str(job_id),
        "interview_token": TEST_TOKEN,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "interview_questions_final": [
            {"id": 1, "question": "Tell me about yourself."},
            {"id": 2, "question": "Explain indexing in MongoDB."}
        ]
    }).inserted_id

    company_settings_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "interview": {"follow_up_mode": "adaptive", "duration_minutes": 30}
    })

    # Load initial adaptive state
    init_res = client.get(f"/api/pipeline/interview/public/{TEST_TOKEN}")
    assert init_res.status_code == 200
    turn_1_id = init_res.get_json()["active_turn"]["turn_id"]

    # 1. Submit answer for turn 1
    turn_res = client.post(f"/api/pipeline/interview/public/{TEST_TOKEN}/turn", json={
        "turn_id": turn_1_id,
        "answer": "I have 5 years of software engineering experience."
    })
    assert turn_res.status_code == 200
    turn_data = turn_res.get_json()
    assert turn_data["success"] is True
    assert turn_data["finished"] is False
    assert turn_data["active_turn"]["question"] == "Explain indexing in MongoDB."
    next_turn_id = turn_data["active_turn"]["turn_id"]

    # 2. Idempotency test: resubmitting turn 1 must return the same next turn without duplicating
    dup_res = client.post(f"/api/pipeline/interview/public/{TEST_TOKEN}/turn", json={
        "turn_id": turn_1_id,
        "answer": "I have 5 years of experience."
    })
    assert dup_res.status_code == 200
    dup_data = dup_res.get_json()
    assert dup_data["active_turn"]["turn_id"] == next_turn_id

    # Check database: no duplicates in interview_turns
    cand_doc = candidates_collection.find_one({"_id": cand_id})
    assert len(cand_doc["interview_turns"]) == 2

def test_code_question_bypasses_follow_up(client):
    # Decision #2: For code-type questions, treat decision as next_core (no follow-ups)
    job_id = ObjectId()
    cand_id = candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Dave Candidate",
        "job_id": str(job_id),
        "interview_token": TEST_TOKEN,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "interview_questions_final": [
            {"id": 1, "question": "Write code to reverse a linked list."},
            {"id": 2, "question": "Behavioral question on teamwork."}
        ]
    }).inserted_id

    company_settings_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "interview": {"follow_up_mode": "adaptive", "duration_minutes": 30}
    })

    client.get(f"/api/pipeline/interview/public/{TEST_TOKEN}")

    # Submit code question answer
    res = client.post(f"/api/pipeline/interview/public/{TEST_TOKEN}/turn", json={
        "turn_id": "turn_1",
        "answer": "def reverse(head): ..."
    })
    assert res.status_code == 200
    data = res.get_json()
    # Advanced directly to next core question (no code follow-up)
    assert data["active_turn"]["question"] == "Behavioral question on teamwork."
    assert data["active_turn"]["core_question_index"] == 1

def test_duration_limit_enforcement(client):
    # Decision #1: Server enforces overall duration_minutes from asked_at/started_at
    job_id = ObjectId()
    past_time = datetime.now(timezone.utc) - timedelta(minutes=35)

    candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Eve Candidate",
        "job_id": str(job_id),
        "interview_token": TEST_TOKEN,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "interview_questions_final": [
            {"id": 1, "question": "Q1"},
            {"id": 2, "question": "Q2"}
        ],
        "interview_turns": [
            {
                "turn_id": "turn_1",
                "parent_turn_id": None,
                "core_question_index": 0,
                "type": "core",
                "question": "Q1",
                "answer": None,
                "asked_at": past_time,
                "answered_at": None
            }
        ],
        "interview_coverage": {
            "required_topics": ["Topic1"],
            "covered_topics": [],
            "current_core_index": 0,
            "follow_ups_on_current": 0,
            "restated_on_current": False,
            "interview_started_at": past_time
        }
    })

    company_settings_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "interview": {"follow_up_mode": "adaptive", "duration_minutes": 30}
    })

    # Submitting past the 30-min duration limit marks the interview finished
    res = client.post(f"/api/pipeline/interview/public/{TEST_TOKEN}/turn", json={
        "turn_id": "turn_1",
        "answer": "My answer"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["finished"] is True

# ─────────────────────────────────────────────────────────────────────────────
# 5. Proctoring Termination Transcript Persistence (Decision #3)
# ─────────────────────────────────────────────────────────────────────────────

def test_proctoring_termination_preserves_transcript(client):
    job_id = ObjectId()
    cand_id = candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Frank Candidate",
        "job_id": str(job_id),
        "interview_token": TEST_TOKEN,
        "interview_token_exp": datetime.now(timezone.utc) + timedelta(days=2),
        "interview_status": "pending",
        "consent_accepted": True,
        "interview_questions_final": [{"id": 1, "question": "Q1"}],
        "interview_turns": [
            {
                "turn_id": "turn_1",
                "parent_turn_id": None,
                "core_question_index": 0,
                "type": "core",
                "question": "Q1",
                "answer": "Partial answer before violation",
                "asked_at": datetime.now(timezone.utc),
                "answered_at": datetime.now(timezone.utc)
            }
        ]
    }).inserted_id

    # Call submit with termination
    res = client.post(f"/api/pipeline/interview/public/{TEST_TOKEN}/submit", json={
        "terminated": True,
        "termination_reason": "Excessive tab switches",
        "integrity_log": [{"event": "tab_switch"}]
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["decision"] == "terminated"

    # Confirm candidate has both interview_answers and interview_turns preserved
    doc = candidates_collection.find_one({"_id": cand_id})
    assert doc["status"] == "terminated"
    assert doc["terminated"] is True
    assert len(doc["interview_turns"]) == 1
    assert len(doc["interview_answers"]) == 1
    assert doc["interview_answers"][0]["answer"] == "Partial answer before violation"
