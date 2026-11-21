import pytest
import os
import sys
import io
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.db import (
    team_members_collection,
    companies_collection,
    audit_logs_collection,
    company_settings_collection,
    candidates_collection,
    pipeline_collection,
    jobs_collection
)
from utils.auth_helper import generate_token, hash_password
from utils.retention import purge_expired_candidates

TEST_COMPANY_ID = "6afec43af93ed2e3e97091f4"
TEST_OWNER_EMAIL = "test@local.dev"

def generate_valid_image(fmt="PNG"):
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color=(50, 120, 200))
    img.save(buf, format=fmt)
    return buf.getvalue()

@pytest.fixture(autouse=True)
def clean_db():
    # Ensure test owner exists
    companies_collection.update_one(
        {"email": TEST_OWNER_EMAIL},
        {
            "$set": {
                "company_name": "Test Company",
                "full_name": "Test Owner",
                "password": hash_password("Password123!"),
                "is_verified": True
            }
        },
        upsert=True
    )
    # Clean collections for test company
    team_members_collection.delete_many({"company_id": TEST_COMPANY_ID})
    audit_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    candidates_collection.delete_many({"company_id": TEST_COMPANY_ID})
    pipeline_collection.delete_many({"company_id": TEST_COMPANY_ID})
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})

    yield

    team_members_collection.delete_many({"company_id": TEST_COMPANY_ID})
    audit_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    candidates_collection.delete_many({"company_id": TEST_COMPANY_ID})
    pipeline_collection.delete_many({"company_id": TEST_COMPANY_ID})
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def make_token(role="owner", user_id=None, email=TEST_OWNER_EMAIL):
    payload = {
        "company_id": TEST_COMPANY_ID,
        "company_name": "Test Company",
        "email": email
    }
    return generate_token(payload, role=role, user_id=user_id or TEST_COMPANY_ID)

def create_member(role="recruiter", email=None):
    email = email or f"{role}_{secrets.token_hex(4)}@example.com"
    member_id = str(team_members_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "email": email,
        "name": f"Test {role.capitalize()}",
        "role": role,
        "status": "active",
        "created_at": datetime.now(timezone.utc)
    }).inserted_id)
    return member_id, email

# ── 1. Logo Upload & Validation Tests ─────────────────────────────────────────

def test_logo_upload_valid_png_and_jpeg(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Valid PNG
    png_bytes = generate_valid_image("PNG")
    data = {"logo": (io.BytesIO(png_bytes), "brand.png")}
    res = client.post("/api/settings/company/logo", data=data, content_type="multipart/form-data", headers=headers)
    assert res.status_code == 200
    res_data = res.get_json()
    assert res_data["success"] is True
    assert res_data["logo"].startswith("data:image/png;base64,")

    # Valid JPEG
    jpg_bytes = generate_valid_image("JPEG")
    data = {"logo": (io.BytesIO(jpg_bytes), "brand.jpg")}
    res = client.post("/api/settings/company/logo", data=data, content_type="multipart/form-data", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["logo"].startswith("data:image/jpeg;base64,")

    # Delete logo
    res_del = client.delete("/api/settings/company/logo", headers=headers)
    assert res_del.status_code == 200
    assert res_del.get_json()["logo"] == ""

def test_logo_upload_oversize_rejected(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Over 1MB (1,048,577 bytes)
    big_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 1048580
    data = {"logo": (io.BytesIO(big_bytes), "oversize.png")}
    res = client.post("/api/settings/company/logo", data=data, content_type="multipart/form-data", headers=headers)
    assert res.status_code == 400
    assert "exceeds maximum size" in res.get_json()["error"]

def test_logo_upload_fake_extension_and_non_image_rejected(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Plain text disguised as .png
    fake_png = b"Hello, this is just a text file renamed to logo.png"
    data = {"logo": (io.BytesIO(fake_png), "malicious.png")}
    res = client.post("/api/settings/company/logo", data=data, content_type="multipart/form-data", headers=headers)
    assert res.status_code == 400
    assert "Invalid image format" in res.get_json()["error"]

    # Script file disguised as .jpg
    fake_jpg = b"<?php echo 'hacked'; ?>"
    data = {"logo": (io.BytesIO(fake_jpg), "script.jpg")}
    res = client.post("/api/settings/company/logo", data=data, content_type="multipart/form-data", headers=headers)
    assert res.status_code == 400

def test_logo_upload_role_enforcement(client):
    # Recruiter and Viewer should be forbidden (admin+ only)
    recruiter_id, recruiter_email = create_member("recruiter")
    recruiter_token = make_token("recruiter", user_id=recruiter_id, email=recruiter_email)

    png_bytes = generate_valid_image("PNG")
    data = {"logo": (io.BytesIO(png_bytes), "brand.png")}
    res = client.post("/api/settings/company/logo", data=data, content_type="multipart/form-data",
                      headers={"Authorization": f"Bearer {recruiter_token}"})
    assert res.status_code == 403

# ── 2. Company & Privacy Settings Validation ──────────────────────────────────

def test_company_settings_validation(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Invalid URL
    res = client.put("/api/settings/company", json={"website": "not-a-valid-url"}, headers=headers)
    assert res.status_code == 400

    # Invalid email
    res = client.put("/api/settings/company", json={"support_email": "invalid-email"}, headers=headers)
    assert res.status_code == 400

    # Invalid hex
    res = client.put("/api/settings/company", json={"brand_color": "12345"}, headers=headers)
    assert res.status_code == 400

    # Valid
    valid_payload = {
        "display_name": "Acme Global",
        "website": "https://acme.example.com",
        "support_email": "support@acme.example.com",
        "brand_color": "#0ea5e9"
    }
    res = client.put("/api/settings/company", json=valid_payload, headers=headers)
    assert res.status_code == 200

    get_res = client.get("/api/settings/company", headers=headers)
    assert get_res.status_code == 200
    assert get_res.get_json()["settings"]["display_name"] == "Acme Global"
    assert get_res.get_json()["settings"]["brand_color"] == "#0ea5e9"

def test_privacy_settings_validation(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Invalid retention days (e.g. 10 days, must be 0 or 30-1095)
    res = client.put("/api/settings/privacy", json={"data_retention_days": 10}, headers=headers)
    assert res.status_code == 400

    # Valid retention days
    res = client.put("/api/settings/privacy", json={"data_retention_days": 90, "record_proctoring_events": False}, headers=headers)
    assert res.status_code == 200

    get_res = client.get("/api/settings/privacy", headers=headers)
    assert get_res.status_code == 200
    assert get_res.get_json()["settings"]["data_retention_days"] == 90
    assert get_res.get_json()["settings"]["record_proctoring_events"] is False

# ── 3. Candidate Data Export Tests ───────────────────────────────────────────

def test_candidate_data_export(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    candidate_id = str(candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Alice Smith",
        "candidate_email": "alice@example.com",
        "status": "shortlisted",
        "match_score": 88,
        "parsed_resume": {"skills": ["Python", "Flask"]},
        "evaluation": {"overall_score": 85},
        "interview_answers": [{"question": "Q1", "answer": "A1"}],
        "created_at": datetime.now(timezone.utc)
    }).inserted_id)

    # Insert a pipeline log
    pipeline_collection.insert_one({
        "candidate_id": candidate_id,
        "company_id": TEST_COMPANY_ID,
        "stage": "interview",
        "status": "success",
        "message": "Interview completed"
    })

    # Owner export
    res = client.get(f"/api/privacy/candidates/{candidate_id}/export", headers=headers)
    assert res.status_code == 200
    export_bundle = res.get_json()["export"]
    assert export_bundle["profile"]["candidate_name"] == "Alice Smith"
    assert export_bundle["scores"]["match_score"] == 88
    assert len(export_bundle["pipeline_logs"]) == 1

    # Recruiter export -> 403
    recruiter_id, recruiter_email = create_member("recruiter")
    rec_token = make_token("recruiter", user_id=recruiter_id, email=recruiter_email)
    res_rec = client.get(f"/api/privacy/candidates/{candidate_id}/export",
                         headers={"Authorization": f"Bearer {rec_token}"})
    assert res_rec.status_code == 403

# ── 4. Candidate Hard Deletion Tests ──────────────────────────────────────────

def test_candidate_hard_deletion_and_audit_hash(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    cand_email = "delete_me@example.com"
    candidate_id = str(candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Bob Target",
        "candidate_email": cand_email,
        "status": "rejected",
        "created_at": datetime.now(timezone.utc)
    }).inserted_id)

    pipeline_collection.insert_one({
        "candidate_id": candidate_id,
        "company_id": TEST_COMPANY_ID,
        "stage": "screener",
        "status": "rejected"
    })

    # Delete candidate
    res = client.delete(f"/api/candidates/{candidate_id}/data", headers=headers)
    assert res.status_code == 200

    # Verify candidate document is gone
    assert candidates_collection.find_one({"_id": ObjectId(candidate_id)}) is None
    # Verify pipeline logs are cascaded
    assert pipeline_collection.find_one({"candidate_id": candidate_id}) is None

    # Verify audit log: candidate_id and email_hash present, raw email NEVER stored
    expected_hash = hashlib.sha256(cand_email.encode("utf-8")).hexdigest()
    audit_entry = audit_logs_collection.find_one({
        "company_id": TEST_COMPANY_ID,
        "action": "candidate.hard_delete"
    })
    assert audit_entry is not None
    assert audit_entry.get("email_hash") == expected_hash
    # Raw email must not appear anywhere in audit entry
    assert cand_email not in str(audit_entry)

# ── 5. Retention Purge Tests ──────────────────────────────────────────────────

def test_retention_purge_dry_run_and_execute(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Set retention to 60 days
    client.put("/api/settings/privacy", json={"data_retention_days": 60}, headers=headers)

    # Candidate A: 10 days old (should stay)
    fresh_id = str(candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Fresh Cand",
        "candidate_email": "fresh@example.com",
        "created_at": datetime.now(timezone.utc) - timedelta(days=10)
    }).inserted_id)

    # Candidate B: 90 days old (should be purged)
    expired_id = str(candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "candidate_name": "Old Cand",
        "candidate_email": "old@example.com",
        "created_at": datetime.now(timezone.utc) - timedelta(days=90)
    }).inserted_id)

    pipeline_collection.insert_one({
        "candidate_id": expired_id,
        "company_id": TEST_COMPANY_ID,
        "stage": "interview"
    })

    # Dry-run via API
    res_dry = client.post("/api/privacy/purge-expired?dry_run=true", headers=headers)
    assert res_dry.status_code == 200
    dry_data = res_dry.get_json()
    assert dry_data["dry_run"] is True
    assert dry_data["deleted_candidates"] == 1
    # Check that candidate still exists
    assert candidates_collection.find_one({"_id": ObjectId(expired_id)}) is not None

    # Execute purge via API
    res_exec = client.post("/api/privacy/purge-expired?dry_run=false", headers=headers)
    assert res_exec.status_code == 200
    exec_data = res_exec.get_json()
    assert exec_data["dry_run"] is False
    assert exec_data["deleted_candidates"] == 1

    # Check that expired candidate is gone and fresh candidate remains
    assert candidates_collection.find_one({"_id": ObjectId(expired_id)}) is None
    assert pipeline_collection.find_one({"candidate_id": expired_id}) is None
    assert candidates_collection.find_one({"_id": ObjectId(fresh_id)}) is not None

def test_purge_script_production_guard():
    # Test standalone script guard directly
    from utils.settings import assert_safe_db
    import pytest

    orig_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"
        with pytest.raises(RuntimeError) as exc_info:
            assert_safe_db()
        assert "Connected to production database" in str(exc_info.value)
    finally:
        Config.DB_NAME = orig_db

# ── 6. Candidate Consent & Proctoring Storage Tests ───────────────────────────

def test_candidate_consent_flow_and_proctoring_recording(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # Set proctoring event recording to False in privacy settings
    client.put("/api/settings/privacy", json={"record_proctoring_events": False}, headers=headers)

    job_id = str(jobs_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "title": "Software Engineer",
        "description": "Python role"
    }).inserted_id)

    token = "test-consent-token-12345"
    candidate_id = str(candidates_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "job_id": job_id,
        "candidate_name": "Charlie Consent",
        "candidate_email": "charlie@example.com",
        "interview_token": token,
        "interview_status": "invited",
        "created_at": datetime.now(timezone.utc)
    }).inserted_id)

    # GET interview details returns consent requirements
    get_res = client.get(f"/api/pipeline/interview/public/{token}")
    assert get_res.status_code == 200
    int_data = get_res.get_json()
    assert int_data["consent_required"] is True
    assert "consent_text" in int_data
    assert int_data["record_proctoring_events"] is False

    # Submit without consent -> 400
    res_no_consent = client.post(f"/api/pipeline/interview/public/{token}/submit", json={
        "qa_pairs": [{"question": "Q1", "answer": "A1"}],
        "terminated": True,
        "termination_reason": "early exit"
    })
    assert res_no_consent.status_code == 400
    assert "Candidate consent is required" in res_no_consent.get_json()["error"]

    # Record consent via endpoint
    res_record = client.post(f"/api/pipeline/interview/public/{token}/consent", json={
        "consent_accepted": True,
        "consent_text": "Sample consent agreement"
    })
    assert res_record.status_code == 200

    cand_after_consent = candidates_collection.find_one({"_id": ObjectId(candidate_id)})
    assert cand_after_consent.get("consent_accepted") is True
    assert cand_after_consent.get("consented_at") is not None

    # Submit interview with integrity log
    res_submit = client.post(f"/api/pipeline/interview/public/{token}/submit", json={
        "qa_pairs": [{"question": "Q1", "answer": "A1"}],
        "integrity_log": [{"type": "tab_switch", "at_seconds": 15}],
        "terminated": True,
        "termination_reason": "test complete"
    })
    assert res_submit.status_code == 200

    # Check candidate document: integrity_log should be empty because record_proctoring_events=False
    cand_after_sub = candidates_collection.find_one({"_id": ObjectId(candidate_id)})
    assert cand_after_sub.get("integrity_log") == []

# ── 7. Production DB Guard Regression Tests ───────────────────────────────────

def test_production_db_guard_regression(client):
    owner_token = make_token("owner")
    headers = {"Authorization": f"Bearer {owner_token}"}

    orig_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"

        # PUT company settings
        res = client.put("/api/settings/company", json={"display_name": "Prod Corp"}, headers=headers)
        assert res.status_code == 200

        # POST company settings reset
        res = client.post("/api/settings/company/reset", headers=headers)
        assert res.status_code == 200

        # PUT privacy settings
        res = client.put("/api/settings/privacy", json={"data_retention_days": 180}, headers=headers)
        assert res.status_code == 200

        # POST privacy settings reset
        res = client.post("/api/settings/privacy/reset", headers=headers)
        assert res.status_code == 200

        # Purge endpoint (request handler) must NOT raise 500 from assert_safe_db
        res_purge = client.post("/api/privacy/purge-expired?dry_run=true", headers=headers)
        assert res_purge.status_code == 200
    finally:
        Config.DB_NAME = orig_db
