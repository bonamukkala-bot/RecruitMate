import copy
import time
import secrets
import hashlib
import html
import re
import traceback
from bson import ObjectId
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from config import Config
from utils.auth_helper import jwt_required, get_current_company, require_role, log_audit_event
from utils.db import (
    company_settings_collection,
    llm_usage_collection,
    team_members_collection,
    companies_collection,
    audit_logs_collection
)
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
from utils.llm import get_company_monthly_tokens, check_budget_limit

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
@require_role("admin")
def update_section(section: str):
    """
    Update a single settings section for the authenticated company.
    Requires 'admin' role or higher.
    """
    try:
        company = get_current_company()
        if not company or not company.get("company_id"):
            return jsonify({"success": False, "error": "Company authorization missing or expired"}), 401
        company_id = company.get("company_id")

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
            return jsonify({"success": False, "error": str(validated_or_err)}), 400

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

        log_audit_event(
            company_id=str(company_id),
            action=f"settings.{section}_update",
            target=section,
            details={"section": section}
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
@require_role("admin")
def reset_section(section: str):
    """
    Reset a specific settings section back to its default configuration.
    Requires 'admin' role or higher.
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

        log_audit_event(
            company_id=str(company_id),
            action=f"settings.{section}_reset",
            target=section,
            details={"section": section}
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
@require_role("admin")
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
@require_role("admin")
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

# ── GET /api/settings/ai/usage ────────────────────────────────────────────────
@settings_bp.route("/ai/usage", methods=["GET"])
@jwt_required
def get_ai_usage():
    """
    Fetches aggregated AI token usage metrics, budget status, agent/model breakdown,
    and daily timeseries for the authenticated company.
    Returns empty totals (zeros, empty lists) when llm_usage has no data or does not exist yet.
    """
    empty_totals = {
        "total_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
        "avg_latency_ms": 0,
        "failed_calls": 0,
        "failure_rate": 0.0
    }

    try:
        company = get_current_company()
        if not company or not company.get("company_id"):
            return jsonify({"success": False, "error": "Company authorization missing or expired"}), 401

        company_id = str(company.get("company_id"))
        settings = get_settings(company_id)
        ai_settings = settings.get("ai", {}) if isinstance(settings, dict) else {}
        budget = int(ai_settings.get("monthly_token_budget", 0) or 0)

        # Budget check
        used_month = 0
        budget_status = "normal"
        try:
            used_month = get_company_monthly_tokens(company_id)
            _, _, budget_status = check_budget_limit(company_id, budget)
        except Exception as b_err:
            print(f"⚠️ [get_ai_usage] budget check non-fatal error: {b_err}")

        budget_pct = round((used_month / budget) * 100.0, 1) if budget > 0 else 0.0

        now = datetime.now(timezone.utc)
        since_7d = now - timedelta(days=7)
        since_30d = now - timedelta(days=30)

        def _get_totals(since_date):
            try:
                pipeline = [
                    {"$match": {"company_id": company_id, "ts": {"$gte": since_date}}},
                    {"$group": {
                        "_id": None,
                        "total_calls": {"$sum": 1},
                        "prompt_tokens": {"$sum": "$prompt_tokens"},
                        "completion_tokens": {"$sum": "$completion_tokens"},
                        "total_tokens": {"$sum": "$total_tokens"},
                        "estimated_cost": {"$sum": "$estimated_cost"},
                        "avg_latency": {"$avg": "$latency_ms"},
                        "failed_calls": {
                            "$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}
                        }
                    }}
                ]
                res = list(llm_usage_collection.aggregate(pipeline))
                if not res:
                    return dict(empty_totals)
                row = res[0]
                total_calls = row.get("total_calls") or 0
                failed = row.get("failed_calls") or 0
                return {
                    "total_calls": total_calls,
                    "prompt_tokens": row.get("prompt_tokens") or 0,
                    "completion_tokens": row.get("completion_tokens") or 0,
                    "total_tokens": row.get("total_tokens") or 0,
                    "estimated_cost": round(float(row.get("estimated_cost") or 0.0), 4),
                    "avg_latency_ms": round(float(row.get("avg_latency") or 0.0), 1),
                    "failed_calls": failed,
                    "failure_rate": round((failed / total_calls) * 100.0, 1) if total_calls > 0 else 0.0
                }
            except Exception as e:
                print(f"⚠️ [_get_totals] aggregation fallback: {e}")
                return dict(empty_totals)

        totals_7d = _get_totals(since_7d)
        totals_30d = _get_totals(since_30d)

        # By Agent breakdown (last 30 days)
        by_agent = []
        try:
            agent_pipeline = [
                {"$match": {"company_id": company_id, "ts": {"$gte": since_30d}}},
                {"$group": {
                    "_id": "$agent",
                    "calls": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "estimated_cost": {"$sum": "$estimated_cost"},
                    "avg_latency": {"$avg": "$latency_ms"},
                    "failed": {"$sum": {"$cond": [{"$eq": ["$success", False]}, 1, 0]}}
                }},
                {"$sort": {"total_tokens": -1}}
            ]
            for r in llm_usage_collection.aggregate(agent_pipeline):
                by_agent.append({
                    "agent": r.get("_id") or "unknown",
                    "calls": r.get("calls") or 0,
                    "total_tokens": r.get("total_tokens") or 0,
                    "estimated_cost": round(float(r.get("estimated_cost") or 0.0), 4),
                    "avg_latency_ms": round(float(r.get("avg_latency") or 0.0), 1),
                    "failed": r.get("failed") or 0
                })
        except Exception as e:
            print(f"⚠️ [by_agent] aggregation fallback: {e}")

        # By Model breakdown (last 30 days)
        by_model = []
        try:
            model_pipeline = [
                {"$match": {"company_id": company_id, "ts": {"$gte": since_30d}}},
                {"$group": {
                    "_id": "$model",
                    "calls": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "estimated_cost": {"$sum": "$estimated_cost"},
                    "avg_latency": {"$avg": "$latency_ms"}
                }},
                {"$sort": {"total_tokens": -1}}
            ]
            for r in llm_usage_collection.aggregate(model_pipeline):
                by_model.append({
                    "model": r.get("_id") or "unknown",
                    "calls": r.get("calls") or 0,
                    "total_tokens": r.get("total_tokens") or 0,
                    "estimated_cost": round(float(r.get("estimated_cost") or 0.0), 4),
                    "avg_latency_ms": round(float(r.get("avg_latency") or 0.0), 1)
                })
        except Exception as e:
            print(f"⚠️ [by_model] aggregation fallback: {e}")

        # Daily timeseries (last 14 days)
        raw_daily = {}
        try:
            daily_pipeline = [
                {"$match": {"company_id": company_id, "ts": {"$gte": now - timedelta(days=14)}}},
                {"$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}
                    },
                    "tokens": {"$sum": "$total_tokens"},
                    "prompt_tokens": {"$sum": "$prompt_tokens"},
                    "completion_tokens": {"$sum": "$completion_tokens"},
                    "cost": {"$sum": "$estimated_cost"},
                    "calls": {"$sum": 1}
                }},
                {"$sort": {"_id": 1}}
            ]
            raw_daily = {r["_id"]: r for r in llm_usage_collection.aggregate(daily_pipeline) if r.get("_id")}
        except Exception as e:
            print(f"⚠️ [daily_timeseries] aggregation fallback: {e}")

        daily_timeseries = []
        for i in range(13, -1, -1):
            day_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            entry = raw_daily.get(day_str, {})
            daily_timeseries.append({
                "date": day_str,
                "tokens": entry.get("tokens") or 0,
                "prompt_tokens": entry.get("prompt_tokens") or 0,
                "completion_tokens": entry.get("completion_tokens") or 0,
                "cost": round(float(entry.get("cost") or 0.0), 4),
                "calls": entry.get("calls") or 0
            })

        return jsonify({
            "success": True,
            "budget": {
                "monthly_limit": budget,
                "used_tokens": used_month,
                "percentage": budget_pct,
                "status": budget_status
            },
            "totals_7d": totals_7d,
            "totals_30d": totals_30d,
            "by_agent": by_agent,
            "by_model": by_model,
            "daily_timeseries": daily_timeseries,
            "allowed_models": Config.GROQ_ALLOWED_MODELS
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to fetch AI usage: {str(e)}"}), 500

# ── Team Invitation Email Helper ──────────────────────────────────────────────
def send_invite_email(to_email: str, inviter_name: str, company_name: str, role: str, raw_token: str) -> tuple[bool, str]:
    """Sends a transactional team invitation email via Brevo."""
    if not Config.BREVO_API_KEY:
        err = "BREVO_API_KEY is not configured"
        print(f"[Brevo Invite] Error: {err}")
        return False, err

    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = Config.BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        accept_link = f"{Config.FRONTEND_URL}/accept-invite?token={raw_token}"
        escaped_company = html.escape(company_name or "RecruitMate Organization")
        escaped_inviter = html.escape(inviter_name or "A team administrator")
        escaped_role = html.escape(role.capitalize())

        html_content = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 540px; margin: auto; padding: 32px; border: 1px solid #e2e8f0; border-radius: 16px; background-color: #ffffff;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #0f172a; font-size: 22px; margin: 0;">Join {escaped_company}</h1>
                <p style="color: #64748b; font-size: 14px; margin-top: 6px;">RecruitMate Team Invitation</p>
            </div>
            <p style="color: #334155; font-size: 15px; line-height: 1.6;">
                Hi there,
            </p>
            <p style="color: #334155; font-size: 15px; line-height: 1.6;">
                <strong>{escaped_inviter}</strong> has invited you to join <strong>{escaped_company}</strong> as a <strong>{escaped_role}</strong>.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{accept_link}" style="background-color: #0284c7; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 10px; font-weight: 600; font-size: 15px; display: inline-block;">
                    Accept Invitation & Set Password
                </a>
            </div>
            <p style="color: #94a3b8; font-size: 13px; line-height: 1.5;">
                This invitation link will expire in 72 hours and can only be used once.<br>
                If you did not expect this invitation, you can safely ignore this email.
            </p>
            <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;" />
            <p style="color: #cbd5e1; font-size: 12px; margin: 0; text-align: center;">
                RecruitMate — Autonomous AI Hiring Platform
            </p>
        </div>
        """

        send_params = {
            "to": [{"email": to_email}],
            "sender": {
                "name": Config.BREVO_SENDER_NAME or "RecruitMate AI",
                "email": Config.BREVO_SENDER_EMAIL
            },
            "subject": f"Invitation to join {company_name} on RecruitMate",
            "html_content": html_content
        }
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        resp = api_instance.send_transac_email(send_smtp_email)
        message_id = getattr(resp, "message_id", str(resp))
        print(f"[Brevo Invite] Sent invitation to {to_email}. Message ID: {message_id}")
        return True, ""
    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo Invite] API Error - Status: {status_code}, Body: {body}")
        return False, f"Email provider error ({status_code})"
    except Exception as e:
        print(f"[Brevo Invite] Unexpected send failure: {e}")
        return False, str(e)

# ── GET /api/settings/team/members ────────────────────────────────────────────
@settings_bp.route("/team/members", methods=["GET"])
@jwt_required
def get_team_members():
    """
    List all team members for the company, including the company owner.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])

        # Fetch company owner
        owner = None
        try:
            owner = companies_collection.find_one({"_id": ObjectId(company_id)})
        except Exception:
            pass
        if not owner:
            owner = companies_collection.find_one({"_id": company_id})

        members_list = []
        if owner:
            owner_created = owner.get("created_at")
            if isinstance(owner_created, datetime):
                owner_created = owner_created.isoformat()
            members_list.append({
                "id": str(owner["_id"]),
                "name": owner.get("full_name") or owner.get("company_name", "Owner"),
                "email": owner["email"],
                "role": "owner",
                "status": "active",
                "is_owner": True,
                "created_at": owner_created,
                "last_login_at": None
            })

        # Fetch team members
        for m in team_members_collection.find({"company_id": company_id}).sort("created_at", -1):
            created_at = m.get("created_at")
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            last_login = m.get("last_login_at")
            if isinstance(last_login, datetime):
                last_login = last_login.isoformat()

            members_list.append({
                "id": str(m["_id"]),
                "name": m.get("name") or "",
                "email": m["email"],
                "role": m.get("role", "viewer"),
                "status": m.get("status", "invited"),
                "is_owner": False,
                "created_at": created_at,
                "last_login_at": last_login
            })

        return jsonify({
            "success": True,
            "members": members_list
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to fetch team members: {str(e)}"}), 500

# ── POST /api/settings/team/invite ────────────────────────────────────────────
@settings_bp.route("/team/invite", methods=["POST"])
@jwt_required
@require_role("admin")
def invite_team_member():
    """
    Invite a new team member. Generates a single-use token and sends an invite email.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])
        body = request.get_json(silent=True) or {}
        email = body.get("email", "").lower().strip()
        role = body.get("role", "recruiter").strip().lower()

        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        # Validate email format
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return jsonify({"success": False, "error": "Invalid email address format"}), 400

        valid_invite_roles = {"admin", "recruiter", "viewer"}
        if role not in valid_invite_roles:
            return jsonify({
                "success": False,
                "error": f"Invalid role '{role}'. Allowed invite roles: {sorted(list(valid_invite_roles))}"
            }), 400

        # Check if email is owner
        owner = companies_collection.find_one({"email": email})
        if owner:
            return jsonify({"success": False, "error": "This email belongs to a registered company owner"}), 400

        # Check existing team members
        existing = team_members_collection.find_one({"email": email})
        if existing:
            status = existing.get("status")
            if status == "active":
                return jsonify({"success": False, "error": "A team member with this email already exists"}), 400
            elif status == "invited":
                return jsonify({"success": False, "error": "An invitation is already pending for this email. Use Resend Invite."}), 400
            elif status == "disabled":
                return jsonify({"success": False, "error": "A team member with this email exists and is currently disabled"}), 400

        # Generate single-use token and store ONLY its hash
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(hours=72)

        member_doc = {
            "company_id": company_id,
            "email": email,
            "name": "",
            "role": role,
            "status": "invited",
            "password_hash": None,
            "invite_token_hash": token_hash,
            "invite_expires_at": expires_at,
            "created_at": now_utc,
            "invited_by": current.get("email")
        }

        inserted = team_members_collection.insert_one(member_doc)

        # Send Brevo email
        company_name = current.get("company_name", "RecruitMate Organization")
        inviter_name = current.get("name") or current.get("email") or "Administrator"
        email_sent, err_msg = send_invite_email(email, inviter_name, company_name, role, raw_token)

        log_audit_event(
            company_id=company_id,
            action="team.invite",
            target=email,
            details={"role": role, "email_sent": email_sent}
        )

        return jsonify({
            "success": True,
            "message": f"Invitation sent to {email}",
            "member_id": str(inserted.inserted_id),
            "email_sent": email_sent
        }), 201

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to invite team member: {str(e)}"}), 500

# ── PATCH /api/settings/team/members/<member_id>/role ─────────────────────────
@settings_bp.route("/team/members/<member_id>/role", methods=["PATCH"])
@jwt_required
@require_role("admin")
def update_member_role(member_id: str):
    """
    Update a team member's role.
    Owner role cannot be changed. Last admin rules prevent lockout.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])
        body = request.get_json(silent=True) or {}
        new_role = body.get("role", "").strip().lower()

        valid_roles = {"admin", "recruiter", "viewer"}
        if new_role not in valid_roles:
            return jsonify({
                "success": False,
                "error": f"Invalid role '{new_role}'. Allowed: {sorted(list(valid_roles))}"
            }), 400

        # Protect owner
        if member_id == company_id:
            return jsonify({"success": False, "error": "Company owner role cannot be changed"}), 400

        member = None
        try:
            member = team_members_collection.find_one({
                "_id": ObjectId(member_id),
                "company_id": company_id
            })
        except Exception:
            pass
        if not member:
            return jsonify({"success": False, "error": "Team member not found"}), 404

        old_role = member.get("role")
        if old_role == new_role:
            return jsonify({"success": True, "message": "Role unchanged"}), 200

        # Last admin lockout prevention
        if old_role == "admin" and new_role != "admin":
            admin_count = team_members_collection.count_documents({
                "company_id": company_id,
                "role": "admin",
                "status": {"$ne": "disabled"}
            })
            if admin_count <= 1:
                return jsonify({
                    "success": False,
                    "error": "Cannot demote the last remaining administrator"
                }), 400

        team_members_collection.update_one(
            {"_id": member["_id"]},
            {"$set": {"role": new_role, "updated_at": datetime.now(timezone.utc)}}
        )

        log_audit_event(
            company_id=company_id,
            action="team.role_change",
            target=member["email"],
            details={"old_role": old_role, "new_role": new_role}
        )

        return jsonify({
            "success": True,
            "message": f"Updated {member['email']} role to {new_role}"
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to update member role: {str(e)}"}), 500

# ── PATCH /api/settings/team/members/<member_id>/status ───────────────────────
@settings_bp.route("/team/members/<member_id>/status", methods=["PATCH"])
@jwt_required
@require_role("admin")
def update_member_status(member_id: str):
    """
    Disable or re-enable a team member.
    Owner cannot be disabled. Last admin rules prevent lockout.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])
        body = request.get_json(silent=True) or {}
        new_status = body.get("status", "").strip().lower()

        if new_status not in {"active", "disabled"}:
            return jsonify({"success": False, "error": "Status must be 'active' or 'disabled'"}), 400

        # Protect owner
        if member_id == company_id:
            return jsonify({"success": False, "error": "Company owner cannot be disabled"}), 400

        member = None
        try:
            member = team_members_collection.find_one({
                "_id": ObjectId(member_id),
                "company_id": company_id
            })
        except Exception:
            pass
        if not member:
            return jsonify({"success": False, "error": "Team member not found"}), 404

        # Last admin lockout prevention
        if new_status == "disabled" and member.get("role") == "admin":
            admin_count = team_members_collection.count_documents({
                "company_id": company_id,
                "role": "admin",
                "status": "active"
            })
            if admin_count <= 1:
                return jsonify({
                    "success": False,
                    "error": "Cannot disable the last active administrator"
                }), 400

        team_members_collection.update_one(
            {"_id": member["_id"]},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}}
        )

        log_audit_event(
            company_id=company_id,
            action="team.status_change",
            target=member["email"],
            details={"status": new_status}
        )

        return jsonify({
            "success": True,
            "message": f"Team member {member['email']} is now {new_status}"
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to update member status: {str(e)}"}), 500

# ── POST /api/settings/team/members/<member_id>/resend-invite ─────────────────
@settings_bp.route("/team/members/<member_id>/resend-invite", methods=["POST"])
@jwt_required
@require_role("admin")
def resend_invite(member_id: str):
    """
    Generate a fresh single-use invite token and resend the invitation email.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])

        member = None
        try:
            member = team_members_collection.find_one({
                "_id": ObjectId(member_id),
                "company_id": company_id
            })
        except Exception:
            pass
        if not member:
            return jsonify({"success": False, "error": "Team member not found"}), 404

        if member.get("status") != "invited":
            return jsonify({"success": False, "error": "Can only resend invitations to pending members"}), 400

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(hours=72)

        team_members_collection.update_one(
            {"_id": member["_id"]},
            {"$set": {
                "invite_token_hash": token_hash,
                "invite_expires_at": expires_at,
                "updated_at": now_utc
            }}
        )

        company_name = current.get("company_name", "RecruitMate Organization")
        inviter_name = current.get("name") or current.get("email") or "Administrator"
        email_sent, err_msg = send_invite_email(member["email"], inviter_name, company_name, member["role"], raw_token)

        log_audit_event(
            company_id=company_id,
            action="team.resend_invite",
            target=member["email"],
            details={"email_sent": email_sent}
        )

        return jsonify({
            "success": True,
            "message": f"Invitation resent to {member['email']}",
            "email_sent": email_sent
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to resend invitation: {str(e)}"}), 500

# ── DELETE /api/settings/team/members/<member_id> ─────────────────────────────
@settings_bp.route("/team/members/<member_id>", methods=["DELETE"])
@jwt_required
@require_role("admin")
def remove_team_member(member_id: str):
    """
    Permanently remove a team member.
    Owner cannot be removed. Last admin rules prevent lockout.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])

        # Protect owner
        if member_id == company_id:
            return jsonify({"success": False, "error": "Company owner cannot be removed"}), 400

        member = None
        try:
            member = team_members_collection.find_one({
                "_id": ObjectId(member_id),
                "company_id": company_id
            })
        except Exception:
            pass
        if not member:
            return jsonify({"success": False, "error": "Team member not found"}), 404

        # Last admin lockout prevention
        if member.get("role") == "admin":
            admin_count = team_members_collection.count_documents({
                "company_id": company_id,
                "role": "admin",
                "status": {"$ne": "disabled"}
            })
            if admin_count <= 1:
                return jsonify({
                    "success": False,
                    "error": "Cannot remove the last remaining administrator"
                }), 400

        team_members_collection.delete_one({"_id": member["_id"]})

        log_audit_event(
            company_id=company_id,
            action="team.remove",
            target=member["email"],
            details={"role": member.get("role")}
        )

        return jsonify({
            "success": True,
            "message": f"Team member {member['email']} removed"
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to remove member: {str(e)}"}), 500

# ── GET /api/settings/team/activity ───────────────────────────────────────────
@settings_bp.route("/team/activity", methods=["GET"])
@jwt_required
@require_role("admin")
def get_audit_activity():
    """
    Fetches the last 100 audit events for the company.
    """
    try:
        current = get_current_company()
        company_id = str(current["company_id"])

        logs = []
        for doc in audit_logs_collection.find({"company_id": company_id}).sort("ts", -1).limit(100):
            ts = doc.get("ts")
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            logs.append({
                "id": str(doc["_id"]),
                "actor": doc.get("actor", {}),
                "action": doc.get("action", ""),
                "target": str(doc.get("target") or ""),
                "details": doc.get("details", {}),
                "ts": ts
            })

        return jsonify({
            "success": True,
            "logs": logs
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to fetch activity logs: {str(e)}"}), 500
