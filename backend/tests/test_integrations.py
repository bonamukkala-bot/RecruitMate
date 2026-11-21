import pytest
import os
import sys
import json
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from bson import ObjectId

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.db import (
    companies_collection,
    team_members_collection,
    company_settings_collection,
    webhooks_collection,
    webhook_logs_collection,
    api_keys_collection,
    jobs_collection,
    candidates_collection,
    audit_logs_collection
)
from utils.auth_helper import generate_token, hash_password
from utils.encryption import encrypt_token, decrypt_token
from utils.webhook_dispatcher import (
    validate_webhook_url,
    compute_webhook_signature,
    deliver_webhook_attempt
)
from utils.api_keys import generate_api_key

TEST_COMPANY_ID = "6afec43af93ed2e3e97091f4"
TEST_OWNER_EMAIL = "test@local.dev"

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup test company
    companies_collection.update_one(
        {"_id": ObjectId(TEST_COMPANY_ID)},
        {
            "$set": {
                "email": TEST_OWNER_EMAIL,
                "company_name": "Acme Corp",
                "full_name": "Acme Admin",
                "is_verified": True
            }
        },
        upsert=True
    )

    # Clean collections for test company
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    webhooks_collection.delete_many({"company_id": TEST_COMPANY_ID})
    webhook_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    api_keys_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    candidates_collection.delete_many({"company_id": TEST_COMPANY_ID})
    team_members_collection.delete_many({"company_id": TEST_COMPANY_ID})
    audit_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})

    yield

    # Clean up after test
    company_settings_collection.delete_many({"company_id": TEST_COMPANY_ID})
    webhooks_collection.delete_many({"company_id": TEST_COMPANY_ID})
    webhook_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    api_keys_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    candidates_collection.delete_many({"company_id": TEST_COMPANY_ID})
    team_members_collection.delete_many({"company_id": TEST_COMPANY_ID})
    audit_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def get_auth_headers(role="owner", email=TEST_OWNER_EMAIL):
    comp_dict = {
        "company_id": TEST_COMPANY_ID,
        "_id": ObjectId(TEST_COMPANY_ID),
        "email": email,
        "company_name": "Acme Corp"
    }

    if role == "owner":
        uid = TEST_COMPANY_ID
    else:
        member_email = f"{role}_{secrets.token_hex(4)}@example.com"
        m_res = team_members_collection.insert_one({
            "company_id": TEST_COMPANY_ID,
            "email": member_email,
            "name": f"Test {role.capitalize()}",
            "role": role,
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        })
        uid = str(m_res.inserted_id)
        comp_dict["email"] = member_email

    token = generate_token(comp_dict, role=role, user_id=uid)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ─────────────────────────────────────────────────────────────────────────────
# 1. Slack Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_slack_url_validation_and_masking(client):
    headers = get_auth_headers("owner")

    # Reject non-Slack URL
    res = client.put("/api/settings/integrations", headers=headers, json={
        "slack_webhook_url": "https://malicious-site.com/webhook",
        "slack_events": {"new_candidate": True}
    })
    assert res.status_code == 400
    assert "https://hooks.slack.com/" in res.get_json()["error"]

    # Reject plain HTTP Slack URL
    res = client.put("/api/settings/integrations", headers=headers, json={
        "slack_webhook_url": "http://hooks.slack.com/services/T00/B00/XXXX"
    })
    assert res.status_code == 400

    # Accept valid Slack URL
    valid_url = "https://hooks.slack.com/services/T12345/B67890/secrettokenabcdef"
    res = client.put("/api/settings/integrations", headers=headers, json={
        "slack_webhook_url": valid_url,
        "slack_events": {"new_candidate": True, "interview_complete": True, "pending_review": False}
    })
    assert res.status_code == 200

    # GET /api/settings/integrations must NEVER return raw Slack URL
    get_res = client.get("/api/settings/integrations", headers=headers)
    assert get_res.status_code == 200
    data = get_res.get_json()["settings"]
    assert data["slack_configured"] is True
    assert "secrettokenabcdef" not in data["slack_webhook_url"]
    assert data["slack_webhook_url"].endswith("cdef")
    assert data["slack_webhook_url_masked"].endswith("cdef")

    # GET /api/settings must also mask it
    all_res = client.get("/api/settings", headers=headers)
    assert all_res.status_code == 200
    all_data = all_res.get_json()["settings"]["integrations"]
    assert all_data["slack_configured"] is True
    assert "secrettokenabcdef" not in all_data["slack_webhook_url"]

    # Submitting back the masked URL preserves the raw URL in DB
    put_masked = client.put("/api/settings/integrations", headers=headers, json={
        "slack_webhook_url": data["slack_webhook_url_masked"],
        "slack_events": {"new_candidate": True, "interview_complete": False, "pending_review": True}
    })
    assert put_masked.status_code == 200

    # Verify raw URL in DB is intact
    db_doc = company_settings_collection.find_one({"company_id": TEST_COMPANY_ID})
    assert db_doc["integrations"]["slack_webhook_url"] == valid_url
    assert db_doc["integrations"]["slack_events"]["pending_review"] is True

def test_slack_test_message_endpoint(client):
    headers = get_auth_headers("owner")

    # When no Slack URL configured
    res = client.post("/api/integrations/slack/test", headers=headers, json={})
    assert res.status_code == 400
    assert "No Slack webhook URL configured" in res.get_json()["error"]

    # With URL in request body or saved in settings
    with patch("utils.slack.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "ok"
        mock_post.return_value = mock_resp

        res = client.post("/api/integrations/slack/test", headers=headers, json={
            "webhook_url": "https://hooks.slack.com/services/T00/B00/test"
        })
        assert res.status_code == 200
        assert res.get_json()["success"] is True
        mock_post.assert_called_once()

# ─────────────────────────────────────────────────────────────────────────────
# 2. SSRF Protection Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_url_ssrf_protection():
    # Reject non-https
    ok, err = validate_webhook_url("http://webhook.site/abc")
    assert not ok
    assert "HTTPS" in err

    # Reject non-standard ports
    ok, err = validate_webhook_url("https://example.com:8443/webhook")
    assert not ok
    assert "port 443" in err

    # Reject loopback IP directly
    ok, err = validate_webhook_url("https://127.0.0.1/webhook")
    assert not ok
    assert any(w in err for w in ("prohibited", "private", "local"))

    # Reject private IPv4 directly
    ok, err = validate_webhook_url("https://192.168.1.1/webhook")
    assert not ok
    assert any(w in err for w in ("prohibited", "private", "local"))

    ok, err = validate_webhook_url("https://10.0.0.5/webhook")
    assert not ok
    assert any(w in err for w in ("prohibited", "private", "local"))

    # Reject AWS/Cloud metadata IP
    ok, err = validate_webhook_url("https://169.254.169.254/latest/meta-data")
    assert not ok
    assert any(w in err for w in ("metadata", "prohibited", "private", "local"))

    # Reject DNS resolving to loopback
    with patch("socket.getaddrinfo") as mock_dns:
        import socket
        # Return loopback IP for hostname evil.local
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]
        ok, err = validate_webhook_url("https://evil.local/webhook")
        assert not ok
        assert any(w in err for w in ("prohibited", "private", "loopback", "local"))

    # Accept valid public IP
    with patch("socket.getaddrinfo") as mock_dns:
        import socket
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        ok, err = validate_webhook_url("https://example.com/webhook")
        assert ok
        assert not err

# ─────────────────────────────────────────────────────────────────────────────
# 3. Outgoing Webhooks Management & Signing
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_crud_and_signing(client):
    headers = get_auth_headers("owner")

    # Create webhook with mock DNS passing
    with patch("socket.getaddrinfo") as mock_dns:
        import socket
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        res = client.post("/api/integrations/webhooks", headers=headers, json={
            "url": "https://example.com/webhook",
            "events": ["candidate.created", "interview.completed"],
            "description": "Production Webhook"
        })
        assert res.status_code == 201
        data = res.get_json()["webhook"]
        assert "secret" in data  # Shown ONCE upon creation
        secret = data["secret"]
        assert len(secret) >= 32
        webhook_id = data["id"]

    # List webhooks: secret MUST NOT be returned
    list_res = client.get("/api/integrations/webhooks", headers=headers)
    assert list_res.status_code == 200
    hooks = list_res.get_json()["webhooks"]
    assert len(hooks) == 1
    assert "secret" not in hooks[0]
    assert hooks[0]["url"] == "https://example.com/webhook"
    assert hooks[0]["events"] == ["candidate.created", "interview.completed"]

    # Test HMAC signature generation
    timestamp = int(time.time())
    payload = {"event": "candidate.created", "data": {"id": "123"}}
    body_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    sig_hex = compute_webhook_signature(secret, body_json, timestamp)
    sig_header = f"t={timestamp},v1={sig_hex}"
    assert sig_header.startswith(f"t={timestamp},v1=")

    # Verify signature format manually
    expected_signed = f"{timestamp}.{body_json}".encode("utf-8")
    expected_hex = hmac.new(secret.encode("utf-8"), expected_signed, hashlib.sha256).hexdigest()
    assert sig_hex == expected_hex

    # Test webhook delivery and delivery log recording
    with patch("socket.getaddrinfo") as mock_dns, patch("requests.post") as mock_req:
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_resp.elapsed.total_seconds.return_value = 0.12
        mock_req.return_value = mock_resp

        hook_doc = {
            "_id": ObjectId(webhook_id),
            "company_id": TEST_COMPANY_ID,
            "url": "https://example.com/webhook",
            "secret": secret
        }
        success, status_code, err_msg = deliver_webhook_attempt(
            webhook=hook_doc,
            event_name="candidate.created",
            payload_json=body_json,
            attempt=1
        )
        assert success is True
        assert status_code == 200

    # Check delivery logs endpoint
    log_res = client.get("/api/integrations/webhooks/deliveries", headers=headers)
    assert log_res.status_code == 200
    logs = log_res.get_json()["deliveries"]
    assert len(logs) == 1
    assert logs[0]["event"] == "candidate.created"
    assert logs[0]["status_code"] == 200
    assert "secret" not in logs[0]

    # Delete webhook
    del_res = client.delete(f"/api/integrations/webhooks/{webhook_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify webhook is deleted
    list_res_after = client.get("/api/integrations/webhooks", headers=headers)
    assert len(list_res_after.get_json()["webhooks"]) == 0

# ─────────────────────────────────────────────────────────────────────────────
# 4. API Keys & Public v1 API
# ─────────────────────────────────────────────────────────────────────────────

def test_api_keys_and_v1_api(client):
    headers = get_auth_headers("owner")

    # 1. Create API key
    res = client.post("/api/integrations/api-keys", headers=headers, json={
        "name": "Zapier Ingestion Key",
        "scopes": ["read:candidates", "write:jobs"],
        "expires_in_days": 30
    })
    assert res.status_code == 201
    key_res = res.get_json()
    raw_key = key_res["key"]
    assert raw_key.startswith("rm_live_")
    key_id = key_res["api_key"]["id"]

    # 2. List API keys: raw key MUST NOT be returned, only prefix
    list_res = client.get("/api/integrations/api-keys", headers=headers)
    assert list_res.status_code == 200
    keys = list_res.get_json()["api_keys"]
    assert len(keys) == 1
    assert "key" not in keys[0]
    assert keys[0]["key_prefix"].startswith("rm_live_")
    assert keys[0]["name"] == "Zapier Ingestion Key"

    # 3. Access public v1 API with the API key
    v1_headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json"
    }

    # Insert a job first
    job_id = str(jobs_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "title": "Backend Engineer",
        "job_title": "Backend Engineer",
        "created_at": datetime.now(timezone.utc)
    }).inserted_id)

    # GET /api/v1/jobs
    jobs_res = client.get("/api/v1/jobs", headers=v1_headers)
    assert jobs_res.status_code == 200
    assert jobs_res.get_json()["success"] is True

    # POST /api/v1/candidates
    with patch("routes.v1.dispatch_webhook_event") as mock_hook, \
         patch("routes.v1.send_slack_notification") as mock_slack:
        cand_res = client.post("/api/v1/candidates", headers=v1_headers, json={
            "job_id": job_id,
            "candidate_name": "John Doe",
            "candidate_email": "johndoe@example.com",
            "candidate_phone": "+1234567890",
            "resume_text": "Experienced Python/Flask engineer with MongoDB."
        })
        assert cand_res.status_code == 201
        assert cand_res.get_json()["candidate_id"] is not None
        # Dispatched candidate.created webhook and slack alert
        mock_hook.assert_called_once()
        mock_slack.assert_called_once()

    # 4. Scope enforcement: create key with only "read:candidates"
    res_limited = client.post("/api/integrations/api-keys", headers=headers, json={
        "name": "Candidate Read Only",
        "scopes": ["read:candidates"]
    })
    limited_key = res_limited.get_json()["key"]
    lim_headers = {"Authorization": f"Bearer {limited_key}"}

    # Attempting to access an endpoint requiring "write:jobs" fails with 403
    jobs_forbidden = client.get("/api/v1/jobs", headers=lim_headers)
    assert jobs_forbidden.status_code == 403
    assert "Insufficient scope" in jobs_forbidden.get_json()["error"]

    # 5. API keys cannot access internal endpoints (e.g. /api/settings)
    settings_res = client.get("/api/settings", headers=v1_headers)
    assert settings_res.status_code == 401

    # 6. Revocation: DELETE key
    del_res = client.delete(f"/api/integrations/api-keys/{key_id}", headers=headers)
    assert del_res.status_code == 200

    # Using revoked key returns 401
    revoked_res = client.get("/api/v1/jobs", headers=v1_headers)
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.get_json()["error"]

# ─────────────────────────────────────────────────────────────────────────────
# 5. Google Calendar Status & Token Encryption
# ─────────────────────────────────────────────────────────────────────────────

def test_google_calendar_status_and_encryption(client):
    headers = get_auth_headers("owner")

    # Status returns disabled by default
    res = client.get("/api/integrations/google/status", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["enabled"] is False
    assert data["connected"] is False

    # Token encryption & decryption round-trip
    sample_token = "ya29.a0AfH6SMD_secret_google_refresh_token_12345"
    enc = encrypt_token(sample_token)
    assert enc != sample_token
    dec = decrypt_token(enc)
    assert dec == sample_token

    # Disconnect returns 200
    disc_res = client.post("/api/integrations/google/disconnect", headers=headers)
    assert disc_res.status_code == 200

# ─────────────────────────────────────────────────────────────────────────────
# 6. RBAC Role Enforcement
# ─────────────────────────────────────────────────────────────────────────────

def test_role_enforcement_on_integrations(client):
    # Recruiter cannot create webhooks or API keys
    recruiter_headers = get_auth_headers("recruiter")
    res1 = client.post("/api/integrations/webhooks", headers=recruiter_headers, json={
        "url": "https://example.com/webhook",
        "events": ["candidate.created"]
    })
    assert res1.status_code == 403

    res2 = client.post("/api/integrations/api-keys", headers=recruiter_headers, json={
        "name": "Key",
        "scopes": ["read:candidates"]
    })
    assert res2.status_code == 403

    # Viewer cannot write
    viewer_headers = get_auth_headers("viewer")
    res3 = client.put("/api/settings/integrations", headers=viewer_headers, json={
        "slack_webhook_url": "https://hooks.slack.com/services/T00/B00/test"
    })
    assert res3.status_code == 403

    # Viewer can read integrations settings
    res4 = client.get("/api/settings/integrations", headers=viewer_headers)
    assert res4.status_code == 200

# ─────────────────────────────────────────────────────────────────────────────
# 7. Production DB Regression Test
# ─────────────────────────────────────────────────────────────────────────────

def test_production_db_regression_no_500(client):
    headers = get_auth_headers("owner")

    with patch.object(Config, "DB_NAME", "recruitmate"):
        put_res = client.put("/api/settings/integrations", headers=headers, json={
            "slack_webhook_url": "https://hooks.slack.com/services/T00/B00/safetest",
            "slack_events": {"new_candidate": True}
        })
        assert put_res.status_code == 200, f"Expected 200 on prod DB, got {put_res.status_code}: {put_res.data}"

        reset_res = client.post("/api/settings/integrations/reset", headers=headers)
        assert reset_res.status_code == 200, f"Expected 200 on prod DB, got {reset_res.status_code}: {reset_res.data}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. API Key Creation & Validation Regression Test
# ─────────────────────────────────────────────────────────────────────────────

def test_api_key_creation_validation_and_lifecycle(client):
    headers_owner = get_auth_headers("owner")
    headers_recruiter = get_auth_headers("recruiter")

    # 1. Non-admin (recruiter) role cannot create key
    res_rec = client.post("/api/integrations/api-keys", headers=headers_recruiter, json={
        "name": "Unauthorized Key",
        "scopes": ["write:jobs"]
    })
    assert res_rec.status_code == 403
    assert "Permission denied" in res_rec.get_json()["error"]

    # 2. Empty name validation
    res_empty_name = client.post("/api/integrations/api-keys", headers=headers_owner, json={
        "name": "   ",
        "scopes": ["write:jobs"]
    })
    assert res_empty_name.status_code == 400
    assert "API key name is required" in res_empty_name.get_json()["error"]

    # 3. Empty scopes validation
    res_empty_scopes = client.post("/api/integrations/api-keys", headers=headers_owner, json={
        "name": "Valid Name",
        "scopes": []
    })
    assert res_empty_scopes.status_code == 400
    assert "At least one scope" in res_empty_scopes.get_json()["error"]

    # 4. Invalid scopes validation
    res_inv_scopes = client.post("/api/integrations/api-keys", headers=headers_owner, json={
        "name": "Valid Name",
        "scopes": ["invalid:scope", "write:jobs"]
    })
    assert res_inv_scopes.status_code == 400
    assert "Invalid scopes" in res_inv_scopes.get_json()["error"]

    # 5. Successful creation with custom expiry
    res_create = client.post("/api/integrations/api-keys", headers=headers_owner, json={
        "name": "Careers Portal Ingestion",
        "scopes": ["read:candidates", "write:jobs"],
        "expires_in_days": 90
    })
    assert res_create.status_code == 201
    body = res_create.get_json()
    assert body["success"] is True
    full_key = body["key"]
    assert full_key.startswith("rm_live_")
    key_info = body["api_key"]
    key_id = key_info["id"]
    assert key_info["name"] == "Careers Portal Ingestion"
    assert key_info["key_prefix"].startswith("rm_live_")
    assert key_info["scopes"] == ["read:candidates", "write:jobs"]
    assert key_info["expires_at"] is not None

    # Verify only prefix and hash are stored in DB, never full raw key
    db_doc = api_keys_collection.find_one({"_id": ObjectId(key_id)})
    assert db_doc is not None
    assert db_doc["key_prefix"] == key_info["key_prefix"]
    assert db_doc["key_hash"] is not None
    assert "key" not in db_doc
    assert full_key not in db_doc.values()

    # 6. Verify key works on /api/v1/jobs
    v1_headers = {"Authorization": f"Bearer {full_key}"}
    jobs_res = client.get("/api/v1/jobs", headers=v1_headers)
    assert jobs_res.status_code == 200
    assert jobs_res.get_json()["success"] is True

    # 7. Verify key is refused on /api/settings (401)
    settings_res = client.get("/api/settings", headers=v1_headers)
    assert settings_res.status_code == 401

    # 8. Revoke key
    del_res = client.delete(f"/api/integrations/api-keys/{key_id}", headers=headers_owner)
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True

    # 9. Key is refused on /api/v1/jobs after revocation (401)
    revoked_res = client.get("/api/v1/jobs", headers=v1_headers)
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.get_json()["error"]
