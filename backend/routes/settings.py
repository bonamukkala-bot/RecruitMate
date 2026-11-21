import copy
import time
import traceback
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from config import Config
from utils.auth_helper import jwt_required, get_current_company
from utils.db import company_settings_collection
from utils.settings import (
    DEFAULT_SETTINGS,
    VALID_SECTIONS,
    get_settings,
    validate_section
)
from utils.email_renderer import (
    render_template,
    build_email_html,
    validate_template_variables
)

settings_bp = Blueprint("settings", __name__)

# In-memory rate limiting for test emails: {company_id: [timestamps]}
_TEST_EMAIL_HISTORY: dict[str, list[float]] = {}
MAX_TEST_EMAILS_PER_HOUR = 5

def _check_rate_limit(company_id: str) -> bool:
    now = time.time()
    cutoff = now - 3600
    timestamps = _TEST_EMAIL_HISTORY.get(company_id, [])
    timestamps = [t for t in timestamps if t > cutoff]
    if len(timestamps) >= MAX_TEST_EMAILS_PER_HOUR:
        _TEST_EMAIL_HISTORY[company_id] = timestamps
        return False
    timestamps.append(now)
    _TEST_EMAIL_HISTORY[company_id] = timestamps
    return True

# ── GET /api/settings ─────────────────────────────────────────────────────────
@settings_bp.route("", methods=["GET"])
@jwt_required
def get_all_settings():
    """
    Get all company settings, deep-merged with DEFAULT_SETTINGS.
    Always returns complete structure even if no settings document exists yet.
    """
    try:
        company = get_current_company()
        company_id = company.get("company_id")
        if not company_id:
            return jsonify({"success": False, "error": "Company ID missing from token"}), 400

        settings = get_settings(company_id)
        return jsonify({"success": True, "settings": settings}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to fetch settings: {str(e)}"}), 500

# ── PUT /api/settings/<section> ───────────────────────────────────────────────
@settings_bp.route("/<section>", methods=["PUT"])
@jwt_required
def update_section(section: str):
    """
    Update a single settings section for the authenticated company.
    Validates input schema and performs deep validation.
    """
    try:
        company = get_current_company()
        company_id = company.get("company_id")
        if not company_id:
            return jsonify({"success": False, "error": "Company ID missing from token"}), 400

        if section not in VALID_SECTIONS:
            return jsonify({
                "success": False,
                "error": f"Invalid section '{section}'. Allowed sections: {sorted(list(VALID_SECTIONS))}"
            }), 400

        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"success": False, "error": "Invalid JSON or missing request body"}), 400

        is_valid, validated_or_err = validate_section(section, payload)
        if not is_valid:
            return jsonify({"success": False, "error": validated_or_err}), 400

        now_utc = datetime.now(timezone.utc)
        updater_email = company.get("email", "unknown")

        company_settings_collection.update_one(
            {"company_id": str(company_id)},
            {
                "$set": {
                    section: validated_or_err,
                    "updated_at": now_utc,
                    "updated_by": updater_email
                }
            },
            upsert=True
        )

        return jsonify({
            "success": True,
            "message": f"{section.capitalize()} settings updated successfully",
            "section": section,
            "data": validated_or_err
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to update {section} settings: {str(e)}"}), 500

# ── POST /api/settings/<section>/reset ────────────────────────────────────────
@settings_bp.route("/<section>/reset", methods=["POST"])
@jwt_required
def reset_section(section: str):
    """
    Reset a specific settings section back to its default configuration.
    """
    try:
        company = get_current_company()
        company_id = company.get("company_id")
        if not company_id:
            return jsonify({"success": False, "error": "Company ID missing from token"}), 400

        if section not in VALID_SECTIONS:
            return jsonify({
                "success": False,
                "error": f"Invalid section '{section}'. Allowed sections: {sorted(list(VALID_SECTIONS))}"
            }), 400

        default_data = copy.deepcopy(DEFAULT_SETTINGS[section])
        now_utc = datetime.now(timezone.utc)
        updater_email = company.get("email", "unknown")

        company_settings_collection.update_one(
            {"company_id": str(company_id)},
            {
                "$set": {
                    section: default_data,
                    "updated_at": now_utc,
                    "updated_by": updater_email
                }
            },
            upsert=True
        )

        return jsonify({
            "success": True,
            "message": f"{section.capitalize()} settings reset to defaults",
            "section": section,
            "data": default_data
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to reset {section} settings: {str(e)}"}), 500

# ── POST /api/settings/email/preview ──────────────────────────────────────────
@settings_bp.route("/email/preview", methods=["POST"])
@jwt_required
def preview_email_template():
    """
    Renders an email template with sample context data.
    Accepts optional custom subject/body in payload, otherwise falls back to company settings.
    """
    try:
        company = get_current_company()
        company_id = company.get("company_id")
        settings = get_settings(company_id)
        email_settings = settings.get("email", {})
        templates = email_settings.get("templates", {})

        payload = request.get_json(silent=True) or {}
        template_type = payload.get("template_type", "interview_invite")
        valid_templates = {"interview_invite", "shortlist", "rejection", "otp_footer"}
        if template_type not in valid_templates:
            return jsonify({
                "success": False,
                "error": f"Invalid template_type '{template_type}'. Allowed: {sorted(list(valid_templates))}"
            }), 400

        company_name = company.get("company_name", "Acme Corp")
        sample_context = {
            "candidate_name": "Alex Mercer",
            "job_title": "Senior Python Engineer",
            "company_name": company_name,
            "next_step": "Technical Round",
            "date": "Nov 25, 2026, 10:00 AM UTC"
        }

        if template_type == "otp_footer":
            raw_footer = payload.get("body") or templates.get("otp_footer", "This code expires in 5 minutes. Do not share it with anyone.")
            valid_footer, err = validate_template_variables(raw_footer)
            if not valid_footer:
                return jsonify({"success": False, "error": err}), 400
            rendered_footer = render_template(raw_footer, sample_context, escape_html=True)
            subject = "RecruitMate AI — Your Verification Code"
            html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 500px; margin: auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 12px; background-color: #ffffff;">
                <h2 style="color: #111827; margin-top: 0;">Welcome to {company_name}</h2>
                <p style="color: #374151;">Hi <strong>Alex Mercer</strong>,</p>
                <p style="color: #374151;">Your email verification code is:</p>
                <div style="font-size: 36px; font-weight: bold; color: #2563eb;
                            letter-spacing: 8px; padding: 16px; background: #f3f4f6;
                            border-radius: 8px; text-align: center; margin: 16px 0;">
                    849201
                </div>
                <p style="color: #6b7280; margin-top: 16px; font-size: 14px;">
                    {rendered_footer}
                </p>
                <p style="color: #6b7280; font-size: 14px; margin-bottom: 0;">— {company_name} Team</p>
            </div>
            """
            return jsonify({
                "success": True,
                "preview": {
                    "subject": subject,
                    "body": rendered_footer,
                    "html": html
                }
            }), 200

        # General templates: interview_invite, shortlist, rejection
        default_tmpl = templates.get(template_type, {})
        subject = payload.get("subject") or default_tmpl.get("subject", "")
        body = payload.get("body") or default_tmpl.get("body", "")

        is_sub_valid, sub_err = validate_template_variables(subject)
        if not is_sub_valid:
            return jsonify({"success": False, "error": sub_err}), 400

        is_body_valid, body_err = validate_template_variables(body)
        if not is_body_valid:
            return jsonify({"success": False, "error": body_err}), 400

        rendered_sub = render_template(subject, sample_context, escape_html=False)
        rendered_body = render_template(body, sample_context, escape_html=False)

        button_text = "Start Your Interview" if template_type == "interview_invite" else None
        button_url = "https://recruitmate.app/interview/preview-token" if template_type == "interview_invite" else None
        details_box = [("Date", "Nov 25, 2026"), ("Time", "10:00 AM UTC"), ("Location", "Virtual Room 3")] if template_type == "shortlist" else None

        html_preview = build_email_html(
            rendered_body=rendered_body,
            company_name=company_name,
            button_text=button_text,
            button_url=button_url,
            details_box=details_box
        )

        return jsonify({
            "success": True,
            "preview": {
                "subject": rendered_sub,
                "body": rendered_body,
                "html": html_preview
            }
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to preview template: {str(e)}"}), 500

# ── POST /api/settings/email/send-test ────────────────────────────────────────
@settings_bp.route("/email/send-test", methods=["POST"])
@jwt_required
def send_test_email():
    """
    Sends a test email to the authenticated user's email address.
    Rate limited to 5 test emails per hour per company.
    """
    try:
        company = get_current_company()
        company_id = company.get("company_id")
        recipient_email = company.get("email")

        if not recipient_email:
            return jsonify({"success": False, "error": "User account has no associated email"}), 400

        if not _check_rate_limit(str(company_id)):
            return jsonify({
                "success": False,
                "error": f"Rate limit exceeded. Maximum {MAX_TEST_EMAILS_PER_HOUR} test emails per hour."
            }), 429

        settings = get_settings(company_id)
        email_settings = settings.get("email", {})
        templates = email_settings.get("templates", {})

        payload = request.get_json(silent=True) or {}
        template_type = payload.get("template_type", "interview_invite")
        valid_templates = {"interview_invite", "shortlist", "rejection", "otp_footer"}
        if template_type not in valid_templates:
            return jsonify({
                "success": False,
                "error": f"Invalid template_type '{template_type}'. Allowed: {sorted(list(valid_templates))}"
            }), 400

        company_name = company.get("company_name", "RecruitMate AI")
        sample_context = {
            "candidate_name": "Alex Mercer",
            "job_title": "Senior Python Engineer",
            "company_name": company_name,
            "next_step": "Technical Round",
            "date": "Nov 25, 2026, 10:00 AM UTC"
        }

        if template_type == "otp_footer":
            raw_footer = payload.get("body") or templates.get("otp_footer", "This code expires in 5 minutes. Do not share it with anyone.")
            rendered_footer = render_template(raw_footer, sample_context, escape_html=True)
            subject = "[TEST] RecruitMate AI — Your Verification Code"
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 500px; margin: auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 12px; background-color: #ffffff;">
                <h2 style="color: #111827; margin-top: 0;">Welcome to {company_name}</h2>
                <p style="color: #374151;">Hi <strong>Alex Mercer</strong>,</p>
                <p style="color: #374151;">Your email verification code is:</p>
                <div style="font-size: 36px; font-weight: bold; color: #2563eb;
                            letter-spacing: 8px; padding: 16px; background: #f3f4f6;
                            border-radius: 8px; text-align: center; margin: 16px 0;">
                    849201
                </div>
                <p style="color: #6b7280; margin-top: 16px; font-size: 14px;">
                    {rendered_footer}
                </p>
                <p style="color: #6b7280; font-size: 14px; margin-bottom: 0;">— {company_name} Team</p>
            </div>
            """
        else:
            default_tmpl = templates.get(template_type, {})
            subject_raw = payload.get("subject") or default_tmpl.get("subject", "")
            body_raw = payload.get("body") or default_tmpl.get("body", "")

            rendered_sub = render_template(subject_raw, sample_context, escape_html=False)
            rendered_body = render_template(body_raw, sample_context, escape_html=False)
            subject = f"[TEST] {rendered_sub}"

            button_text = "Start Your Interview" if template_type == "interview_invite" else None
            button_url = "https://recruitmate.app/interview/sample-token" if template_type == "interview_invite" else None
            details_box = [("Date", "Nov 25, 2026"), ("Time", "10:00 AM UTC"), ("Location", "Virtual Room 3")] if template_type == "shortlist" else None

            html_content = build_email_html(
                rendered_body=rendered_body,
                company_name=company_name,
                button_text=button_text,
                button_url=button_url,
                details_box=details_box
            )

        sender_name = email_settings.get("sender_name") or Config.BREVO_SENDER_NAME or "RecruitMate AI"
        reply_to = email_settings.get("reply_to", "").strip()

        if not Config.BREVO_API_KEY:
            return jsonify({
                "success": False,
                "error": "Email service (BREVO_API_KEY) is not configured in this environment"
            }), 503

        # Configure Brevo
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = Config.BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        send_params = {
            "to": [{"email": recipient_email, "name": company_name}],
            "sender": {
                "name": sender_name,
                "email": Config.BREVO_SENDER_EMAIL
            },
            "subject": subject,
            "html_content": html_content
        }
        if reply_to:
            send_params["reply_to"] = {"email": reply_to}

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        resp = api_instance.send_transac_email(send_smtp_email)
        message_id = getattr(resp, "message_id", str(resp))
        print(f"[Brevo Test] Sent test email to {recipient_email}. Message ID: {message_id}")

        return jsonify({
            "success": True,
            "message": f"Test email sent successfully to {recipient_email}"
        }), 200

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo Test] API Error - Status: {status_code}, Body: {body}")
        return jsonify({
            "success": False,
            "error": f"Email provider error ({status_code})"
        }), 502
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to send test email: {str(e)}"}), 500
