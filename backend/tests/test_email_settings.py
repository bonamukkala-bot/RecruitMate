import pytest
import os
import sys
import unittest.mock as mock
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.settings import DEFAULT_SETTINGS, validate_section, get_settings
from utils.email_renderer import (
    validate_template_variables,
    render_template,
    build_email_html,
    ALLOWED_TEMPLATE_VARS
)
from utils.db import company_settings_collection, companies_collection
from utils.auth_helper import generate_token
from agents.email_sender import send_owner_notification, send_interview_link_email

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_headers():
    test_company = {
        "_id": "650000000000000000000099",
        "company_id": "test_co_email_001",
        "email": "test@local.dev",
        "company_name": "Acme Test Corp"
    }
    token = generate_token(test_company)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ── 1. Template variable validation tests ──────────────────────────────────────
def test_validate_template_variables_allowed():
    """Whitelisted variables are valid."""
    text = "Hello {candidate_name}, welcome to {company_name} for {job_title} on {date}. Next: {next_step}."
    is_valid, err = validate_template_variables(text)
    assert is_valid is True
    assert err == ""

def test_validate_template_variables_unknown_rejected():
    """Non-whitelisted variables are rejected with an informative error message."""
    text = "Hello {candidate_name}, your password is {password}!"
    is_valid, err = validate_template_variables(text)
    assert is_valid is False
    assert "{password}" in err
    assert "Allowed variables" in err

def test_validate_template_variables_complex_injection():
    """Expressions or arbitrary attribute lookups are rejected."""
    text = "Hello {candidate.__class__.__name__}"
    is_valid, err = validate_template_variables(text)
    assert is_valid is False

# ── 2. Safe rendering & HTML escaping tests ───────────────────────────────────
def test_render_template_basic_substitution():
    """Allowed tokens are correctly replaced with context values."""
    tmpl = "Dear {candidate_name}, your interview for {job_title} at {company_name} is set."
    ctx = {
        "candidate_name": "Jane Doe",
        "job_title": "Staff Architect",
        "company_name": "TechCorp"
    }
    rendered = render_template(tmpl, ctx, escape_html=False)
    assert rendered == "Dear Jane Doe, your interview for Staff Architect at TechCorp is set."

def test_render_template_html_escaping_xss_protection():
    """Context values containing HTML/script tags are properly escaped when escape_html=True."""
    tmpl = "Welcome {candidate_name} to {company_name}!"
    ctx = {
        "candidate_name": "<script>alert('XSS')</script>",
        "company_name": "O'Reilly & Sons <img src=x onerror=alert(1)>"
    }
    rendered = render_template(tmpl, ctx, escape_html=True)
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;" in rendered
    assert "&lt;img" in rendered

def test_render_template_missing_keys_fallback_to_empty():
    """Missing context keys are replaced with empty string, no exception raised."""
    tmpl = "Hello {candidate_name}, your date is {date}."
    ctx = {"candidate_name": "John"}
    rendered = render_template(tmpl, ctx)
    assert rendered == "Hello John, your date is ."

# ── 3. Section validation tests ───────────────────────────────────────────────
def test_validate_email_section_valid():
    """Valid email settings payload passes schema validation."""
    data = {
        "sender_name": "Recruit Talent Team",
        "reply_to": "recruiting@testcorp.com",
        "templates": {
            "interview_invite": {
                "subject": "Invite: {job_title}",
                "body": "Hi {candidate_name}, welcome to {company_name}!"
            }
        },
        "notifications": {
            "notify_on_new_candidate": False,
            "daily_digest": True
        }
    }
    is_valid, validated_data = validate_section("email", data)
    assert is_valid is True
    assert validated_data["sender_name"] == "Recruit Talent Team"
    assert validated_data["reply_to"] == "recruiting@testcorp.com"
    assert validated_data["notifications"]["notify_on_new_candidate"] is False
    assert validated_data["notifications"]["daily_digest"] is True

def test_validate_email_section_invalid_reply_to():
    """Invalid email in reply_to fails validation."""
    data = {"reply_to": "not-an-email"}
    is_valid, err = validate_section("email", data)
    assert is_valid is False
    assert "reply_to must be a valid email" in err

def test_validate_email_section_subject_length_limit():
    """Subject longer than 150 characters is rejected."""
    long_subject = "A" * 151
    data = {
        "templates": {
            "interview_invite": {
                "subject": long_subject,
                "body": "Valid body text"
            }
        }
    }
    is_valid, err = validate_section("email", data)
    assert is_valid is False
    assert "between 1 and 150 characters" in err

def test_validate_email_section_body_length_limit():
    """Body longer than 5000 characters is rejected."""
    long_body = "B" * 5001
    data = {
        "templates": {
            "rejection": {
                "subject": "Application Update",
                "body": long_body
            }
        }
    }
    is_valid, err = validate_section("email", data)
    assert is_valid is False
    assert "between 1 and 5000 characters" in err

def test_validate_email_section_unknown_template_var_rejected():
    """Template containing unknown variable fails section validation."""
    data = {
        "templates": {
            "shortlist": {
                "subject": "Status for {candidate_name}",
                "body": "Your salary is {candidate_salary}."
            }
        }
    }
    is_valid, err = validate_section("email", data)
    assert is_valid is False
    assert "Unknown template variable '{candidate_salary}'" in err

# ── 4. Preview Endpoint Tests ─────────────────────────────────────────────────
def test_email_preview_endpoint(client, auth_headers):
    """POST /api/settings/email/preview renders valid template."""
    res = client.post(
        "/api/settings/email/preview",
        headers=auth_headers,
        json={
            "template_type": "interview_invite",
            "subject": "Interview for {job_title} at {company_name}",
            "body": "Hello {candidate_name}, you have been selected for {job_title}!"
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    preview = data["preview"]
    assert "Senior Python Engineer" in preview["subject"]
    assert "Alex Mercer" in preview["body"]
    assert "Start Your Interview" in preview["html"]

def test_email_preview_endpoint_rejects_unknown_var(client, auth_headers):
    """POST /api/settings/email/preview rejects unknown template placeholders."""
    res = client.post(
        "/api/settings/email/preview",
        headers=auth_headers,
        json={
            "template_type": "rejection",
            "body": "Dear {candidate_name}, {invalid_token}"
        }
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "{invalid_token}" in data["error"]

def test_email_preview_otp_footer(client, auth_headers):
    """POST /api/settings/email/preview renders OTP email with custom footer."""
    res = client.post(
        "/api/settings/email/preview",
        headers=auth_headers,
        json={
            "template_type": "otp_footer",
            "body": "Expires in 10 minutes. Keep secret."
        }
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "849201" in data["preview"]["html"]
    assert "Expires in 10 minutes. Keep secret." in data["preview"]["html"]

# ── 5. Send Test Email Endpoint & Rate Limiting ───────────────────────────────
def test_send_test_email_success_and_rate_limit(client, auth_headers):
    """POST /api/settings/email/send-test succeeds and enforces 5/hour rate limit."""
    mock_resp = mock.MagicMock()
    mock_resp.message_id = "test-msg-12345"

    with mock.patch("sib_api_v3_sdk.TransactionalEmailsApi.send_transac_email", return_value=mock_resp), \
         mock.patch.object(Config, "BREVO_API_KEY", "mock-brevo-key"):

        from routes.settings import _TEST_EMAIL_HISTORY
        _TEST_EMAIL_HISTORY.clear()

        # Send up to limit (5)
        for i in range(5):
            res = client.post(
                "/api/settings/email/send-test",
                headers=auth_headers,
                json={"template_type": "interview_invite"}
            )
            assert res.status_code == 200
            assert res.get_json()["success"] is True

        # 6th attempt within the hour must return 429
        res_limit = client.post(
            "/api/settings/email/send-test",
            headers=auth_headers,
            json={"template_type": "interview_invite"}
        )
        assert res_limit.status_code == 429
        assert "Rate limit exceeded" in res_limit.get_json()["error"]

# ── 6. Owner Notification Logic ───────────────────────────────────────────────
def test_send_owner_notification_disabled_skip():
    """send_owner_notification skips sending when disabled in settings."""
    company_id = "test_co_email_001"
    # Ensure setting has notify_on_new_candidate = False
    company_settings_collection.update_one(
        {"company_id": company_id},
        {"$set": {"email.notifications.notify_on_new_candidate": False}},
        upsert=True
    )

    res = send_owner_notification(
        company_id=company_id,
        event_type="new_candidate",
        details={"candidate_name": "Sam Sample", "job_title": "Developer", "match_score": 85}
    )
    assert res.get("skipped") is True
    assert res.get("reason") == "Notification disabled"

# ── 7. Regression Test: Production DB Name Guard Applies ONLY to Scripts ──────
def test_settings_email_routes_allow_production_db_name(client, auth_headers):
    """
    CRITICAL REGRESSION TEST:
    Verifies that PUT /api/settings/email and POST /api/settings/email/reset
    return 200 (not 500) even when Config.DB_NAME is 'recruitmate'.
    """
    original_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"

        # 1. Test PUT
        put_res = client.put(
            "/api/settings/email",
            headers=auth_headers,
            json={"sender_name": "Recruit Production Test"}
        )
        assert put_res.status_code == 200, f"Expected 200, got {put_res.status_code}: {put_res.get_data(as_text=True)}"

        # 2. Test Reset
        reset_res = client.post(
            "/api/settings/email/reset",
            headers=auth_headers
        )
        assert reset_res.status_code == 200, f"Expected 200, got {reset_res.status_code}: {reset_res.get_data(as_text=True)}"

    finally:
        Config.DB_NAME = original_db
