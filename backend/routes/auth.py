import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from utils.db import companies_collection, otp_collection
from utils.auth_helper import hash_password, verify_password, generate_token, generate_otp
from config import Config

auth_bp = Blueprint("auth", __name__)

# ── Send OTP email via Brevo ──────────────────────────────────────────────────
def send_otp_email(to_email: str, otp: str, company_name: str) -> bool:
    try:
        configuration         = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = Config.BREVO_API_KEY

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 32px;">
            <h2 style="color: #1f2937;">Welcome to RecruitMate AI</h2>
            <p>Hi <strong>{company_name}</strong>,</p>
            <p>Your email verification code is:</p>
            <div style="font-size: 36px; font-weight: bold; color: #2563eb;
                        letter-spacing: 8px; padding: 16px; background: #f3f4f6;
                        border-radius: 8px; text-align: center;">
                {otp}
            </div>
            <p style="color: #6b7280; margin-top: 16px;">
                This code expires in <strong>5 minutes</strong>. Do not share it with anyone.
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

        api_instance.send_transac_email(send_smtp_email)
        return True

    except ApiException as e:
        print(f"Brevo API error: {e}")
        return False
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ── POST /api/auth/register ───────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    body = request.get_json()

    required = {"email", "password", "company_name", "full_name"}
    missing  = required - body.keys()
    if missing:
        return jsonify({"success": False, "error": f"Missing fields: {missing}"}), 400

    email        = body["email"].lower().strip()
    password     = body["password"]
    company_name = body["company_name"].strip()
    full_name    = body["full_name"].strip()

    # Check if email already exists
    if companies_collection.find_one({"email": email}):
        return jsonify({"success": False, "error": "Email already registered"}), 409

    # Hash password and create company doc
    company_doc = {
        "email"       : email,
        "password"    : hash_password(password),
        "company_name": company_name,
        "full_name"   : full_name,
        "is_verified" : False,
        "created_at"  : datetime.now(timezone.utc)
    }

    inserted   = companies_collection.insert_one(company_doc)
    company_id = str(inserted.inserted_id)

    # Generate OTP
    otp = generate_otp()

    # Store OTP in DB with 5 minute expiry
    otp_collection.insert_one({
        "email"     : email,
        "otp"       : otp,
        "company_id": company_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)
    })

    # Send OTP email via Brevo
    email_sent = send_otp_email(email, otp, company_name)

    return jsonify({
        "success"   : True,
        "message"   : "Registration successful. Check your email for OTP.",
        "company_id": company_id,
        "email_sent": email_sent
    }), 201

# ── POST /api/auth/verify-otp ─────────────────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    body  = request.get_json()
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
    body     = request.get_json()
    email    = body.get("email", "").lower().strip()
    password = body.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    company = companies_collection.find_one({"email": email})

    if not company:
        return jsonify({"success": False, "error": "Invalid email or password"}), 401

    if not company.get("is_verified"):
        return jsonify({"success": False, "error": "Please verify your email first"}), 403

    if not verify_password(password, company["password"]):
        return jsonify({"success": False, "error": "Invalid email or password"}), 401

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