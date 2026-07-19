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

# ── JWT token generation ─────────────────────────────────────────────────────
def generate_token(company: dict) -> str:
    """
    Generate a JWT token containing company identity.
    Valid for JWT_EXPIRY_HOURS (default 8 hours).
    """
    payload = {
        "company_id"  : str(company["_id"]),
        "email"       : company["email"],
        "company_name": company["company_name"],
        "exp"         : datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")

# ── JWT token decoding ───────────────────────────────────────────────────────
def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Returns payload dict or raises exception.
    """
    return jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])

# ── JWT required decorator ───────────────────────────────────────────────────
def jwt_required(f):
    """
    Decorator that protects a route with JWT authentication.
    Extracts company identity from token and passes it to the route.
    Usage: @jwt_required on any route function.
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
            request.company = payload  # attach to request object
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