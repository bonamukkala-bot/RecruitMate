import os
import json
import re
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ── Singletons ───────────────────────────────────────────────────────────────
_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0.7
)

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
_FENCE = re.compile(r"```(?:json)?\s*|\s*```")

def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip()

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
    raw = ""
    try:
        raw = _llm.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _TEMPLATE.format(
                    candidate_name=candidate_data.get("candidate_name", "Candidate"),
                    candidate_email=candidate_data.get("candidate_email", ""),
                    job_title=job_data.get("job_title", ""),
                    company_name=company_name,
                    match_score=screen_data.get("match_score", 0),
                    matched_skills=", ".join(screen_data.get("matched_skills", []))
                )}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        missing = _REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Step 2: Send shortlist email via Brevo ────────────────────────────────────
def send_email(candidate_data: dict, job_data: dict, screen_data: dict, company_name: str, from_email: str) -> dict:
    try:
        result = generate_email_content(candidate_data, job_data, screen_data, company_name)
        if not result["success"]:
            return result

        parts     = result["data"]
        html_body = _build_html(parts, company_name)

        sender_email = from_email or _BREVO_SENDER_EMAIL

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"name": _BREVO_SENDER_NAME, "email": sender_email},
            to=[{"email": candidate_data.get("candidate_email")}],
            subject=parts["subject"],
            html_content=html_body
        )

        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Shortlist email sent successfully",
            "email_id": response.message_id,
            "subject" : parts["subject"]
        }

    except ApiException as e:
        return {"success": False, "error": f"Brevo API error: {e.reason}", "details": str(e.body)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Step 3: Generate interview invitation content via LLM ────────────────────
def generate_interview_email_content(candidate_data: dict, job_data: dict, company_name: str, matched_skills: list) -> dict:
    raw = ""
    try:
        raw = _llm.invoke(
            [
                {"role": "system", "content": _INTERVIEW_SYSTEM},
                {"role": "user",   "content": _INTERVIEW_TEMPLATE.format(
                    candidate_name=candidate_data.get("candidate_name", "Candidate"),
                    job_title=job_data.get("job_title", "") if job_data else "",
                    company_name=company_name,
                    matched_skills=", ".join(matched_skills or [])
                )}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        missing = _INTERVIEW_REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Step 4: Send interview invitation email via Brevo ─────────────────────────
def send_interview_link_email(candidate_data: dict, job_data: dict, company_name: str, interview_url: str, from_email: str, matched_skills: list = None) -> dict:
    """
    Generates a warm, LLM-written interview invitation and sends it via Brevo,
    with the interview link embedded as a styled button + plain link.
    """
    try:
        result = generate_interview_email_content(candidate_data, job_data, company_name, matched_skills or [])
        if not result["success"]:
            return result

        parts     = result["data"]
        html_body = _build_interview_html(parts, company_name, interview_url)

        sender_email = from_email or _BREVO_SENDER_EMAIL

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"name": _BREVO_SENDER_NAME, "email": sender_email},
            to=[{"email": candidate_data.get("candidate_email")}],
            subject=parts["subject"],
            html_content=html_body
        )

        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Interview invitation sent successfully",
            "email_id": response.message_id,
            "subject" : parts["subject"]
        }

    except ApiException as e:
        return {"success": False, "error": f"Brevo API error: {e.reason}", "details": str(e.body)}
    except Exception as e:
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
    raw = ""
    try:
        raw = _llm.invoke(
            [
                {"role": "system", "content": _OFFLINE_SYSTEM},
                {"role": "user",   "content": _OFFLINE_TEMPLATE.format(
                    candidate_name=candidate_data.get("candidate_name", "Candidate"),
                    job_title=job_data.get("job_title", "") if job_data else "",
                    company_name=company_name,
                    interview_date=interview_date,
                    interview_time=interview_time,
                    location=location
                )}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        missing = _OFFLINE_REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Step 6: Send offline interview confirmation email via Brevo ──────────────
def send_shortlist_offline_email(candidate_data: dict, job_data: dict, company_name: str, interview_date: str, interview_time: str, location: str, from_email: str) -> dict:
    try:
        result = generate_offline_email_content(candidate_data, job_data, company_name, interview_date, interview_time, location)
        if not result["success"]:
            return result

        parts     = result["data"]
        html_body = _build_offline_html(parts, company_name, interview_date, interview_time, location)

        sender_email = from_email or _BREVO_SENDER_EMAIL

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"name": _BREVO_SENDER_NAME, "email": sender_email},
            to=[{"email": candidate_data.get("candidate_email")}],
            subject=parts["subject"],
            html_content=html_body
        )

        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Offline interview confirmation sent successfully",
            "email_id": response.message_id,
            "subject" : parts["subject"]
        }

    except ApiException as e:
        return {"success": False, "error": f"Brevo API error: {e.reason}", "details": str(e.body)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Step 7: Generate rejection email content via LLM ──────────────────────────
def generate_rejection_email_content(candidate_data: dict, job_data: dict, company_name: str, stage: str) -> dict:
    raw = ""
    try:
        raw = _llm.invoke(
            [
                {"role": "system", "content": _REJECTION_SYSTEM},
                {"role": "user",   "content": _REJECTION_TEMPLATE.format(
                    candidate_name=candidate_data.get("candidate_name", "Candidate"),
                    job_title=job_data.get("job_title", "") if job_data else "",
                    company_name=company_name,
                    stage=stage
                )}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        missing = _REJECTION_REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Step 8: Send rejection email via Brevo ─────────────────────────────────────
def send_rejection_email(candidate_data: dict, job_data: dict, company_name: str, from_email: str, stage: str = "resume screening") -> dict:
    """
    Generates and sends a respectful rejection email.
    `stage` should be either "resume screening" or "interview" so the LLM
    can phrase the email appropriately without revealing any score.
    """
    try:
        result = generate_rejection_email_content(candidate_data, job_data, company_name, stage)
        if not result["success"]:
            return result

        parts     = result["data"]
        html_body = _build_rejection_html(parts, company_name)

        sender_email = from_email or _BREVO_SENDER_EMAIL

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"name": _BREVO_SENDER_NAME, "email": sender_email},
            to=[{"email": candidate_data.get("candidate_email")}],
            subject=parts["subject"],
            html_content=html_body
        )

        response = _brevo_client.send_transac_email(send_smtp_email)

        return {
            "success" : True,
            "message" : "Rejection email sent successfully",
            "email_id": response.message_id,
            "subject" : parts["subject"]
        }

    except ApiException as e:
        return {"success": False, "error": f"Brevo API error: {e.reason}", "details": str(e.body)}
    except Exception as e:
        return {"success": False, "error": str(e)}