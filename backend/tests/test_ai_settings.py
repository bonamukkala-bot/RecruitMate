import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

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
    llm_usage_collection
)
from utils.auth_helper import generate_token
from utils.llm import (
    call_llm,
    clean_reasoning_text,
    extract_json_payload,
    get_company_monthly_tokens,
    check_budget_limit,
    log_llm_usage,
    TokenBudgetExceededError
)

TEST_COMPANY_ID = "650000000000000000000004"

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

@pytest.fixture(autouse=True)
def cleanup():
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    llm_usage_collection.delete_many({"company_id": TEST_COMPANY_ID})
    yield
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    llm_usage_collection.delete_many({"company_id": TEST_COMPANY_ID})

# ── 1. Settings Schema & Allow-list Validation ────────────────────────────────
def test_ai_settings_allow_list_validation():
    """Valid and invalid model selection from GROQ_ALLOWED_MODELS."""
    # Valid models
    valid_payload = {
        "model_default": Config.GROQ_ALLOWED_MODELS[0],
        "model_heavy": Config.GROQ_ALLOWED_MODELS[-1]
    }
    valid, res = validate_section("ai", valid_payload)
    assert valid is True
    assert res["model_default"] == Config.GROQ_ALLOWED_MODELS[0]
    assert res["model_heavy"] == Config.GROQ_ALLOWED_MODELS[-1]

    # Disallowed model
    invalid_payload = {
        "model_default": "unauthorized/super-gpt-9000"
    }
    valid, err = validate_section("ai", invalid_payload)
    assert valid is False
    assert "not in allowed models" in err

def test_ai_settings_language_tone_temp_budget_validation():
    """Validation for output_language, tone, temperature, and monthly_token_budget."""
    # Invalid language
    valid, err = validate_section("ai", {"output_language": "French"})
    assert valid is False
    assert "output_language must be one of" in err

    # Valid languages
    for lang in ["English", "Telugu", "Hindi"]:
        valid, res = validate_section("ai", {"output_language": lang})
        assert valid is True
        assert res["output_language"] == lang

    # Invalid tone
    valid, err = validate_section("ai", {"tone": "aggressive"})
    assert valid is False
    assert "tone must be one of" in err

    # Valid tones
    for tone in ["professional", "friendly", "concise"]:
        valid, res = validate_section("ai", {"tone": tone})
        assert valid is True
        assert res["tone"] == tone

    # Invalid temperature
    valid, err = validate_section("ai", {"temperature": 1.5})
    assert valid is False
    assert "temperature must be a number between 0.0 and 1.0" in err

    valid, err = validate_section("ai", {"temperature": -0.1})
    assert valid is False
    assert "temperature must be a number between 0.0 and 1.0" in err

    # Invalid budget
    valid, err = validate_section("ai", {"monthly_token_budget": -50})
    assert valid is False
    assert "monthly_token_budget must be a non-negative integer" in err

    valid, err = validate_section("ai", {"monthly_token_budget": "unlimited"})
    assert valid is False
    assert "monthly_token_budget must be a non-negative integer" in err

    # Valid budget: 0 (unlimited) and positive numbers (int and numeric string)
    valid, res = validate_section("ai", {"monthly_token_budget": 0})
    assert valid is True
    assert res["monthly_token_budget"] == 0

    valid, res = validate_section("ai", {"monthly_token_budget": "50000"})
    assert valid is True
    assert res["monthly_token_budget"] == 50000

    # Valid temperatures (numeric float, int, numeric string)
    for t_val, expected in [(0, 0.0), (0.35, 0.35), ("0.7", 0.7), (1, 1.0)]:
        valid, res = validate_section("ai", {"temperature": t_val})
        assert valid is True
        assert res["temperature"] == expected

    # Boolean temperature or budget must be rejected
    valid, err = validate_section("ai", {"temperature": True})
    assert valid is False
    valid, err = validate_section("ai", {"monthly_token_budget": True})
    assert valid is False

# ── 2. Reasoning Text Stripping & JSON Extraction ─────────────────────────────
def test_clean_reasoning_and_fences():
    """Ensure <think> tags, <thought> tags, and markdown code fences are stripped."""
    raw = """<think>
    Thinking through candidate skills...
    The match is 85%.
    </think>
    ```json
    {"score": 85, "verdict": "shortlist"}
    ```"""
    cleaned = clean_reasoning_text(raw)
    assert "<think>" not in cleaned
    assert "Thinking through" not in cleaned
    assert "```json" not in cleaned
    assert '{"score": 85, "verdict": "shortlist"}' in cleaned

def test_extract_json_payload():
    """Extract JSON object or array even when embedded in prose."""
    prose_json = """Here is the result of the evaluation:
    {
        "status": "passed",
        "score": 92
    }
    Hope this helps!"""
    parsed = extract_json_payload(prose_json)
    assert parsed == {"status": "passed", "score": 92}

    # Array extraction
    prose_array = """[{"q": "What is Python?"}, {"q": "Explain Docker"}]"""
    parsed_arr = extract_json_payload(prose_array)
    assert len(parsed_arr) == 2
    assert parsed_arr[0]["q"] == "What is Python?"

    # Invalid JSON
    assert extract_json_payload("Plain text with no brackets") is None

# ── 3. Central call_llm & Mocking ─────────────────────────────────────────────
def test_call_llm_applies_company_settings():
    """call_llm applies company settings (language, tone, temperature, model)."""
    # Seed company settings
    company_settings_collection.update_one(
        {"company_id": TEST_COMPANY_ID},
        {"$set": {
            "company_id": TEST_COMPANY_ID,
            "ai": {
                "model_default": Config.GROQ_ALLOWED_MODELS[0],
                "model_heavy": Config.GROQ_ALLOWED_MODELS[-1],
                "output_language": "Telugu",
                "tone": "friendly",
                "temperature": 0.7,
                "monthly_token_budget": 0
            }
        }},
        upsert=True
    )

    fake_response = MagicMock()
    fake_response.content = '{"greeting": "నమస్కారం"}'
    fake_response.response_metadata = {
        "token_usage": {
            "prompt_tokens": 50,
            "completion_tokens": 20,
            "total_tokens": 70
        }
    }

    with patch("utils.llm.ChatGroq") as mock_groq_class:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = fake_response
        mock_groq_class.return_value = mock_instance

        # Call standard model
        result = call_llm(
            company_id=TEST_COMPANY_ID,
            agent_name="test_agent",
            messages=[{"role": "user", "content": "Hello"}],
            heavy=False,
            expect_json=True
        )

        assert result["success"] is True
        assert result["data"] == {"greeting": "నమస్కారం"}
        # Verify ChatGroq initialized with model_default and temperature
        mock_groq_class.assert_called_with(
            groq_api_key=Config.GROQ_API_KEY,
            model_name=Config.GROQ_ALLOWED_MODELS[0],
            temperature=0.7,
            max_tokens=2048,
            timeout=45.0
        )

        # Call heavy model
        call_llm(
            company_id=TEST_COMPANY_ID,
            agent_name="test_heavy_agent",
            messages=[{"role": "user", "content": "Complex analysis"}],
            heavy=True,
            expect_json=True
        )
        mock_groq_class.assert_called_with(
            groq_api_key=Config.GROQ_API_KEY,
            model_name=Config.GROQ_ALLOWED_MODELS[-1],
            temperature=0.7,
            max_tokens=4096,
            timeout=45.0
        )

# ── 4. Transient Error Retry ──────────────────────────────────────────────────
def test_call_llm_transient_retry():
    """call_llm retries once on transient failure and succeeds on 2nd attempt."""
    fake_success = MagicMock()
    fake_success.content = "All good"
    fake_success.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}

    with patch("utils.llm.ChatGroq") as mock_groq_class:
        mock_instance = MagicMock()
        # Fail first, succeed second
        mock_instance.invoke.side_effect = [Exception("Rate limit 429"), fake_success]
        mock_groq_class.return_value = mock_instance

        res = call_llm(
            company_id=TEST_COMPANY_ID,
            agent_name="retry_agent",
            messages=[{"role": "user", "content": "Ping"}]
        )

        assert res["success"] is True
        assert res["text"] == "All good"
        assert mock_instance.invoke.call_count == 2

# ── 5. Usage Logging ──────────────────────────────────────────────────────────
def test_call_llm_usage_logged_to_db():
    """call_llm records token usage and estimated cost to llm_usage_collection."""
    fake_response = MagicMock()
    fake_response.content = "Response text"
    fake_response.response_metadata = {
        "token_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }

    with patch("utils.llm.ChatGroq") as mock_groq_class:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = fake_response
        mock_groq_class.return_value = mock_instance

        call_llm(
            company_id=TEST_COMPANY_ID,
            agent_name="screening_agent",
            messages=[{"role": "user", "content": "Analyze"}]
        )

        # Check DB log
        record = llm_usage_collection.find_one({"company_id": TEST_COMPANY_ID, "agent": "screening_agent"})
        assert record is not None
        assert record["prompt_tokens"] == 100
        assert record["completion_tokens"] == 50
        assert record["total_tokens"] == 150
        assert record["success"] is True
        assert record["estimated_cost"] > 0
        assert "latency_ms" in record

# ── 6. Monthly Token Budget Enforcement ───────────────────────────────────────
def test_token_budget_blocking():
    """Non-essential calls are blocked at 100% budget, essential calls proceed."""
    # Seed company settings with a tiny budget of 100 tokens
    company_settings_collection.update_one(
        {"company_id": TEST_COMPANY_ID},
        {"$set": {
            "company_id": TEST_COMPANY_ID,
            "ai": {
                "monthly_token_budget": 100
            }
        }},
        upsert=True
    )

    # Seed usage that already exceeded 100 tokens this month
    now = datetime.now(timezone.utc)
    llm_usage_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "agent": "old_call",
        "model": "model-x",
        "prompt_tokens": 80,
        "completion_tokens": 50,
        "total_tokens": 130,
        "estimated_cost": 0.001,
        "latency_ms": 300,
        "success": True,
        "ts": now
    })

    fake_response = MagicMock()
    fake_response.content = "OK"
    fake_response.response_metadata = {"token_usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}}

    with patch("utils.llm.ChatGroq") as mock_groq_class:
        mock_instance = MagicMock()
        mock_instance.invoke.return_value = fake_response
        mock_groq_class.return_value = mock_instance

        # Non-essential call should raise TokenBudgetExceededError
        with pytest.raises(TokenBudgetExceededError):
            call_llm(
                company_id=TEST_COMPANY_ID,
                agent_name="resume_screener",
                messages=[{"role": "user", "content": "Screen this"}],
                essential=False
            )

        # Essential call should proceed without exception
        essential_res = call_llm(
            company_id=TEST_COMPANY_ID,
            agent_name="auth_service",
            messages=[{"role": "user", "content": "Verify"}],
            essential=True
        )
        assert essential_res["success"] is True
        assert essential_res["text"] == "OK"

# ── 7. Usage API Endpoint ─────────────────────────────────────────────────────
def test_get_ai_usage_endpoint_empty_collection(client, auth_headers):
    """GET /api/settings/ai/usage returns 200 with all zeros when llm_usage is empty."""
    # Ensure collection has no records
    llm_usage_collection.delete_many({"company_id": TEST_COMPANY_ID})

    res = client.get("/api/settings/ai/usage", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["totals_7d"]["total_calls"] == 0
    assert data["totals_7d"]["total_tokens"] == 0
    assert data["totals_7d"]["estimated_cost"] == 0.0
    assert data["totals_30d"]["total_calls"] == 0
    assert data["totals_30d"]["total_tokens"] == 0
    assert data["totals_30d"]["estimated_cost"] == 0.0
    assert data["by_agent"] == []
    assert data["by_model"] == []
    assert len(data["daily_timeseries"]) == 14
    for day in data["daily_timeseries"]:
        assert day["tokens"] == 0
        assert day["cost"] == 0.0

def test_get_ai_usage_endpoint(client, auth_headers):
    """GET /api/settings/ai/usage returns aggregated statistics and timeseries."""
    # Insert dummy records
    now = datetime.now(timezone.utc)
    llm_usage_collection.insert_many([
        {
            "company_id": TEST_COMPANY_ID,
            "agent": "jd_parser",
            "model": "openai/gpt-oss-20b",
            "prompt_tokens": 500,
            "completion_tokens": 100,
            "total_tokens": 600,
            "estimated_cost": 0.0001,
            "latency_ms": 450,
            "success": True,
            "ts": now - timedelta(days=2)
        },
        {
            "company_id": TEST_COMPANY_ID,
            "agent": "resume_screener",
            "model": "openai/gpt-oss-120b",
            "prompt_tokens": 1500,
            "completion_tokens": 300,
            "total_tokens": 1800,
            "estimated_cost": 0.0012,
            "latency_ms": 1200,
            "success": True,
            "ts": now - timedelta(hours=1)
        }
    ])

    res = client.get("/api/settings/ai/usage", headers=auth_headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "budget" in data
    assert "totals_7d" in data
    assert "totals_30d" in data
    assert "by_agent" in data
    assert "by_model" in data
    assert "daily_timeseries" in data
    assert len(data["daily_timeseries"]) == 14
    assert data["totals_7d"]["total_tokens"] == 2400
    assert len(data["by_agent"]) == 2
    assert len(data["by_model"]) == 2

# ── 8. Regression Test: Production Guard Never Blocks API Handlers ────────────
def test_regression_prod_guard_does_not_block_settings_api(client, auth_headers):
    """
    Assert that PUT /api/settings/ai and POST /api/settings/ai/reset
    return 200 even when Config.DB_NAME is patched to 'recruitmate'.
    """
    original_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"

        # Save AI settings
        payload = {
            "model_default": Config.GROQ_ALLOWED_MODELS[0],
            "model_heavy": Config.GROQ_ALLOWED_MODELS[-1],
            "output_language": "Telugu",
            "tone": "friendly",
            "temperature": 0.5,
            "monthly_token_budget": 500000
        }
        put_res = client.put("/api/settings/ai", json=payload, headers=auth_headers)
        assert put_res.status_code == 200
        assert put_res.get_json()["success"] is True
        assert put_res.get_json()["data"]["output_language"] == "Telugu"

        # Reset AI settings
        reset_res = client.post("/api/settings/ai/reset", headers=auth_headers)
        assert reset_res.status_code == 200
        assert reset_res.get_json()["success"] is True
        assert reset_res.get_json()["data"]["output_language"] == DEFAULT_SETTINGS["ai"]["output_language"]

    finally:
        Config.DB_NAME = original_db
        company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})

# ── 9. Config Defaults and TTL Index Creation ─────────────────────────────────
def test_default_settings_ai_passes_validation():
    """Verify that DEFAULT_SETTINGS['ai'] always passes validate_section."""
    valid, res = validate_section("ai", DEFAULT_SETTINGS["ai"])
    assert valid is True
    assert res["model_default"] in Config.GROQ_ALLOWED_MODELS
    assert res["model_heavy"] in Config.GROQ_ALLOWED_MODELS
    assert res["monthly_token_budget"] == 0

def test_index_creation_runs_safely():
    """create_indexes should run without raising exceptions even if indexes already exist."""
    from utils.db import create_indexes
    try:
        create_indexes()
    except Exception as e:
        pytest.fail(f"create_indexes raised an unexpected exception: {e}")

