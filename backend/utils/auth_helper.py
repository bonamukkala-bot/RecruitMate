import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config

# ── Password hashing ─────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    """Check plain password against bcrypt hash."""
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        hashed.encode("utf-8")
    )

# ── Role Hierarchy & Access Levels ───────────────────────────────────────────
ROLE_HIERARCHY = {
    "owner": 4,
    "admin": 3,
    "recruiter": 2,
    "viewer": 1
}
VALID_ROLES = set(ROLE_HIERARCHY.keys())

# ── JWT token generation ─────────────────────────────────────────────────────
def generate_token(company: dict, role: str = None, user_id: str = None) -> str:
    """
    Generate a JWT token containing company and user identity.
    Carries company_id, user_id, and role.
    Tokens without role claim default to 'owner' on decoding.
    Valid for JWT_EXPIRY_HOURS (default 8 hours).
    """
    comp_id = str(company.get("company_id") or company.get("_id"))
    uid = str(user_id or company.get("user_id") or company.get("_id"))
    token_role = role or company.get("role") or "owner"

    payload = {
        "company_id"  : comp_id,
        "user_id"     : uid,
        "email"       : company.get("email", ""),
        "role"        : token_role,
        "company_name": company.get("company_name", ""),
        "name"        : company.get("name") or company.get("full_name") or "",
        "exp"         : datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")

# ── JWT token decoding ───────────────────────────────────────────────────────
def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Ensures backward compatibility: tokens without role default to 'owner'.
    Returns payload dict or raises exception.
    """
    payload = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
    if "role" not in payload:
        payload["role"] = "owner"
    if "user_id" not in payload:
        payload["user_id"] = payload.get("company_id")
    return payload

# ── JWT required decorator ───────────────────────────────────────────────────
def jwt_required(f):
    """
    Decorator that protects a route with JWT authentication.
    Extracts company identity & role from token and passes it to the route.
    Validates server-side that non-owner members are active (rejects disabled sessions).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({
                "success": False,
                "error"  : "Authorization token is missing"
            }), 401

        try:
            payload = decode_token(token)
            role = payload.get("role", "owner")
            payload["role"] = role

            # Server-side check for team members: ensure account is not disabled
            if role != "owner":
                from utils.db import team_members_collection
                from bson import ObjectId

                uid = payload.get("user_id")
                member = None
                try:
                    member = team_members_collection.find_one({"_id": ObjectId(uid)})
                except Exception:
                    pass
                if not member:
                    member = team_members_collection.find_one({"_id": uid})

                if not member:
                    return jsonify({
                        "success": False,
                        "error": "Account no longer exists. Please contact your administrator."
                    }), 401

                if member.get("status") == "disabled":
                    return jsonify({
                        "success": False,
                        "error": "Your account has been disabled. Please contact your company administrator."
                    }), 403

                if member.get("status") == "invited":
                    return jsonify({
                        "success": False,
                        "error": "Please accept your invitation first."
                    }), 403

                # Keep role synchronized with DB
                payload["role"] = member.get("role", role)

            request.company = payload  # attach to request object
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error"  : "Token has expired. Please log in again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error"  : "Invalid token. Please log in again."
            }), 401

        return f(*args, **kwargs)
    return decorated

# ── Role-based Access Control Decorator ──────────────────────────────────────
def require_role(min_role: str):
    """
    Decorator enforcing role hierarchy: owner > admin > recruiter > viewer.
    Must be placed on routes that also use @jwt_required.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            current = getattr(request, "company", None)
            if not current:
                return jsonify({"success": False, "error": "Authentication required"}), 401

            user_role = current.get("role", "owner")
            user_rank = ROLE_HIERARCHY.get(user_role, 0)
            required_rank = ROLE_HIERARCHY.get(min_role, 0)

            if user_rank < required_rank:
                return jsonify({
                    "success": False,
                    "error": f"Permission denied: '{min_role}' role or higher required (current: '{user_role}')"
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator

# ── Audit Logging Helper ──────────────────────────────────────────────────────
def log_audit_event(
    company_id: str,
    action: str,
    actor: dict | None = None,
    target: str | dict | None = None,
    details: dict | None = None,
    candidate_id: str | None = None,
    **extra
):
    """
    Safely records an audit event in audit_logs collection.
    Logging failures will never break active request handlers.
    """
    try:
        from utils.db import audit_logs_collection

        if actor is None:
            curr = getattr(request, "company", {}) if request else {}
            actor = {
                "user_id": curr.get("user_id"),
                "email": curr.get("email", "system"),
                "role": curr.get("role", "owner"),
                "name": curr.get("name") or curr.get("company_name") or ""
            }

        audit_doc = {
            "company_id": str(company_id),
            "actor": actor,
            "action": action,
            "target": target,
            "details": details or {},
            "ts": datetime.now(timezone.utc),
            **extra
        }
        if candidate_id:
            audit_doc["candidate_id"] = str(candidate_id)
        elif isinstance(target, str) and (action.startswith("candidate") or "candidate" in action):
            audit_doc["candidate_id"] = target

        audit_logs_collection.insert_one(audit_doc)
    except Exception as log_err:
        print(f"⚠️ [audit_log] Error logging event: {log_err}")

# ── Get current company from request ────────────────────────────────────────
def get_current_company() -> dict:
    """
    Returns the company payload extracted from JWT token.
    Must be used inside a @jwt_required protected route.
    """
    return request.company

# ── OTP generation ───────────────────────────────────────────────────────────
def generate_otp() -> str:
    """Generate a secure 6-digit OTP."""
    import secrets
    return str(secrets.randbelow(900000) + 100000)
