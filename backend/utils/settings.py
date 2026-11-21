import copy
import re
from datetime import datetime, timezone
from config import Config
from utils.db import company_settings_collection
from utils.email_renderer import validate_template_variables

# ── Safety Check ─────────────────────────────────────────────────────────────
# Refuse any standalone/script execution if pointed at production
def assert_safe_db():
    if Config.DB_NAME == "recruitmate":
        raise RuntimeError("Operation prohibited: Connected to production database 'recruitmate'!")

# ── Default Settings ──────────────────────────────────────────────────────────
# These values reproduce the hardcoded default behavior across the codebase
DEFAULT_SETTINGS = {
    "hiring": {
        "thresholds": {
            "senior": {"advance_score": 75, "l2_score": 75, "hr_score": 55},
            "mid":    {"advance_score": 70, "l2_score": 70, "hr_score": 50},
            "junior": {"advance_score": 65, "l2_score": 65, "hr_score": 45}
        },
        "scoring_weights": {
            "skills": 40,
            "experience": 30,
            "education": 15,
            "projects": 15
        },
        "approval_mode": {
            "auto_reject_requires_approval": False
        }
    },
    "interview": {
        "duration_minutes": 30,
        "question_count": 8,
        "difficulty": "medium",          # "easy" | "medium" | "hard" | "adaptive"
        "question_types": "mixed",       # "technical" | "behavioral" | "mixed"
        "proctoring": {
            "enabled": True,
            "face_detection": True,
            "fullscreen_required": True,
            "tab_switch_violations_allowed": 1,
            "no_face_grace_seconds": 10,
            "terminate_on_violation": True
        }
    },
    "email": {
        "sender_name": "RecruitMate AI",
        "reply_to": "",
        "templates": {
            "interview_invite": {
                "subject": "Interview Invitation: {job_title} at {company_name}",
                "body": (
                    "Dear {candidate_name},\n\n"
                    "You have been shortlisted for an AI voice interview for the {job_title} role at {company_name}.\n\n"
                    "Please complete your interview by clicking your personal interview link.\n\n"
                    "Best regards,\n{company_name} Team"
                )
            },
            "shortlist": {
                "subject": "Application Update: {job_title} at {company_name}",
                "body": (
                    "Dear {candidate_name},\n\n"
                    "Congratulations! You have been advanced to the next round ({next_step}) for the {job_title} role at {company_name}.\n\n"
                    "Scheduled Time: {date}\n\n"
                    "Best regards,\n{company_name} Team"
                )
            },
            "rejection": {
                "subject": "Application Status: {job_title} at {company_name}",
                "body": (
                    "Dear {candidate_name},\n\n"
                    "Thank you for taking the time to interview for the {job_title} position at {company_name}. "
                    "After careful review, we have decided not to move forward with your application at this time.\n\n"
                    "We wish you all the best in your job search.\n\n"
                    "Best regards,\n{company_name} Team"
                )
            },
            "otp_footer": "This code expires in 5 minutes. Do not share it with anyone."
        },
        "notifications": {
            "notify_on_new_candidate": True,
            "notify_on_interview_complete": True,
            "notify_on_pending_review": True,
            "daily_digest": False
        }
    },
    "ai": {
        "model_default": Config.GROQ_MODEL or "openai/gpt-oss-20b",
        "model_heavy": Config.GROQ_MODEL_HEAVY or "openai/gpt-oss-120b",
        "output_language": "English",    # "English" | "Telugu" | "Hindi"
        "tone": "professional",          # "professional" | "friendly" | "concise"
        "temperature": 0.3
    },
    "privacy": {
        "data_retention_days": 0,        # 0 = keep forever, else 30-1095
        "consent_text": (
            "I consent to the collection and processing of my interview audio, "
            "video, and responses for the purpose of job application evaluation."
        ),
        "record_proctoring_events": True
    },
    "integrations": {
        "slack_webhook_url": "",
        "slack_events": {
            "new_candidate": False,
            "interview_complete": False,
            "pending_review": False
        },
        "webhook_url": "",
        "webhook_events": [],
        "google_calendar_enabled": False
    }
}

VALID_SECTIONS = set(DEFAULT_SETTINGS.keys())

# ── Deep Merge Utility ────────────────────────────────────────────────────────
def deep_merge(base: dict, update: dict) -> dict:
    """Recursively merge update dict into base dict."""
    merged = copy.deepcopy(base)
    for key, val in update.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = deep_merge(merged[key], val)
        else:
            merged[key] = copy.deepcopy(val)
    return merged

# ── Fetch Settings ────────────────────────────────────────────────────────────
def get_settings(company_id: str) -> dict:
    """
    Fetch stored company settings, deep-merged over DEFAULT_SETTINGS.
    Always returns all keys with defaults filled in.
    """
    if not company_id:
        return copy.deepcopy(DEFAULT_SETTINGS)

    doc = company_settings_collection.find_one({"company_id": str(company_id)})
    if not doc:
        return copy.deepcopy(DEFAULT_SETTINGS)

    # Remove mongo internals
    stored = {k: v for k, v in doc.items() if k in VALID_SECTIONS}
    merged = deep_merge(DEFAULT_SETTINGS, stored)
    return merged

# ── Section Validation ────────────────────────────────────────────────────────
def validate_section(section: str, data: dict) -> tuple[bool, str | dict]:
    """
    Validate a single settings section against its schema.
    Returns (True, sanitized_data) or (False, "error message").
    """
    if section not in VALID_SECTIONS:
        return False, f"Unknown settings section: '{section}'. Allowed: {sorted(list(VALID_SECTIONS))}"

    if not isinstance(data, dict):
        return False, "Section payload must be a JSON object"

    # Merge against section defaults to allow partial section updates
    merged = deep_merge(DEFAULT_SETTINGS[section], data)

    # 1. Hiring section validation
    if section == "hiring":
        thresholds = merged.get("thresholds", {})
        if not isinstance(thresholds, dict):
            return False, "thresholds must be an object"

        for role in ["senior", "mid", "junior"]:
            t = thresholds.get(role)
            if not isinstance(t, dict):
                return False, f"thresholds.{role} must be an object"
            if "advance_score" not in t or t.get("advance_score") is None:
                t["advance_score"] = t.get("l2_score", 70)
            for k in ["advance_score", "l2_score", "hr_score"]:
                val = t.get(k)
                if not isinstance(val, int) or val < 0 or val > 100:
                    return False, f"thresholds.{role}.{k} must be an integer between 0 and 100"
            if t["l2_score"] < t["hr_score"]:
                return False, f"thresholds.{role}: l2_score ({t['l2_score']}) cannot be lower than hr_score ({t['hr_score']})"

        weights = merged.get("scoring_weights", {})
        if not isinstance(weights, dict):
            return False, "scoring_weights must be an object"

        total_weight = 0
        for k in ["skills", "experience", "education", "projects"]:
            w = weights.get(k)
            if not isinstance(w, int) or w < 0 or w > 100:
                return False, f"scoring_weights.{k} must be an integer between 0 and 100"
            total_weight += w

        if total_weight != 100:
            return False, f"scoring_weights must sum to 100 (got {total_weight})"

        approval = merged.get("approval_mode", {})
        if not isinstance(approval, dict) or not isinstance(approval.get("auto_reject_requires_approval"), bool):
            return False, "approval_mode.auto_reject_requires_approval must be a boolean"

    # 2. Interview section validation
    elif section == "interview":
        duration = merged.get("duration_minutes")
        if not isinstance(duration, int) or duration < 5 or duration > 120:
            return False, "duration_minutes must be an integer between 5 and 120"

        q_count = merged.get("question_count")
        if not isinstance(q_count, int) or q_count < 3 or q_count > 20:
            return False, "question_count must be an integer between 3 and 20"

        allowed_diff = ["easy", "medium", "hard", "adaptive"]
        if merged.get("difficulty") not in allowed_diff:
            return False, f"difficulty must be one of {allowed_diff}"

        allowed_types = ["technical", "behavioral", "mixed"]
        if merged.get("question_types") not in allowed_types:
            return False, f"question_types must be one of {allowed_types}"

        proctoring = merged.get("proctoring", {})
        if not isinstance(proctoring, dict):
            return False, "proctoring must be an object"

        for b_key in ["enabled", "face_detection", "fullscreen_required", "terminate_on_violation"]:
            if not isinstance(proctoring.get(b_key), bool):
                return False, f"proctoring.{b_key} must be a boolean"

        tab_violations = proctoring.get("tab_switch_violations_allowed")
        if not isinstance(tab_violations, int) or tab_violations < 0 or tab_violations > 5:
            return False, "proctoring.tab_switch_violations_allowed must be an integer between 0 and 5"

        grace_secs = proctoring.get("no_face_grace_seconds")
        if not isinstance(grace_secs, int) or grace_secs < 0 or grace_secs > 60:
            return False, "proctoring.no_face_grace_seconds must be an integer between 0 and 60"

    # 3. Email section validation
    elif section == "email":
        sender = merged.get("sender_name", "")
        if not isinstance(sender, str) or len(sender.strip()) == 0 or len(sender) > 100:
            return False, "sender_name must be a non-empty string under 100 characters"

        reply_to = merged.get("reply_to", "").strip()
        if reply_to and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", reply_to):
            return False, "reply_to must be a valid email address or empty"

        templates = merged.get("templates", {})
        if not isinstance(templates, dict):
            return False, "templates must be an object"

        for tmpl in ["interview_invite", "shortlist", "rejection"]:
            t_obj = templates.get(tmpl)
            if not isinstance(t_obj, dict):
                return False, f"templates.{tmpl} must be an object"
            
            subject = t_obj.get("subject")
            if not isinstance(subject, str) or len(subject.strip()) == 0 or len(subject) > 150:
                return False, f"templates.{tmpl}.subject must be between 1 and 150 characters"
            
            body = t_obj.get("body")
            if not isinstance(body, str) or len(body.strip()) == 0 or len(body) > 5000:
                return False, f"templates.{tmpl}.body must be between 1 and 5000 characters"

            is_valid_sub, sub_err = validate_template_variables(subject)
            if not is_valid_sub:
                return False, f"templates.{tmpl}.subject: {sub_err}"

            is_valid_body, body_err = validate_template_variables(body)
            if not is_valid_body:
                return False, f"templates.{tmpl}.body: {body_err}"

        otp_footer = templates.get("otp_footer")
        if not isinstance(otp_footer, str) or len(otp_footer) > 500:
            return False, "templates.otp_footer must be a string up to 500 characters"
        is_valid_footer, footer_err = validate_template_variables(otp_footer)
        if not is_valid_footer:
            return False, f"templates.otp_footer: {footer_err}"

        notifications = merged.get("notifications", {})
        if not isinstance(notifications, dict):
            return False, "notifications must be an object"
        for n_key in ["notify_on_new_candidate", "notify_on_interview_complete", "notify_on_pending_review", "daily_digest"]:
            if not isinstance(notifications.get(n_key), bool):
                return False, f"notifications.{n_key} must be a boolean"

    # 4. AI section validation
    elif section == "ai":
        for str_key in ["model_default", "model_heavy"]:
            if not isinstance(merged.get(str_key), str) or not merged.get(str_key).strip():
                return False, f"{str_key} must be a non-empty string"

        allowed_lang = ["English", "Telugu", "Hindi"]
        if merged.get("output_language") not in allowed_lang:
            return False, f"output_language must be one of {allowed_lang}"

        allowed_tones = ["professional", "friendly", "concise"]
        if merged.get("tone") not in allowed_tones:
            return False, f"tone must be one of {allowed_tones}"

        temp = merged.get("temperature")
        if not isinstance(temp, (int, float)) or temp < 0.0 or temp > 1.0:
            return False, "temperature must be a number between 0.0 and 1.0"

    # 5. Privacy section validation
    elif section == "privacy":
        retention = merged.get("data_retention_days")
        if not isinstance(retention, int) or (retention != 0 and (retention < 30 or retention > 1095)):
            return False, "data_retention_days must be 0 (keep forever) or between 30 and 1095"

        consent = merged.get("consent_text")
        if not isinstance(consent, str) or len(consent.strip()) == 0 or len(consent) > 2000:
            return False, "consent_text must be a non-empty string up to 2000 characters"

        if not isinstance(merged.get("record_proctoring_events"), bool):
            return False, "record_proctoring_events must be a boolean"

    # 6. Integrations section validation
    elif section == "integrations":
        slack_url = merged.get("slack_webhook_url", "").strip()
        if slack_url and not slack_url.startswith("https://hooks.slack.com/"):
            return False, "slack_webhook_url must start with 'https://hooks.slack.com/' or be empty"

        slack_events = merged.get("slack_events", {})
        if not isinstance(slack_events, dict):
            return False, "slack_events must be an object"
        for s_key in ["new_candidate", "interview_complete", "pending_review"]:
            if not isinstance(slack_events.get(s_key), bool):
                return False, f"slack_events.{s_key} must be a boolean"

        wh_url = merged.get("webhook_url", "").strip()
        if wh_url and not (wh_url.startswith("https://") or wh_url.startswith("http://")):
            return False, "webhook_url must be a valid URL or empty"

        wh_events = merged.get("webhook_events")
        if not isinstance(wh_events, list):
            return False, "webhook_events must be a list"

        if not isinstance(merged.get("google_calendar_enabled"), bool):
            return False, "google_calendar_enabled must be a boolean"

    return True, merged
