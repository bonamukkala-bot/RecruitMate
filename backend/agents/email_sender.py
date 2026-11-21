import os
import sys
import json
import re
from datetime import datetime, timezone
from bson import ObjectId
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.settings import get_settings
from utils.email_renderer import render_template, build_email_html
from utils.db import companies_collection
from utils.llm import call_llm

load_dotenv()

# ── Brevo client setup ────────────────────────────────────────────────────────
_brevo_config = sib_api_v3_sdk.Configuration()
_brevo_config.api_key["api-key"] = os.getenv("BREVO_API_KEY")
_brevo_client = sib_api_v3_sdk.TransactionalEmailsApi(
    sib_api_v3_sdk.ApiClient(_brevo_config)
)

_BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
_BREVO_SENDER_NAME  = os.getenv("BREVO_SENDER_NAME", "RecruitMate AI")

# ── Prompts: Shortlist email ──────────────────────────────────────────────────
_SYSTEM = "You are a professional HR communication specialist. Return ONLY valid JSON. No markdown, no explanation."

_TEMPLATE = """Write a warm, professional shortlist notification email for this candidate.

CANDIDATE NAME  : {candidate_name}
CANDIDATE EMAIL : {candidate_email}
JOB TITLE       : {job_title}
COMPANY NAME    : {company_name}
MATCH SCORE     : {match_score}%
MATCHED SKILLS  : {matched_skills}

STRICT RULES:
- Write under the company's name, NOT HireFlow AI or RecruitMate AI
- Do NOT reveal interview questions or match score in the email
- Keep it concise, warm, and professional
- End with a clear call-to-action (confirm availability)

Return ONLY this JSON shape — no markdown fences:
{{
  "subject": "string",
  "greeting": "string",
  "body": "string",
  "call_to_action": "string",
  "sign_off": "string"
}}"""

_REQUIRED = {"subject", "greeting", "body", "call_to_action", "sign_off"}

# ── Prompts: Interview invitation email ───────────────────────────────────────
_INTERVIEW_SYSTEM = "You are a professional HR communication specialist writing an interview invitation. Return ONLY valid JSON. No markdown, no explanation."

_INTERVIEW_TEMPLATE = """Write a warm, professional, and slightly creative interview invitation email for this candidate.
Introduce the company briefly, express enthusiasm about their profile matching the role, and explain that
this is an AI-powered voice interview they can complete at their convenience via the link provided.

CANDIDATE NAME  : {candidate_name}
JOB TITLE       : {job_title}
COMPANY NAME    : {company_name}
MATCHED SKILLS  : {matched_skills}

STRICT RULES:
- Write under the company's name, NOT RecruitMate AI
- Briefly introduce what the company does or the spirit of the role, in 1-2 sentences (keep it generic/positive if no company description is available)
- Mention this is a short AI-conducted voice interview (4 questions, ~10 minutes total)
- Do NOT reveal the actual interview questions
- Keep tone warm, professional, and encouraging — not stiff or robotic
- Do NOT include the interview link yourself — it will be inserted separately after your "body" text

Return ONLY this JSON shape — no markdown fences:
{{
  "subject": "string",
  "greeting": "string",
  "body": "string",
  "sign_off": "string"
}}"""

_INTERVIEW_REQUIRED = {"subject", "greeting", "body", "sign_off"}

# ── Prompts: Rejection email ───────────────────────────────────────────────────
_REJECTION_SYSTEM = "You are a professional HR communication specialist writing a respectful rejection email. Return ONLY valid JSON. No markdown, no explanation."

_REJECTION_TEMPLATE = """Write a warm, respectful, professional rejection email for this candidate. This candidate is being
turned down at the stage indicated below. Keep the door open for future opportunities and thank them sincerely
for their time and interest.

CANDIDATE NAME  : {candidate_name}
JOB TITLE       : {job_title}
COMPANY NAME    : {company_name}
STAGE           : {stage}

STRICT RULES:
- Write under the company's name, NOT RecruitMate AI
- Do NOT reveal any score, numeric evaluation, or specific reasons for rejection
- Do NOT sound robotic or generic — keep it kind, human, and encouraging
- Thank them for their time and interest in the role
- Mention that the company will keep their profile on file for future openings that may be a better fit
- Keep it concise — 3-4 short sentences in the body is enough

Return ONLY this JSON shape — no markdown fences:
{{
  "subject": "string",
  "greeting": "string",
  "body": "string",
  "sign_off": "string"
}}"""

_REJECTION_REQUIRED = {"subject", "greeting", "body", "sign_off"}

# ── Utility ──────────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<(think|thought)>[\s\S]*?</\1>", "", text, flags=re.IGNORECASE).strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        return fence_match.group(1).strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        return cleaned[first_brace:last_brace + 1].strip()
    return cleaned.strip()

def _build_html(parts: dict, company_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 8px;">
        <h2 style="color: #1f2937;">{parts['greeting']}</h2>
        <p style="color: #374151; line-height: 1.7;">{parts['body']}</p>
        <p style="color: #374151; line-height: 1.7;">{parts['call_to_action']}</p>
        <br/>
        <p style="color: #374151;">{parts['sign_off']}</p>
        <p style="color: #6b7280; font-weight: bold;">{company_name} Talent Acquisition Team</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-top: 24px;"/>
        <p style="font-size: 12px; color: #9ca3af;">This email was sent by {company_name}. Please do not reply directly.</p>
    </div>
    """

def _build_interview_html(parts: dict, company_name: str, interview_url: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 8px;">
        <h2 style="color: #1f2937;">{parts['greeting']}</h2>
        <p style="color: #374151; line-height: 1.7;">{parts['body']}</p>
        <div style="text-align: center; margin: 28px 0;">
            <a href="{interview_url}" style="background-color: #3b82f6; color: #ffffff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">
                Start Your Interview
            </a>
        </div>
        <p style="color: #6b7280; font-size: 13px; line-height: 1.6;">
            Or copy this link into your browser:<br/>
            <span style="color: #3b82f6;">{interview_url}</span>
        </p>
        <br/>
        <p style="color: #374151;">{parts['sign_off']}</p>
        <p style="color: #6b7280; font-weight: bold;">{company_name} Talent Acquisition Team</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-top: 24px;"/>
        <p style="font-size: 12px; color: #9ca3af;">This email was sent by {company_name}. Please do not reply directly. This link expires in 3 days.</p>
    </div>
    """

def _build_offline_html(parts: dict, company_name: str, interview_date: str, interview_time: str, location: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 8px;">
        <h2 style="color: #1f2937;">{parts['greeting']}</h2>
        <p style="color: #374151; line-height: 1.7;">{parts['body']}</p>
        <div style="background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 20px; margin: 24px 0;">
            <p style="margin: 0 0 8px 0; color: #166534; font-weight: bold;">Interview Details</p>
            <p style="margin: 4px 0; color: #374151;"><strong>Date:</strong> {interview_date}</p>
            <p style="margin: 4px 0; color: #374151;"><strong>Time:</strong> {interview_time}</p>
            <p style="margin: 4px 0; color: #374151;"><strong>Location:</strong> {location}</p>
        </div>
        <p style="color: #374151; line-height: 1.7;">Please bring a valid ID and try to arrive 10 minutes early.</p>
        <br/>
        <p style="color: #374151;">{parts['sign_off']}</p>
        <p style="color: #6b7280; font-weight: bold;">{company_name} Talent Acquisition Team</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-top: 24px;"/>
        <p style="font-size: 12px; color: #9ca3af;">This email was sent by {company_name}. Please do not reply directly.</p>
    </div>
    """

def _build_rejection_html(parts: dict, company_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 32px; border: 1px solid #e5e7eb; border-radius: 8px;">
        <h2 style="color: #1f2937;">{parts['greeting']}</h2>
        <p style="color: #374151; line-height: 1.7;">{parts['body']}</p>
        <br/>
        <p style="color: #374151;">{parts['sign_off']}</p>
        <p style="color: #6b7280; font-weight: bold;">{company_name} Talent Acquisition Team</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin-top: 24px;"/>
        <p style="font-size: 12px; color: #9ca3af;">This email was sent by {company_name}. Please do not reply directly.</p>
    </div>
    """

# ── Step 1: Generate shortlist email content via LLM ──────────────────────────
def generate_email_content(candidate_data: dict, job_data: dict, screen_data: dict, company_name: str) -> dict:
    company_id = candidate_data.get("company_id")
    return call_llm(
        company_id=company_id,
        agent_name="email_sender",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _TEMPLATE.format(
                candidate_name=candidate_data.get("candidate_name", "Candidate"),
                candidate_email=candidate_data.get("candidate_email", ""),
                job_title=job_data.get("job_title", ""),
                company_name=company_name,
                match_score=screen_data.get("match_score", 0),
                matched_skills=", ".join(screen_data.get("matched_skills", []))
            )}
        ],
        heavy=False,
        temperature=0.7,
        expect_json=True,
        required_keys=_REQUIRED
    )

# ── Step 2: Send shortlist email via Brevo ────────────────────────────────────
def send_email(candidate_data: dict, job_data: dict, screen_data: dict, company_name: str, from_email: str) -> dict:
    try:
        company_id = candidate_data.get("company_id") if isinstance(candidate_data, dict) else None
        settings = get_settings(company_id) if company_id else None
        email_settings = settings.get("email", {}) if settings else {}
        sender_name = email_settings.get("sender_name") or Config.BREVO_SENDER_NAME or _BREVO_SENDER_NAME
        reply_to = email_settings.get("reply_to", "").strip() if email_settings else ""

        result = generate_email_content(candidate_data, job_data, screen_data, company_name)
        if not result["success"]:
            return result

        parts     = result["data"]
        html_body = _build_html(parts, company_name)

        sender_email = from_email or Config.BREVO_SENDER_EMAIL or _BREVO_SENDER_EMAIL

        send_params = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": candidate_data.get("candidate_email")}],
            "subject": parts["subject"],
            "html_content": html_body
        }
        if reply_to:
            send_params["reply_to"] = {"email": reply_to}

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Shortlist email sent successfully",
            "email_id": response.message_id,
            "subject" : parts["subject"]
        }

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo Email] API Error - Status: {status_code}, Body: {body}")
        return {"success": False, "error": f"Brevo API error: {status_code}", "details": str(body)}
    except Exception as e:
        print(f"[Brevo Email] Unexpected error: {e}")
        return {"success": False, "error": str(e)}

# ── Step 3: Generate interview invitation content via LLM ────────────────────
def generate_interview_email_content(candidate_data: dict, job_data: dict, company_name: str, matched_skills: list) -> dict:
    company_id = candidate_data.get("company_id")
    return call_llm(
        company_id=company_id,
        agent_name="email_sender",
        messages=[
            {"role": "system", "content": _INTERVIEW_SYSTEM},
            {"role": "user",   "content": _INTERVIEW_TEMPLATE.format(
                candidate_name=candidate_data.get("candidate_name", "Candidate"),
                job_title=job_data.get("job_title", "") if job_data else "",
                company_name=company_name,
                matched_skills=", ".join(matched_skills or [])
            )}
        ],
        heavy=False,
        temperature=0.7,
        expect_json=True,
        required_keys=_INTERVIEW_REQUIRED
    )

# ── Step 4: Send interview invitation email via Brevo ─────────────────────────
def send_interview_link_email(candidate_data: dict, job_data: dict, company_name: str, interview_url: str, from_email: str, matched_skills: list = None) -> dict:
    """
    Generates an interview invitation (using company's custom template if configured,
    or LLM generation as fallback) and sends it via Brevo with the interview link.
    """
    try:
        company_id = candidate_data.get("company_id") if isinstance(candidate_data, dict) else None
        settings = get_settings(company_id) if company_id else None
        email_settings = settings.get("email", {}) if settings else {}
        sender_name = email_settings.get("sender_name") or Config.BREVO_SENDER_NAME or _BREVO_SENDER_NAME
        reply_to = email_settings.get("reply_to", "").strip() if email_settings else ""
        templates = email_settings.get("templates", {}) if email_settings else {}

        subject = None
        html_body = None

        custom_invite = templates.get("interview_invite")
        if custom_invite and isinstance(custom_invite, dict) and custom_invite.get("subject") and custom_invite.get("body"):
            context = {
                "candidate_name": candidate_data.get("candidate_name", "Candidate"),
                "job_title": job_data.get("job_title", "") if job_data else "",
                "company_name": company_name,
                "next_step": "AI Voice Interview",
                "date": datetime.now(timezone.utc).strftime("%B %d, %Y")
            }
            subject = render_template(custom_invite["subject"], context, escape_html=False)
            rendered_body = render_template(custom_invite["body"], context, escape_html=False)
            html_body = build_email_html(
                rendered_body=rendered_body,
                company_name=company_name,
                button_text="Start Your Interview",
                button_url=interview_url
            )
        else:
            result = generate_interview_email_content(candidate_data, job_data, company_name, matched_skills or [])
            if not result["success"]:
                return result
            parts = result["data"]
            subject = parts["subject"]
            html_body = _build_interview_html(parts, company_name, interview_url)

        sender_email = from_email or Config.BREVO_SENDER_EMAIL or _BREVO_SENDER_EMAIL

        send_params = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": candidate_data.get("candidate_email")}],
            "subject": subject,
            "html_content": html_body
        }
        if reply_to:
            send_params["reply_to"] = {"email": reply_to}

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Interview invitation sent successfully",
            "email_id": response.message_id,
            "subject" : subject
        }

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo Email] API Error - Status: {status_code}, Body: {body}")
        return {"success": False, "error": f"Brevo API error: {status_code}", "details": str(body)}
    except Exception as e:
        print(f"[Brevo Email] Unexpected error: {e}")
        return {"success": False, "error": str(e)}

# ── Prompts: Offline interview confirmation email ─────────────────────────────
_OFFLINE_SYSTEM = "You are a professional HR communication specialist writing a final interview confirmation. Return ONLY valid JSON. No markdown, no explanation."

_OFFLINE_TEMPLATE = """Write a warm, professional email congratulating this candidate on being shortlisted after
their AI screening interview, and confirming their in-person offline interview details.

CANDIDATE NAME   : {candidate_name}
JOB TITLE        : {job_title}
COMPANY NAME     : {company_name}
INTERVIEW DATE   : {interview_date}
INTERVIEW TIME   : {interview_time}
LOCATION         : {location}

STRICT RULES:
- Write under the company's name, NOT RecruitMate AI
- Clearly congratulate them on being shortlisted
- Clearly state the date, time, and location as separate, easy-to-spot details (do not bury them in a paragraph)
- Mention they should bring a valid ID and arrive 10 minutes early
- Keep tone warm, professional, and encouraging
- Do NOT include the date/time/location yourself inside "body" — they will be inserted separately as a details block after your "body" text

Return ONLY this JSON shape — no markdown fences:
{{
  "subject": "string",
  "greeting": "string",
  "body": "string",
  "sign_off": "string"
}}"""

_OFFLINE_REQUIRED = {"subject", "greeting", "body", "sign_off"}

# ── Step 5: Generate offline interview email content via LLM ─────────────────
def generate_offline_email_content(candidate_data: dict, job_data: dict, company_name: str, interview_date: str, interview_time: str, location: str) -> dict:
    company_id = candidate_data.get("company_id")
    return call_llm(
        company_id=company_id,
        agent_name="email_sender",
        messages=[
            {"role": "system", "content": _OFFLINE_SYSTEM},
            {"role": "user",   "content": _OFFLINE_TEMPLATE.format(
                candidate_name=candidate_data.get("candidate_name", "Candidate"),
                job_title=job_data.get("job_title", "") if job_data else "",
                company_name=company_name,
                interview_date=interview_date,
                interview_time=interview_time,
                location=location
            )}
        ],
        heavy=False,
        temperature=0.7,
        expect_json=True,
        required_keys=_OFFLINE_REQUIRED
    )

# ── Step 6: Send offline interview confirmation email via Brevo ──────────────
def send_shortlist_offline_email(candidate_data: dict, job_data: dict, company_name: str, interview_date: str, interview_time: str, location: str, from_email: str) -> dict:
    try:
        company_id = candidate_data.get("company_id") if isinstance(candidate_data, dict) else None
        settings = get_settings(company_id) if company_id else None
        email_settings = settings.get("email", {}) if settings else {}
        sender_name = email_settings.get("sender_name") or Config.BREVO_SENDER_NAME or _BREVO_SENDER_NAME
        reply_to = email_settings.get("reply_to", "").strip() if email_settings else ""
        templates = email_settings.get("templates", {}) if email_settings else {}

        subject = None
        html_body = None

        custom_shortlist = templates.get("shortlist")
        if custom_shortlist and isinstance(custom_shortlist, dict) and custom_shortlist.get("subject") and custom_shortlist.get("body"):
            context = {
                "candidate_name": candidate_data.get("candidate_name", "Candidate"),
                "job_title": job_data.get("job_title", "") if job_data else "",
                "company_name": company_name,
                "next_step": "In-person Interview",
                "date": f"{interview_date} at {interview_time}"
            }
            subject = render_template(custom_shortlist["subject"], context, escape_html=False)
            rendered_body = render_template(custom_shortlist["body"], context, escape_html=False)
            html_body = build_email_html(
                rendered_body=rendered_body,
                company_name=company_name,
                details_box=[("Date", interview_date), ("Time", interview_time), ("Location", location)]
            )
        else:
            result = generate_offline_email_content(candidate_data, job_data, company_name, interview_date, interview_time, location)
            if not result["success"]:
                return result
            parts = result["data"]
            subject = parts["subject"]
            html_body = _build_offline_html(parts, company_name, interview_date, interview_time, location)

        sender_email = from_email or Config.BREVO_SENDER_EMAIL or _BREVO_SENDER_EMAIL

        send_params = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": candidate_data.get("candidate_email")}],
            "subject": subject,
            "html_content": html_body
        }
        if reply_to:
            send_params["reply_to"] = {"email": reply_to}

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Offline interview confirmation sent successfully",
            "email_id": response.message_id,
            "subject" : subject
        }

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo Email] API Error - Status: {status_code}, Body: {body}")
        return {"success": False, "error": f"Brevo API error: {status_code}", "details": str(body)}
    except Exception as e:
        print(f"[Brevo Email] Unexpected error: {e}")
        return {"success": False, "error": str(e)}

# ── Step 7: Generate rejection email content via LLM ──────────────────────────
def generate_rejection_email_content(candidate_data: dict, job_data: dict, company_name: str, stage: str) -> dict:
    company_id = candidate_data.get("company_id")
    return call_llm(
        company_id=company_id,
        agent_name="email_sender",
        messages=[
            {"role": "system", "content": _REJECTION_SYSTEM},
            {"role": "user",   "content": _REJECTION_TEMPLATE.format(
                candidate_name=candidate_data.get("candidate_name", "Candidate"),
                job_title=job_data.get("job_title", "") if job_data else "",
                company_name=company_name,
                stage=stage
            )}
        ],
        heavy=False,
        temperature=0.7,
        expect_json=True,
        required_keys=_REJECTION_REQUIRED
    )

# ── Step 8: Send rejection email via Brevo ─────────────────────────────────────
def send_rejection_email(candidate_data: dict, job_data: dict, company_name: str, from_email: str, stage: str = "resume screening") -> dict:
    """
    Generates and sends a respectful rejection email using custom settings or LLM generation.
    """
    try:
        company_id = candidate_data.get("company_id") if isinstance(candidate_data, dict) else None
        settings = get_settings(company_id) if company_id else None
        email_settings = settings.get("email", {}) if settings else {}
        sender_name = email_settings.get("sender_name") or Config.BREVO_SENDER_NAME or _BREVO_SENDER_NAME
        reply_to = email_settings.get("reply_to", "").strip() if email_settings else ""
        templates = email_settings.get("templates", {}) if email_settings else {}

        subject = None
        html_body = None

        custom_rejection = templates.get("rejection")
        if custom_rejection and isinstance(custom_rejection, dict) and custom_rejection.get("subject") and custom_rejection.get("body"):
            context = {
                "candidate_name": candidate_data.get("candidate_name", "Candidate"),
                "job_title": job_data.get("job_title", "") if job_data else "",
                "company_name": company_name,
                "next_step": "N/A",
                "date": datetime.now(timezone.utc).strftime("%B %d, %Y")
            }
            subject = render_template(custom_rejection["subject"], context, escape_html=False)
            rendered_body = render_template(custom_rejection["body"], context, escape_html=False)
            html_body = build_email_html(
                rendered_body=rendered_body,
                company_name=company_name
            )
        else:
            result = generate_rejection_email_content(candidate_data, job_data, company_name, stage)
            if not result["success"]:
                return result
            parts = result["data"]
            subject = parts["subject"]
            html_body = _build_rejection_html(parts, company_name)

        sender_email = from_email or Config.BREVO_SENDER_EMAIL or _BREVO_SENDER_EMAIL

        send_params = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": candidate_data.get("candidate_email")}],
            "subject": subject,
            "html_content": html_body
        }
        if reply_to:
            send_params["reply_to"] = {"email": reply_to}

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Rejection email sent successfully",
            "email_id": response.message_id,
            "subject" : subject
        }

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Brevo Email] API Error - Status: {status_code}, Body: {body}")
        return {"success": False, "error": f"Brevo API error: {status_code}", "details": str(body)}
    except Exception as e:
        print(f"[Brevo Email] Unexpected error: {e}")
        return {"success": False, "error": str(e)}

# ── Step 9: Send owner notifications ───────────────────────────────────────────
def send_owner_notification(company_id: str, event_type: str, details: dict) -> dict:
    """
    Sends an automated email notification to the company owner based on notification preferences.
    event_type: "new_candidate" | "interview_complete" | "pending_review"
    """
    if not company_id:
        return {"success": False, "error": "company_id required"}

    try:
        settings = get_settings(company_id)
        email_settings = settings.get("email", {})
        notifications = email_settings.get("notifications", {})

        pref_map = {
            "new_candidate": "notify_on_new_candidate",
            "interview_complete": "notify_on_interview_complete",
            "pending_review": "notify_on_pending_review"
        }

        pref_key = pref_map.get(event_type)
        if pref_key and not notifications.get(pref_key, True):
            print(f"[Owner Notification] Skipped {event_type} for company {company_id} (notification disabled)")
            return {"success": True, "skipped": True, "reason": "Notification disabled"}

        # Look up company owner email
        queries = [{"company_id": str(company_id)}]
        if ObjectId.is_valid(company_id):
            queries.append({"_id": ObjectId(company_id)})
        company = companies_collection.find_one({"$or": queries})

        if not company or not company.get("email"):
            print(f"[Owner Notification] No email found for company {company_id}")
            return {"success": False, "error": "Company owner email not found"}

        owner_email = company.get("email")
        company_name = company.get("company_name", "RecruitMate AI")

        if event_type == "new_candidate":
            cand_name = details.get("candidate_name", "A candidate")
            job_title = details.get("job_title", "Position")
            score = details.get("match_score", "N/A")
            subject = f"New Candidate Screened: {cand_name} ({job_title})"
            body = (
                f"Hello,\n\n"
                f"A new candidate has applied and completed resume screening:\n\n"
                f"• Candidate: {cand_name}\n"
                f"• Role: {job_title}\n"
                f"• Resume Match Score: {score}%\n\n"
                f"Log in to your RecruitMate dashboard to review their details."
            )
        elif event_type == "interview_complete":
            cand_name = details.get("candidate_name", "A candidate")
            job_title = details.get("job_title", "Position")
            score = details.get("score", "N/A")
            status = str(details.get("status", "completed"))
            subject = f"Interview Completed: {cand_name} ({job_title})"
            body = (
                f"Hello,\n\n"
                f"Candidate {cand_name} has just completed their AI voice interview for {job_title}:\n\n"
                f"• Candidate: {cand_name}\n"
                f"• Score: {score}%\n"
                f"• Outcome: {status.title()}\n\n"
                f"Log in to your RecruitMate dashboard to review the full audio transcript and integrity logs."
            )
        elif event_type == "pending_review":
            cand_name = details.get("candidate_name", "A candidate")
            job_title = details.get("job_title", "Position")
            reason = details.get("reason", "Needs manual decision")
            subject = f"Action Required: Candidate Needs Review - {cand_name}"
            body = (
                f"Hello,\n\n"
                f"A candidate requires your manual review before a final decision is made:\n\n"
                f"• Candidate: {cand_name}\n"
                f"• Role: {job_title}\n"
                f"• Reason: {reason}\n\n"
                f"Please visit the Candidates page and select 'Needs Review' to approve or override."
            )
        else:
            return {"success": False, "error": f"Unknown event_type {event_type}"}

        sender_name = email_settings.get("sender_name") or Config.BREVO_SENDER_NAME or _BREVO_SENDER_NAME
        reply_to = email_settings.get("reply_to", "").strip()

        html_content = build_email_html(body, company_name)

        if not Config.BREVO_API_KEY:
            print(f"[Owner Notification] BREVO_API_KEY not configured. Skipping email to {owner_email}")
            return {"success": True, "mock": True}

        sender_email = Config.BREVO_SENDER_EMAIL or _BREVO_SENDER_EMAIL
        send_params = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": owner_email, "name": company_name}],
            "subject": subject,
            "html_content": html_content
        }
        if reply_to:
            send_params["reply_to"] = {"email": reply_to}

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(**send_params)
        resp = _brevo_client.send_transac_email(send_smtp_email)
        message_id = getattr(resp, "message_id", str(resp))
        print(f"[Owner Notification] Sent {event_type} notification to {owner_email}. ID: {message_id}")
        return {"success": True, "email_id": message_id}

    except ApiException as e:
        status_code = getattr(e, "status", None)
        body = getattr(e, "body", str(e))
        print(f"[Owner Notification] API Error - Status: {status_code}, Body: {body}")
        return {"success": False, "error": f"Brevo API error ({status_code})"}
    except Exception as e:
        print(f"[Owner Notification] Unexpected error: {e}")
        return {"success": False, "error": str(e)}
