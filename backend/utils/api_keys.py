import time
import secrets
import hashlib
from functools import wraps
from datetime import datetime, timezone
from flask import request, jsonify, g
from utils.db import api_keys_collection

VALID_SCOPES = {"read:candidates", "write:jobs"}
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

# In-memory sliding window rate limiter: {key_hash: [timestamps]}
_RATE_LIMIT_STORE: dict[str, list[float]] = {}

def generate_api_key() -> tuple[str, str, str]:
    """
    Generates a new API key.
    Returns (full_key, key_hash, key_prefix).
    The full_key is displayed to the user ONCE.
    """
    token = secrets.token_hex(20)
    full_key = f"rm_live_{token}"
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    key_prefix = f"{full_key[:12]}..."
    return full_key, key_hash, key_prefix

def hash_api_key(raw_key: str) -> str:
    """Computes SHA-256 hash of API key for database lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()

def check_rate_limit(key_hash: str) -> bool:
    """Sliding-window rate limiter per API key (60 req/min). Returns True if allowed."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _RATE_LIMIT_STORE.get(key_hash, [])
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        _RATE_LIMIT_STORE[key_hash] = timestamps
        return False

    timestamps.append(now)
    _RATE_LIMIT_STORE[key_hash] = timestamps
    return True

def api_key_required(required_scope: str | None = None):
    """
    Flask route decorator to authenticate external API calls via API key.
    Enforces key existence, validity, scope permissions, and rate limits.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            raw_key = None
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                raw_key = auth_header.split(" ", 1)[1].strip()
            elif request.headers.get("X-API-Key"):
                raw_key = request.headers.get("X-API-Key").strip()

            if not raw_key:
                return jsonify({
                    "success": False,
                    "error": "Authentication required. Provide an API key via 'Authorization: Bearer <key>' or 'X-API-Key'."
                }), 401

            key_hash = hash_api_key(raw_key)
            key_doc = api_keys_collection.find_one({"key_hash": key_hash})

            if not key_doc:
                return jsonify({"success": False, "error": "Invalid API key"}), 401

            if key_doc.get("revoked", False):
                return jsonify({"success": False, "error": "API key has been revoked"}), 401

            expires_at = key_doc.get("expires_at")
            if expires_at:
                now_utc = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now_utc:
                    return jsonify({"success": False, "error": "API key has expired"}), 401

            # Rate limiting
            if not check_rate_limit(key_hash):
                return jsonify({
                    "success": False,
                    "error": f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per minute."
                }), 429

            # Scope enforcement
            scopes = key_doc.get("scopes", [])
            if required_scope and required_scope not in scopes:
                return jsonify({
                    "success": False,
                    "error": f"Insufficient scope. Required scope: '{required_scope}'"
                }), 403

            # Update last_used_at timestamp
            api_keys_collection.update_one(
                {"_id": key_doc["_id"]},
                {"$set": {"last_used_at": datetime.now(timezone.utc)}}
            )

            # Store identity in flask.g for downstream handlers
            g.company_id = str(key_doc["company_id"])
            g.api_key_id = str(key_doc["_id"])
            g.api_key_scopes = scopes

            return fn(*args, **kwargs)
        return wrapper
    return decorator
