import pytest
import os
import sys
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from bson import ObjectId

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from config import Config
from utils.db import (
    team_members_collection,
    companies_collection,
    audit_logs_collection,
    jobs_collection
)
from utils.auth_helper import generate_token, hash_password

TEST_COMPANY_ID = "6afec43af93ed2e3e97091f4"
TEST_OWNER_EMAIL = "test@local.dev"

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
    # Clean team members, audit logs and jobs for test company
    team_members_collection.delete_many({"company_id": TEST_COMPANY_ID})
    audit_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})
    jobs_collection.delete_many({"company_id": TEST_COMPANY_ID})

    yield

    team_members_collection.delete_many({"company_id": TEST_COMPANY_ID})
    audit_logs_collection.delete_many({"company_id": TEST_COMPANY_ID})
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

def create_member(role="recruiter", email=None, status="active"):
    email = email or f"{role}_{secrets.token_hex(4)}@example.com"
    member_id = str(team_members_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "email": email,
        "name": f"Test {role.capitalize()}",
        "role": role,
        "status": status,
        "password_hash": hash_password("Password123!"),
        "created_at": datetime.now(timezone.utc)
    }).inserted_id)
    token = make_token(role=role, user_id=member_id, email=email)
    return member_id, token, email

def auth_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ── 1. Role Hierarchy & Protected Endpoints ──────────────────────────────────
def test_role_hierarchy_settings_protection(client):
    owner_tok = make_token(role="owner", user_id=TEST_COMPANY_ID, email=TEST_OWNER_EMAIL)
    _, admin_tok, _ = create_member(role="admin")
    _, recruiter_tok, _ = create_member(role="recruiter")
    _, viewer_tok, _ = create_member(role="viewer")

    payload = {"duration_minutes": 45, "question_count": 10}

    # Viewer cannot update settings (403)
    res_v = client.put("/api/settings/interview", json=payload, headers=auth_headers(viewer_tok))
    assert res_v.status_code == 403
    assert "permission denied" in res_v.get_json()["error"].lower()

    # Recruiter cannot update settings (403)
    res_r = client.put("/api/settings/interview", json=payload, headers=auth_headers(recruiter_tok))
    assert res_r.status_code == 403

    # Admin CAN update settings (200)
    res_a = client.put("/api/settings/interview", json=payload, headers=auth_headers(admin_tok))
    assert res_a.status_code == 200

    # Owner CAN update settings (200)
    res_o = client.put("/api/settings/interview", json=payload, headers=auth_headers(owner_tok))
    assert res_o.status_code == 200

# ── 2. Data Deletion (Owner Only) ─────────────────────────────────────────────
def test_data_deletion_owner_only(client):
    owner_tok = make_token(role="owner", user_id=TEST_COMPANY_ID, email=TEST_OWNER_EMAIL)
    _, admin_tok, _ = create_member(role="admin")
    _, recruiter_tok, _ = create_member(role="recruiter")
    _, viewer_tok, _ = create_member(role="viewer")

    job_id = str(jobs_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "title": "Software Engineer",
        "status": "active"
    }).inserted_id)

    # Viewer -> 403
    res_v = client.delete(f"/api/jobs/{job_id}", headers=auth_headers(viewer_tok))
    assert res_v.status_code == 403

    # Recruiter -> 403
    res_r = client.delete(f"/api/jobs/{job_id}", headers=auth_headers(recruiter_tok))
    assert res_r.status_code == 403

    # Admin -> 403 (Owner only!)
    res_a = client.delete(f"/api/jobs/{job_id}", headers=auth_headers(admin_tok))
    assert res_a.status_code == 403

    # Owner -> 200
    res_o = client.delete(f"/api/jobs/{job_id}", headers=auth_headers(owner_tok))
    assert res_o.status_code == 200
    assert jobs_collection.find_one({"_id": ObjectId(job_id)}) is None

# ── 3. Recruiter Endpoints (Jobs & Candidates) ────────────────────────────────
def test_recruiter_endpoints_permission(client):
    _, recruiter_tok, _ = create_member(role="recruiter")
    _, viewer_tok, _ = create_member(role="viewer")

    job_id = str(jobs_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "title": "Backend Developer",
        "status": "active"
    }).inserted_id)

    # Viewer cannot update job status (403)
    res_v = client.patch(f"/api/jobs/{job_id}/status", json={"status": "closed"}, headers=auth_headers(viewer_tok))
    assert res_v.status_code == 403

    # Recruiter CAN update job status (200)
    res_r = client.patch(f"/api/jobs/{job_id}/status", json={"status": "closed"}, headers=auth_headers(recruiter_tok))
    assert res_r.status_code == 200
    assert jobs_collection.find_one({"_id": ObjectId(job_id)})["status"] == "closed"

# ── 4. Viewer Read-Only Access ────────────────────────────────────────────────
def test_viewer_read_only_access(client):
    _, viewer_tok, _ = create_member(role="viewer")

    # Viewer can read settings
    res_settings = client.get("/api/settings", headers=auth_headers(viewer_tok))
    assert res_settings.status_code == 200

    # Viewer can read jobs
    res_jobs = client.get("/api/jobs/", headers=auth_headers(viewer_tok))
    assert res_jobs.status_code == 200

    # Viewer can read team roster
    res_team = client.get("/api/settings/team/members", headers=auth_headers(viewer_tok))
    assert res_team.status_code == 200

# ── 5. Invite Member Flow & Hash Storage ──────────────────────────────────────
def test_invite_member_flow(client):
    _, admin_tok, _ = create_member(role="admin")
    invite_email = "newhire@example.com"

    res = client.post("/api/settings/team/invite", json={
        "email": invite_email,
        "role": "recruiter"
    }, headers=auth_headers(admin_tok))
    assert res.status_code in (200, 201)

    member = team_members_collection.find_one({"email": invite_email})
    assert member is not None
    assert member["role"] == "recruiter"
    assert member["status"] == "invited"
    assert member["company_id"] == TEST_COMPANY_ID

    # Ensure raw token is NEVER stored, only SHA-256 hash
    assert "invite_token_hash" in member
    assert len(member["invite_token_hash"]) == 64
    assert "invite_token" not in member

    # Attempt to invite same email again -> 400
    res_dup = client.post("/api/settings/team/invite", json={
        "email": invite_email,
        "role": "viewer"
    }, headers=auth_headers(admin_tok))
    assert res_dup.status_code == 400

    # Attempt to invite company owner email -> 400
    res_owner = client.post("/api/settings/team/invite", json={
        "email": TEST_OWNER_EMAIL,
        "role": "admin"
    }, headers=auth_headers(admin_tok))
    assert res_owner.status_code == 400

# ── 6. Verify & Accept Invite ─────────────────────────────────────────────────
def test_verify_and_accept_invite(client):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=72)

    member_id = team_members_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "email": "invitee@example.com",
        "name": "",
        "role": "recruiter",
        "status": "invited",
        "invite_token_hash": token_hash,
        "invite_expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    }).inserted_id

    # 1. Verify invite
    res_verify = client.get(f"/api/auth/verify-invite?token={raw_token}")
    assert res_verify.status_code == 200
    data = res_verify.get_json()
    assert data["success"] is True
    assert data["email"] == "invitee@example.com"
    assert data["role"] == "recruiter"

    # 2. Accept invite with password < 8 chars -> 400
    res_short = client.post("/api/auth/accept-invite", json={
        "token": raw_token,
        "name": "Jane Doe",
        "password": "short"
    })
    assert res_short.status_code == 400

    # 3. Accept invite successfully
    res_accept = client.post("/api/auth/accept-invite", json={
        "token": raw_token,
        "name": "Jane Doe",
        "password": "SecurePassword123!"
    })
    assert res_accept.status_code == 200

    updated = team_members_collection.find_one({"_id": member_id})
    assert updated["status"] == "active"
    assert updated["name"] == "Jane Doe"
    assert updated["invite_token_hash"] is None
    assert updated["password_hash"] is not None

    # 4. Attempt to reuse token -> 400
    res_reuse = client.post("/api/auth/accept-invite", json={
        "token": raw_token,
        "name": "Jane Doe",
        "password": "SecurePassword123!"
    })
    assert res_reuse.status_code == 400

# ── 7. Expired Invite Token ───────────────────────────────────────────────────
def test_expired_invite_token(client):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    past_expires = datetime.now(timezone.utc) - timedelta(hours=1)

    team_members_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "email": "expired@example.com",
        "role": "viewer",
        "status": "invited",
        "invite_token_hash": token_hash,
        "invite_expires_at": past_expires,
        "created_at": datetime.now(timezone.utc)
    })

    res = client.get(f"/api/auth/verify-invite?token={raw_token}")
    assert res.status_code == 400
    assert "expired" in res.get_json()["error"].lower()

# ── 8. Team Member Login & Status Restrictions ────────────────────────────────
def test_team_member_login(client):
    password = "MyMemberPassword123!"
    member_id = team_members_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "email": "activemember@example.com",
        "name": "Active Member",
        "role": "recruiter",
        "status": "active",
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc)
    }).inserted_id

    # Success login
    res = client.post("/api/auth/login", json={
        "email": "activemember@example.com",
        "password": password
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["role"] == "recruiter"
    assert data["name"] == "Active Member"
    assert "token" in data

    # Wrong password -> 401
    res_wrong = client.post("/api/auth/login", json={
        "email": "activemember@example.com",
        "password": "wrongpassword"
    })
    assert res_wrong.status_code == 401

    # Invited status -> 403
    team_members_collection.update_one({"_id": member_id}, {"$set": {"status": "invited"}})
    res_inv = client.post("/api/auth/login", json={
        "email": "activemember@example.com",
        "password": password
    })
    assert res_inv.status_code == 403

    # Disabled status -> 403
    team_members_collection.update_one({"_id": member_id}, {"$set": {"status": "disabled"}})
    res_dis = client.post("/api/auth/login", json={
        "email": "activemember@example.com",
        "password": password
    })
    assert res_dis.status_code == 403

# ── 9. Session Revocation for Disabled Members ────────────────────────────────
def test_disabled_member_session_revocation(client):
    password = "ValidPassword123!"
    member_id, token, _ = create_member(role="recruiter")

    # Request succeeds while active
    res_ok = client.get("/api/settings", headers=auth_headers(token))
    assert res_ok.status_code == 200

    # Admin disables member in database
    team_members_collection.update_one({"_id": ObjectId(member_id)}, {"$set": {"status": "disabled"}})

    # Subsequent request using existing token is revoked server-side (403)
    res_revoked = client.get("/api/settings", headers=auth_headers(token))
    assert res_revoked.status_code == 403
    assert "disabled" in res_revoked.get_json()["error"].lower()

# ── 10. Legacy Token Defaults to Owner ────────────────────────────────────────
def test_legacy_token_defaults_to_owner(client):
    legacy_payload = {
        "company_id": TEST_COMPANY_ID,
        "email": TEST_OWNER_EMAIL,
        "company_name": "Test Company"
    }
    legacy_token = generate_token(legacy_payload)

    job_id = str(jobs_collection.insert_one({
        "company_id": TEST_COMPANY_ID,
        "title": "Legacy Job",
        "status": "active"
    }).inserted_id)

    res = client.delete(f"/api/jobs/{job_id}", headers=auth_headers(legacy_token))
    assert res.status_code == 200

# ── 11. Owner Protection & Last Admin Rule ────────────────────────────────────
def test_owner_and_last_admin_protection(client):
    admin_id, admin_tok, _ = create_member(role="admin")

    # Cannot demote owner
    res_demote_owner = client.patch(f"/api/settings/team/members/{TEST_COMPANY_ID}/role", json={
        "role": "recruiter"
    }, headers=auth_headers(admin_tok))
    assert res_demote_owner.status_code == 400
    assert "owner" in res_demote_owner.get_json()["error"].lower()

    # Cannot disable owner
    res_dis_owner = client.patch(f"/api/settings/team/members/{TEST_COMPANY_ID}/status", json={
        "status": "disabled"
    }, headers=auth_headers(admin_tok))
    assert res_dis_owner.status_code == 400

    # Cannot remove owner
    res_del_owner = client.delete(f"/api/settings/team/members/{TEST_COMPANY_ID}", headers=auth_headers(admin_tok))
    assert res_del_owner.status_code == 400

    # Last admin rule: cannot demote the only admin
    res_demote_admin = client.patch(f"/api/settings/team/members/{admin_id}/role", json={
        "role": "recruiter"
    }, headers=auth_headers(admin_tok))
    assert res_demote_admin.status_code == 400
    assert "administrator" in res_demote_admin.get_json()["error"].lower()

    # Last admin rule: cannot remove the only admin
    res_del_admin = client.delete(f"/api/settings/team/members/{admin_id}", headers=auth_headers(admin_tok))
    assert res_del_admin.status_code == 400
    assert "administrator" in res_del_admin.get_json()["error"].lower()

# ── 12. Regression Test: Production DB Name ───────────────────────────────────
def test_team_routes_allow_production_db_name(client):
    _, admin_tok, _ = create_member(role="admin")
    original_db = Config.DB_NAME
    try:
        Config.DB_NAME = "recruitmate"

        # GET /api/settings/team/members succeeds with 200
        res = client.get("/api/settings/team/members", headers=auth_headers(admin_tok))
        assert res.status_code == 200
        assert res.get_json()["success"] is True

        # GET /api/settings/team/activity succeeds with 200
        res_act = client.get("/api/settings/team/activity", headers=auth_headers(admin_tok))
        assert res_act.status_code == 200
        assert res_act.get_json()["success"] is True
    finally:
        Config.DB_NAME = original_db

# ── 13. Audit Log Trail ───────────────────────────────────────────────────────
def test_audit_logging_writes_and_retrieval(client):
    _, admin_tok, _ = create_member(role="admin")

    # Invite a member
    client.post("/api/settings/team/invite", json={
        "email": "audit_test@example.com",
        "role": "viewer"
    }, headers=auth_headers(admin_tok))

    # Fetch activity
    res = client.get("/api/settings/team/activity", headers=auth_headers(admin_tok))
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["logs"]) > 0
    actions = [log["action"] for log in data["logs"]]
    assert "team.invite" in actions
