import json
import secrets
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from flask import Blueprint, request, jsonify

from config import Config
from utils.auth_helper import jwt_required, get_current_company, require_role, log_audit_event
from utils.db import (
    api_keys_collection,
    webhooks_collection,
    webhook_logs_collection,
    company_settings_collection
)
from utils.settings import get_settings
from utils.webhook_dispatcher import (
    validate_webhook_url,
    deliver_webhook_attempt
)
from utils.slack import send_slack_message
from utils.api_keys import generate_api_key, VALID_SCOPES

integrations_bp = Blueprint("integrations", __name__)

ALLOWED_WEBHOOK_EVENTS = [
    "candidate.created",
    "interview.completed",
    "candidate.pending_review"
]

# ── Slack Endpoints ───────────────────────────────────────────────────────────

@integrations_bp.route("/slack/test", methods=["POST"])
@jwt_required
@require_role("admin")
def test_slack_webhook():
    """Sends a test message to the configured or provided Slack webhook URL."""
    company = get_current_company()
    company_id = company["company_id"]

    body = request.get_json(silent=True) or {}
    webhook_url = body.get("webhook_url", "").strip()

    # If not passed in body, load from company settings
    if not webhook_url or webhook_url.startswith("https://hooks.slack.com/..."):
        settings = get_settings(company_id)
        webhook_url = settings.get("integrations", {}).get("slack_webhook_url", "").strip()

    if not webhook_url:
        return jsonify({"success": False, "error": "No Slack webhook URL configured"}), 400

    if not webhook_url.startswith("https://hooks.slack.com/"):
        return jsonify({"success": False, "error": "Slack webhook URL must start with 'https://hooks.slack.com/'"}), 400

    text = f"✅ *RecruitMate Integration Test:* Slack alerts are successfully connected for *{company.get('company_name', 'Your Company')}*!"
    success, msg = send_slack_message(webhook_url, text)

    if success:
        return jsonify({"success": True, "message": "Test message sent to Slack successfully"}), 200
    return jsonify({"success": False, "error": msg}), 400

# ── Outgoing Webhooks Endpoints ───────────────────────────────────────────────

@integrations_bp.route("/webhooks", methods=["GET"])
@jwt_required
def list_webhooks():
    """Lists configured outgoing webhooks for the company. Omits secrets."""
    company = get_current_company()
    company_id = company["company_id"]

    docs = list(webhooks_collection.find({"company_id": company_id}).sort("created_at", -1))
    results = []
    for d in docs:
        results.append({
            "id": str(d["_id"]),
            "url": d.get("url", ""),
            "events": d.get("events", []),
            "active": d.get("active", True),
            "created_at": d.get("created_at").isoformat() if isinstance(d.get("created_at"), datetime) else str(d.get("created_at", ""))
        })

    return jsonify({"success": True, "webhooks": results}), 200

@integrations_bp.route("/webhooks", methods=["POST"])
@jwt_required
@require_role("admin")
def create_webhook():
    """
    Registers a new outgoing webhook endpoint.
    Performs SSRF validation.
    Generates a signing secret that is returned ONCE.
    """
    company = get_current_company()
    company_id = company["company_id"]
    body = request.get_json(silent=True) or {}

    url = (body.get("url") or "").strip()
    is_valid, err_msg = validate_webhook_url(url)
    if not is_valid:
        return jsonify({"success": False, "error": err_msg}), 400

    events = body.get("events", [])
    if not isinstance(events, list) or not events:
        return jsonify({"success": False, "error": "At least one valid event must be selected"}), 400

    invalid_events = [e for e in events if e not in ALLOWED_WEBHOOK_EVENTS]
    if invalid_events:
        return jsonify({"success": False, "error": f"Invalid events: {invalid_events}. Allowed: {ALLOWED_WEBHOOK_EVENTS}"}), 400

    secret = secrets.token_hex(24)
    now_utc = datetime.now(timezone.utc)

    doc = {
        "company_id": company_id,
        "url": url,
        "events": events,
        "secret": secret,
        "active": True,
        "created_at": now_utc,
        "created_by": company.get("email", "unknown")
    }

    result = webhooks_collection.insert_one(doc)
    wh_id = str(result.inserted_id)

    log_audit_event(
        company_id=company_id,
        action="webhook.create",
        target=wh_id,
        details={"url": url, "events": events}
    )

    return jsonify({
        "success": True,
        "message": "Webhook created successfully. Save your signing secret now; it will not be shown again.",
        "webhook": {
            "id": wh_id,
            "url": url,
            "events": events,
            "secret": secret,
            "created_at": now_utc.isoformat()
        }
    }), 201

@integrations_bp.route("/webhooks/<webhook_id>", methods=["DELETE"])
@jwt_required
@require_role("admin")
def delete_webhook(webhook_id: str):
    """Deletes an outgoing webhook."""
    company = get_current_company()
    company_id = company["company_id"]

    try:
        wh_oid = ObjectId(webhook_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid webhook ID"}), 400

    result = webhooks_collection.delete_one({"_id": wh_oid, "company_id": company_id})
    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "Webhook not found"}), 404

    log_audit_event(
        company_id=company_id,
        action="webhook.delete",
        target=webhook_id,
        details={}
    )

    return jsonify({"success": True, "message": "Webhook deleted"}), 200

@integrations_bp.route("/webhooks/<webhook_id>/test", methods=["POST"])
@jwt_required
@require_role("admin")
def test_webhook(webhook_id: str):
    """Sends a ping test event to a specific webhook."""
    company = get_current_company()
    company_id = company["company_id"]

    try:
        wh_oid = ObjectId(webhook_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid webhook ID"}), 400

    wh = webhooks_collection.find_one({"_id": wh_oid, "company_id": company_id})
    if not wh:
        return jsonify({"success": False, "error": "Webhook not found"}), 404

    test_payload = {
        "event": "ping",
        "company_id": company_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "RecruitMate webhook connection test"
    }
    payload_json = json.dumps(test_payload)

    success, status_code, err = deliver_webhook_attempt(wh, "ping", payload_json, attempt=1)
    if success:
        return jsonify({"success": True, "message": f"Webhook ping delivered (HTTP {status_code})"}), 200
    return jsonify({"success": False, "error": f"Webhook test failed: {err}"}), 400

@integrations_bp.route("/webhooks/deliveries", methods=["GET"])
@jwt_required
def get_webhook_deliveries():
    """Returns the last 50 webhook delivery log entries for the company."""
    company = get_current_company()
    company_id = company["company_id"]

    logs = list(
        webhook_logs_collection.find({"company_id": company_id})
        .sort("delivered_at", -1)
        .limit(50)
    )

    results = []
    for l in logs:
        results.append({
            "id": str(l["_id"]),
            "webhook_id": l.get("webhook_id", ""),
            "event": l.get("event", ""),
            "url": l.get("url", ""),
            "status_code": l.get("status_code", 0),
            "response_time_ms": l.get("response_time_ms", 0),
            "attempt": l.get("attempt", 1),
            "success": l.get("success", False),
            "error_message": l.get("error_message", ""),
            "delivered_at": l.get("delivered_at").isoformat() if isinstance(l.get("delivered_at"), datetime) else str(l.get("delivered_at", ""))
        })

    return jsonify({"success": True, "deliveries": results}), 200

# ── API Keys Endpoints ────────────────────────────────────────────────────────

@integrations_bp.route("/api-keys", methods=["GET"])
@jwt_required
def list_api_keys():
    """Lists API keys for the company (omits full key hash, returns visible prefix)."""
    company = get_current_company()
    company_id = company["company_id"]

    keys = list(api_keys_collection.find({"company_id": company_id}).sort("created_at", -1))
    results = []
    for k in keys:
        results.append({
            "id": str(k["_id"]),
            "name": k.get("name", "Default Key"),
            "key_prefix": k.get("key_prefix", "rm_live_..."),
            "scopes": k.get("scopes", []),
            "revoked": k.get("revoked", False),
            "created_at": k.get("created_at").isoformat() if isinstance(k.get("created_at"), datetime) else str(k.get("created_at", "")),
            "expires_at": k.get("expires_at").isoformat() if isinstance(k.get("expires_at"), datetime) else None,
            "last_used_at": k.get("last_used_at").isoformat() if isinstance(k.get("last_used_at"), datetime) else None
        })

    return jsonify({"success": True, "api_keys": results}), 200

@integrations_bp.route("/api-keys", methods=["POST"])
@jwt_required
@require_role("admin")
def create_api_key_endpoint():
    """Creates a new API key. The raw key is returned ONCE and never stored."""
    company = get_current_company()
    company_id = company["company_id"]
    body = request.get_json(silent=True) or {}

    name = (body.get("name") or "API Key").strip()
    scopes = body.get("scopes", ["read:candidates", "write:jobs"])

    if not isinstance(scopes, list) or not scopes:
        return jsonify({"success": False, "error": "At least one scope must be provided"}), 400

    invalid_scopes = [s for s in scopes if s not in VALID_SCOPES]
    if invalid_scopes:
        return jsonify({"success": False, "error": f"Invalid scopes: {invalid_scopes}. Allowed: {list(VALID_SCOPES)}"}), 400

    expires_in_days = body.get("expires_in_days")
    expires_at = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            if days > 0:
                expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        except (ValueError, TypeError):
            pass

    full_key, key_hash, key_prefix = generate_api_key()
    now_utc = datetime.now(timezone.utc)

    doc = {
        "company_id": company_id,
        "name": name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "scopes": scopes,
        "revoked": False,
        "created_at": now_utc,
        "expires_at": expires_at,
        "created_by": company.get("email", "unknown"),
        "last_used_at": None
    }

    result = api_keys_collection.insert_one(doc)
    key_id = str(result.inserted_id)

    log_audit_event(
        company_id=company_id,
        action="api_key.create",
        target=key_id,
        details={"name": name, "scopes": scopes, "prefix": key_prefix}
    )

    return jsonify({
        "success": True,
        "message": "API key generated successfully. Copy it now; you will not be able to view it again.",
        "key": full_key,
        "api_key": {
            "id": key_id,
            "name": name,
            "key_prefix": key_prefix,
            "scopes": scopes,
            "created_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None
        }
    }), 201

@integrations_bp.route("/api-keys/<key_id>", methods=["DELETE"])
@jwt_required
@require_role("admin")
def revoke_api_key(key_id: str):
    """Revokes an API key permanently."""
    company = get_current_company()
    company_id = company["company_id"]

    try:
        k_oid = ObjectId(key_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid API key ID"}), 400

    result = api_keys_collection.update_one(
        {"_id": k_oid, "company_id": company_id},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc)}}
    )

    if result.matched_count == 0:
        return jsonify({"success": False, "error": "API key not found"}), 404

    log_audit_event(
        company_id=company_id,
        action="api_key.revoke",
        target=key_id,
        details={}
    )

    return jsonify({"success": True, "message": "API key revoked"}), 200

# ── Google Calendar & Meet Status ─────────────────────────────────────────────

@integrations_bp.route("/google/status", methods=["GET"])
@jwt_required
def google_calendar_status():
    """Returns Google Calendar / Meet integration status."""
    company = get_current_company()
    company_id = company["company_id"]

    settings = get_settings(company_id)
    integrations = settings.get("integrations", {})
    connected = bool(integrations.get("google_calendar_connected", False))
    calendar_email = integrations.get("google_calendar_email", "")

    return jsonify({
        "success": True,
        "enabled": Config.GOOGLE_CALENDAR_ENABLED,
        "connected": connected,
        "calendar_email": calendar_email
    }), 200

@integrations_bp.route("/google/disconnect", methods=["POST"])
@jwt_required
@require_role("admin")
def google_calendar_disconnect():
    """Disconnects Google Calendar integration."""
    company = get_current_company()
    company_id = company["company_id"]

    company_settings_collection.update_one(
        {"company_id": company_id},
        {
            "$set": {
                "integrations.google_calendar_enabled": False,
                "integrations.google_calendar_connected": False,
                "integrations.google_refresh_token_enc": "",
                "integrations.google_calendar_email": "",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    log_audit_event(
        company_id=company_id,
        action="google_calendar.disconnect",
        target="google_calendar",
        details={}
    )

    return jsonify({"success": True, "message": "Google Calendar disconnected"}), 200
