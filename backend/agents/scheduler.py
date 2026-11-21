import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

_SYSTEM = "You are an HR scheduling assistant. Return ONLY valid JSON. No markdown, no explanation."

# ── Score thresholds → next step decision ────────────────────────────────────
_THRESHOLDS = {
    "senior" : {"l2": 75, "hr": 55},
    "mid"    : {"l2": 70, "hr": 50},
    "junior" : {"l2": 65, "hr": 45}
}

# ── Notification email template ──────────────────────────────────────────────
_NOTIFY_TEMPLATE = """Write a professional scheduling notification email for this candidate.

CANDIDATE NAME : {candidate_name}
JOB TITLE      : {job_title}
COMPANY NAME   : {company_name}
NEXT STEP      : {next_step}
SCHEDULED TIME : {scheduled_time}
DECISION       : {decision}

Rules:
- Write under company name, NOT HireFlow AI
- Be warm and professional
- If rejected, be respectful and encouraging
- If scheduling next round, be clear about what to expect

Return ONLY this JSON shape — no markdown fences:
{{
  "subject": "string",
  "body"   : "string"
}}"""

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

def _invoke(content: str) -> str:
    resp = _llm.invoke(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": content}
        ]
    )
    return resp.content or ""

# ── Rule-based decision engine ───────────────────────────────────────────────
def _decide_next_step(
    overall_score: int,
    role_level: str,
    hiring_recommendation: str,
    thresholds: dict = None
) -> dict:
    """
    Pure logic — no LLM needed here.
    Returns next_step and decision.
    """
    level = role_level.lower() if role_level.lower() in _THRESHOLDS else "mid"
    default_thresh = _THRESHOLDS[level]

    if thresholds and isinstance(thresholds.get(level), dict):
        lvl_cfg = thresholds[level]
        l2_thresh = lvl_cfg.get("l2_score", lvl_cfg.get("l2", default_thresh["l2"]))
        hr_thresh = lvl_cfg.get("hr_score", lvl_cfg.get("hr", default_thresh["hr"]))
    else:
        l2_thresh = default_thresh["l2"]
        hr_thresh = default_thresh["hr"]

    # Map recommendation to a weight
    rec_map = {
        "strongly recommend": 2,
        "recommend"         : 1,
        "on the fence"      : 0,
        "do not recommend"  : -1
    }
    rec_weight = rec_map.get((hiring_recommendation or "").lower(), 0)

    if overall_score >= l2_thresh and rec_weight >= 1:
        next_step = "L2 Technical Round"
        decision  = "advance"
    elif overall_score >= hr_thresh and rec_weight >= 0:
        next_step = "HR Round"
        decision  = "advance"
    else:
        next_step = "Rejected"
        decision  = "reject"

    # Schedule 3 business days from now
    scheduled_dt = datetime.now(timezone.utc) + timedelta(days=3)

    return {
        "next_step"           : next_step,
        "decision"            : decision,
        "recommended_decision": decision,
        "scheduled_time"      : scheduled_dt.strftime("%Y-%m-%d %H:%M UTC"),
        "role_level"          : level,
        "score_used"          : overall_score,
        "thresholds_used"     : {"l2": l2_thresh, "hr": hr_thresh}
    }

# ── Main public function ─────────────────────────────────────────────────────
def schedule_next_step(
    candidate_data: dict,
    job_data      : dict,
    eval_data     : dict,   # output from answer_evaluator
    company_name  : str,
    role_level    : str = "mid",
    thresholds    : dict = None,
    approval_mode : dict = None
) -> dict:
    """
    Input  : candidate_data, job_data, eval_data (from answer_evaluator),
             company_name, role_level ("junior"/"mid"/"senior")
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "..."}
    """
    raw = ""
    try:
        eval_data = eval_data or {}
        candidate_data = candidate_data or {}
        job_data = job_data or {}

        overall_score         = eval_data.get("overall_score", 0)
        hiring_recommendation = eval_data.get("hiring_recommendation") or "on the fence"

        # Step 1 — Rule-based decision (no LLM, instant)
        schedule = _decide_next_step(overall_score, role_level, hiring_recommendation, thresholds=thresholds)

        # Step 2 — Generate notification email via LLM
        prompt_content = _NOTIFY_TEMPLATE.format(
            candidate_name=candidate_data.get("candidate_name", "Candidate"),
            job_title=job_data.get("job_title", ""),
            company_name=company_name,
            next_step=schedule["next_step"],
            scheduled_time=schedule["scheduled_time"],
            decision=schedule["decision"]
        )

        res = call_llm(
            company_id=candidate_data.get("company_id"),
            agent_name="scheduler",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": prompt_content}
            ],
            heavy=False,
            temperature=0.3,
            expect_json=True
        )

        email_content = res.get("data", {}) if res.get("success") else {"subject": "Application Update", "body": f"Next step: {schedule['next_step']}"}

        auto_reject_requires_approval = bool((approval_mode or {}).get("auto_reject_requires_approval", False))
        res_data = {
            "candidate_name"      : candidate_data.get("candidate_name"),
            "candidate_email"     : candidate_data.get("candidate_email"),
            "job_title"           : job_data.get("job_title"),
            "next_step"           : schedule["next_step"],
            "decision"            : schedule["decision"],
            "recommended_decision": schedule["decision"],
            "scheduled_time"      : schedule["scheduled_time"],
            "role_level"          : schedule["role_level"],
            "score_used"          : schedule["score_used"],
            "overall_score"       : overall_score,
            "hiring_recommendation": hiring_recommendation,
            "email_subject"       : email_content.get("subject", ""),
            "email_body"          : email_content.get("body", ""),
            "notification_email"  : email_content
        }
        if schedule["decision"] == "reject" and auto_reject_requires_approval:
            res_data["status"] = "pending_review"
            res_data["review_reason"] = f"Evaluation score {overall_score} did not meet threshold for {schedule['role_level']} role"

        return {
            "success": True,
            "data": res_data
        }

    except json.JSONDecodeError as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [scheduler] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [scheduler] Error: {e}")
        return {"success": False, "error": str(e), "raw_response": raw}

