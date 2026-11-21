import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
import requests
from utils.db import companies_collection, otp_collection
from utils.auth_helper import hash_password, verify_password, generate_token, generate_otp
from config import Config
import pyotp
import qrcode
import io
import base64
from bson import ObjectId
from utils.auth_helper import jwt_required, get_current_company
from utils.settings import get_settings
import html

auth_bp = Blueprint("auth", __name__)

OTP_COOLDOWN_SECONDS = 60

def check_otp_cooldown(email: str) -> tuple[bool, int]:
    """Returns (is_in_cooldown, remaining_seconds)."""
    otp_record = otp_collection.find_one({"email": email})
    if otp_record and otp_record.get("last_sent_at"):
        last_sent = otp_record["last_sent_at"]
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_sent).total_seconds()
        if elapsed < OTP_COOLDOWN_SECONDS:
            remaining = int(OTP_COOLDOWN_SECONDS - elapsed)
            return True, remaining
    return False, 0

# ── Verify Cloudflare Turnstile token ──────────────────────────────────────────
def verify_turnstile(token: str, remote_ip: str = None) -> bool:
    if not token:
        print("[Turnstile] Verification failed: Token is empty or missing")
        return False
    try:
        secret = os.getenv("TURNSTILE_SECRET_KEY") or Config.TURNSTILE_SECRET_KEY
        if not secret:
            print("[Turnstile] Verification failed: TURNSTILE_SECRET_KEY is not configured")
            return False

        payload = {
            "secret": secret,
            "response": token
        }
        if remote_ip:
            payload["remoteip"] = remote_ip

        resp = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=payload,
            timeout=5
        )
        status_code = resp.status_code
        try:
            result = resp.json()
        except Exception:
            result = {}

        success = result.get("success", False)
        error_codes = result.get("error-codes", [])

        print(f"[Turnstile] Siteverify HTTP status: {status_code}, success: {success}, error-codes: {error_codes}")
        return bool(success)
    except requests.exceptions.Timeout:
        print("[Turnstile] Siteverify error: Request timed out after 5 seconds")
        return False
    except requests.exceptions.RequestException as e:
        print(f"[Turnstile] Siteverify network error: {e}")
        return False
    except Exception as e:
        print(f"[Turnstile] Siteverify error: {e}")
        return False

# ── Send OTP email via Brevo ──────────────────────────────────────────────────
def send_otp_email(to_email: str, otp: str, company_name: str, company_id: str = None) -> tuple[bool, str]:
    if not Config.BREVO_API_KEY:
        err = "BREVO_API_KEY is not configured"
        print(f"[Brevo OTP] Error: {err}")
        return False, err

    try:
        settings = get_settings(company_id) if company_id else None
        footer_text = "This code expires in 5 minutes. Do not share it with anyone."
        if settings:
            footer_text = settings.get("email", {}).get("templates", {}).get("otp_footer") or footer_text

        configuration         = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = Config.BREVO_API_KEY

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        escaped_company = html.escape(company_name)
        escaped_footer = html.escape(footer_text)

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 32px;">
            <h2 style="color: #1f2937;">Welcome to RecruitMate AI</h2>
            <p>Hi <strong>{escaped_company}</strong>,</p>
            <p>Your email verification code is:</p>
            <div style="font-size: 36px; font-weight: bold; color: #2563eb;
                        letter-spacing: 8px; padding: 16px; background: #f3f4f6;
                        border-radius: 8px; text-align: center;">
                {otp}
            </div>
            <p style="color: #6b7280; margin-top: 16px;">
                {escaped_footer}
            </p>
            <p style="color: #6b7280;">— RecruitMate AI Team</p>
        </div>
        """

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email, "name": company_name}],
            sender={
                "email": Config.BREVO_SENDER_EMAIL,
                "name" : Config.BREVO_SENDER_NAME
            },
            subject="RecruitMate AI — Your Verification Code",
            html_content=html_content
        )

        resp = api_instance.send_transac_email(send_smtp_email)
        message_id = getattr(resp, "message_id", str(resp))
        print(f"[Brevo OTP] Email sent successfully to {to_email}. Message ID: {message_id}")
        return True, ""

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo OTP] API Error - Status: {status_code}, Body: {body}")
        return False, f"Email provider error ({status_code})"
    except Exception as e:
        print(f"[Brevo OTP] Unexpected error: {e}")
        return False, str(e)

# ── POST /api/auth/register ───────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}

    print(f"\n[DEBUG /api/auth/register] Received request keys: {list(body.keys())}")
    required = {"email", "password", "company_name", "full_name"}
    print(f"[DEBUG /api/auth/register] Expected required keys: {list(required)}")

    turnstile_token = body.get("turnstile_token")
    print(f"[DEBUG /api/auth/register] Has turnstile_token: {bool(turnstile_token)}")

    if not verify_turnstile(turnstile_token, request.remote_addr):
        print("[DEBUG /api/auth/register] 400 branch fired: CAPTCHA verification failed. Please try again.")
        return jsonify({"success": False, "error": "CAPTCHA verification failed. Please try again."}), 400

    missing  = required - body.keys()
    if missing:
        print(f"[DEBUG /api/auth/register] 400 branch fired: Missing fields: {missing}")
        return jsonify({"success": False, "error": f"Missing fields: {missing}"}), 400

    email        = body["email"].lower().strip()
    password     = body["password"]
    company_name = body["company_name"].strip()
    full_name    = body["full_name"].strip()

    # Check if email already exists
    existing = companies_collection.find_one({"email": email})
    if existing:
        if not existing.get("is_verified"):
            # Enforce 60-second cooldown
            in_cooldown, remaining = check_otp_cooldown(email)
            if in_cooldown:
                return jsonify({
                    "success": False,
                    "error": f"Please wait {remaining} seconds before requesting another code",
                    "cooldown_remaining": remaining
                }), 429

            # Update stored password hash, company_name and full_name with newly submitted values
            companies_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "password": hash_password(password),
                    "company_name": company_name,
                    "full_name": full_name
                }}
            )

            # Generate fresh OTP and send verification email
            otp = generate_otp()
            company_id = str(existing["_id"])
            now_utc = datetime.now(timezone.utc)

            email_sent, err_msg = send_otp_email(email, otp, company_name)
            if not email_sent:
                return jsonify({
                    "success": False,
                    "error": f"Failed to send verification email: {err_msg}"
                }), 502

            otp_collection.update_one(
                {"email": email},
                {"$set": {
                    "otp": otp,
                    "company_id": company_id,
                    "expires_at": now_utc + timedelta(minutes=5),
                    "last_sent_at": now_utc
                }},
                upsert=True
            )

            return jsonify({
                "success": True,
                "requires_verification": True,
                "message": "Verification code sent. Check your email for OTP.",
                "company_id": company_id
            }), 200

        return jsonify({"success": False, "error": "An account with this email already exists"}), 409

    # Fresh registration: generate OTP and send email before inserting company
    otp = generate_otp()
    email_sent, err_msg = send_otp_email(email, otp, company_name)
    if not email_sent:
        return jsonify({
            "success": False,
            "error": f"Failed to send verification email: {err_msg}"
        }), 502

    now_utc = datetime.now(timezone.utc)
    company_doc = {
        "email"       : email,
        "password"    : hash_password(password),
        "company_name": company_name,
        "full_name"   : full_name,
        "is_verified" : False,
        "created_at"  : now_utc
    }

    inserted   = companies_collection.insert_one(company_doc)
    company_id = str(inserted.inserted_id)

    # Store OTP in DB with 5 minute expiry and record last_sent_at for cooldown
    otp_collection.update_one(
        {"email": email},
        {"$set": {
            "email"       : email,
            "otp"         : otp,
            "company_id"  : company_id,
            "expires_at"  : now_utc + timedelta(minutes=5),
            "last_sent_at": now_utc
        }},
        upsert=True
    )

    return jsonify({
        "success"   : True,
        "message"   : "Registration successful. Check your email for OTP.",
        "company_id": company_id,
        "email_sent": True
    }), 201

# ── POST /api/auth/resend-otp ─────────────────────────────────────────────────
@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    body  = request.get_json(silent=True) or {}
    email = body.get("email", "").lower().strip()

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    # Generic success response returned whether or not account exists (anti-enumeration)
    generic_success = {
        "success": True,
        "message": "A new verification code has been sent to your email."
    }

    company = companies_collection.find_one({"email": email})
    # If account doesn't exist or is already verified, return generic success without revealing status
    if not company or company.get("is_verified"):
        return jsonify(generic_success), 200

    # Account exists and is unverified: enforce 60-second cooldown
    in_cooldown, remaining = check_otp_cooldown(email)
    if in_cooldown:
        return jsonify({
            "success": False,
            "error": f"Please wait {remaining} seconds before requesting another code",
            "cooldown_remaining": remaining
        }), 429

    otp = generate_otp()
    company_id = str(company["_id"])
    now_utc = datetime.now(timezone.utc)

    email_sent, err_msg = send_otp_email(email, otp, company.get("company_name", "RecruitMate User"))
    if not email_sent:
        return jsonify({
            "success": False,
            "error": f"Failed to send verification email: {err_msg}"
        }), 502

    otp_collection.update_one(
        {"email": email},
        {"$set": {
            "otp": otp,
            "company_id": company_id,
            "expires_at": now_utc + timedelta(minutes=5),
            "last_sent_at": now_utc
        }},
        upsert=True
    )

    return jsonify(generic_success), 200

# ── POST /api/auth/verify-otp ─────────────────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    body  = request.get_json(silent=True) or {}
    email = body.get("email", "").lower().strip()
    otp   = body.get("otp", "").strip()

    if not email or not otp:
        return jsonify({"success": False, "error": "Email and OTP are required"}), 400

    # Find OTP record
    otp_record = otp_collection.find_one({"email": email, "otp": otp})

    if not otp_record:
        return jsonify({"success": False, "error": "Invalid or expired OTP"}), 400

    # Check expiry
    expires_at = otp_record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        otp_collection.delete_one({"email": email})
        return jsonify({"success": False, "error": "OTP has expired. Please register again."}), 400

    # Mark company as verified
    companies_collection.update_one(
        {"email": email},
        {"$set": {"is_verified": True}}
    )

    # Delete used OTP
    otp_collection.delete_one({"email": email})

    # Get company and issue JWT
    company = companies_collection.find_one({"email": email})
    token   = generate_token(company)

    return jsonify({
        "success"     : True,
        "message"     : "Email verified successfully",
        "token"       : token,
        "company_name": company["company_name"]
    }), 200

# ── POST /api/auth/login ──────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    body     = request.get_json(silent=True) or {}
    email    = body.get("email", "").lower().strip()
    password = body.get("password", "")
    totp_code = body.get("totp_code")

    print(f"\n[DEBUG /api/auth/login] Received login request for: '{email}'")
    print(f"[DEBUG /api/auth/login] Database name in use: '{companies_collection.database.name}'")

    if not email or not password:
        print("[DEBUG /api/auth/login] 400: Missing email or password in request body")
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    company = companies_collection.find_one({"email": email})

    if not company:
        print(f"[DEBUG /api/auth/login] 401: User NOT found in '{companies_collection.name}' collection for email: '{email}'")
        return jsonify({"success": False, "error": "Invalid email or password"}), 401

    print(f"[DEBUG /api/auth/login] User found: company_id={company.get('_id')}, is_verified={company.get('is_verified')}")

    if not company.get("is_verified"):
        print(f"[DEBUG /api/auth/login] 403: User is not verified")
        return jsonify({"success": False, "error": "Please verify your email first"}), 403

    if not verify_password(password, company["password"]):
        print(f"[DEBUG /api/auth/login] 401: Password verification failed (bcrypt mismatch) for email: '{email}'")
        return jsonify({"success": False, "error": "Invalid email or password"}), 401

    if company.get("totp_enabled"):
        if not totp_code:
            print("[DEBUG /api/auth/login] 200: 2FA required for this account")
            return jsonify({
                "success": False,
                "requires_2fa": True,
                "message": "Enter your 2FA code"
            }), 200

        totp = pyotp.TOTP(company["totp_secret"])
        if not totp.verify(totp_code, valid_window=1):
            print("[DEBUG /api/auth/login] 401: 2FA TOTP verification failed")
            return jsonify({"success": False, "error": "Invalid 2FA code"}), 401

    print(f"[DEBUG /api/auth/login] 200: Login successful for email: '{email}'")
    token = generate_token(company)

    return jsonify({
        "success"     : True,
        "message"     : "Login successful",
        "token"       : token,
        "company_name": company["company_name"],
        "company_id"  : str(company["_id"])
    }), 200

# ── GET /api/auth/me ──────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
def me():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return jsonify({"success": False, "error": "Token required"}), 401
    try:
        from utils.auth_helper import decode_token
        payload = decode_token(token)
        return jsonify({"success": True, "company": payload}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 401

@auth_bp.route('/2fa/setup', methods=['POST'])
@jwt_required
def setup_2fa():
    current_company = get_current_company()
    company = companies_collection.find_one({
        "_id": ObjectId(current_company["company_id"])
    })
    if not company:
        return jsonify({"success": False, "error": "Company not found"}), 404

    # Generate a new secret (don't save it as active yet)
    secret = pyotp.random_base32()

    # Build the provisioning URI (what the QR code encodes)
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=company['email'],
        issuer_name='RecruitMate'
    )

    # Generate QR code image as base64 so the frontend can display it directly
    qr = qrcode.make(provisioning_uri)
    buffered = io.BytesIO()
    qr.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    # Store the secret temporarily (not yet marked as enabled)
    companies_collection.update_one(
        {'_id': company['_id']},
        {'$set': {'pending_totp_secret': secret}}
    )

    return {
        'success': True,
        'qr_code': f'data:image/png;base64,{qr_base64}',
        'secret': secret  # shown as text too, for manual entry
    }

@auth_bp.route('/2fa/enable', methods=['POST'])
@jwt_required
def enable_2fa():
    current_company = get_current_company()
    company = companies_collection.find_one({
        "_id": ObjectId(current_company["company_id"])
    })
    if not company:
        return jsonify({"success": False, "error": "Company not found"}), 404

    data = request.get_json(silent=True) or {}
    code = data.get('code')

    if not code:
        return {'success': False, 'error': 'Code is required'}, 400

    pending_secret = company.get('pending_totp_secret')
    if not pending_secret:
        return {'success': False, 'error': 'No 2FA setup in progress. Call /2fa/setup first.'}, 400

    totp = pyotp.TOTP(pending_secret)
    if not totp.verify(code):
        return {'success': False, 'error': 'Invalid code. Check your authenticator app and try again.'}, 400

    # Code matched — promote pending secret to the real, active one
    companies_collection.update_one(
        {'_id': company['_id']},
        {
            '$set': {'totp_secret': pending_secret, 'totp_enabled': True},
            '$unset': {'pending_totp_secret': ''}
        }
    )

    return {'success': True, 'message': '2FA enabled successfully'}

@auth_bp.route('/2fa/status', methods=['GET'])
@jwt_required
def status_2fa():
    current_company = get_current_company()
    company = companies_collection.find_one({
        "_id": ObjectId(current_company["company_id"])
    })
    if not company:
        return jsonify({"success": False, "error": "Company not found"}), 404

    return {"success": True, "enabled": bool(company.get("totp_enabled"))}

@auth_bp.route('/2fa/disable', methods=['POST'])
@jwt_required
def disable_2fa():
    current_company = get_current_company()
    company = companies_collection.find_one({
        "_id": ObjectId(current_company["company_id"])
    })
    if not company:
        return jsonify({"success": False, "error": "Company not found"}), 404

    data = request.get_json(silent=True) or {}
    password = data.get("password")

    if not password:
        return jsonify({"success": False, "error": "Password is required"}), 400

    if not verify_password(password, company.get("password", "")):
        return jsonify({"success": False, "error": "Invalid password"}), 401

    companies_collection.update_one(
        {"_id": company["_id"]},
        {"$set": {"totp_enabled": False}, "$unset": {"totp_secret": ""}}
    )

    return {"success": True, "message": "2FA disabled"}
