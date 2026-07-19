import os
import json
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ── LLM singleton ────────────────────────────────────────────────────────────
_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0.3
)

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
_FENCE = re.compile(r"```(?:json)?\s*|\s*```")

def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip()

def _invoke(content: str) -> str:
    return _llm.invoke(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": content}
        ]
    ).content

# ── Rule-based decision engine ───────────────────────────────────────────────
def _decide_next_step(overall_score: int, role_level: str, hiring_recommendation: str) -> dict:
    """
    Pure logic — no LLM needed here.
    Returns next_step and decision.
    """
    level     = role_level.lower() if role_level.lower() in _THRESHOLDS else "mid"
    threshold = _THRESHOLDS[level]

    # Map recommendation to a weight
    rec_map = {
        "strongly recommend": 2,
        "recommend"         : 1,
        "on the fence"      : 0,
        "do not recommend"  : -1
    }
    rec_weight = rec_map.get(hiring_recommendation.lower(), 0)

    if overall_score >= threshold["l2"] and rec_weight >= 1:
        next_step = "L2 Technical Round"
        decision  = "advance"
    elif overall_score >= threshold["hr"] and rec_weight >= 0:
        next_step = "HR Round"
        decision  = "advance"
    else:
        next_step = "Rejected"
        decision  = "reject"

    # Schedule 3 business days from now
    scheduled_dt = datetime.now(timezone.utc) + timedelta(days=3)

    return {
        "next_step"     : next_step,
        "decision"      : decision,
        "scheduled_time": scheduled_dt.strftime("%Y-%m-%d %H:%M UTC"),
        "role_level"    : level,
        "score_used"    : overall_score
    }

# ── Main public function ─────────────────────────────────────────────────────
def schedule_next_step(
    candidate_data: dict,
    job_data      : dict,
    eval_data     : dict,   # output from answer_evaluator
    company_name  : str,
    role_level    : str = "mid"
) -> dict:
    """
    Input  : candidate_data, job_data, eval_data (from answer_evaluator),
             company_name, role_level ("junior"/"mid"/"senior")
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "..."}
    """
    raw = ""
    try:
        overall_score         = eval_data.get("overall_score", 0)
        hiring_recommendation = eval_data.get("hiring_recommendation", "on the fence")

        # Step 1 — Rule-based decision (no LLM, instant)
        schedule = _decide_next_step(overall_score, role_level, hiring_recommendation)

        # Step 2 — Generate notification email via LLM
        raw = _invoke(_NOTIFY_TEMPLATE.format(
            candidate_name=candidate_data.get("candidate_name", "Candidate"),
            job_title=job_data.get("job_title", ""),
            company_name=company_name,
            next_step=schedule["next_step"],
            scheduled_time=schedule["scheduled_time"],
            decision=schedule["decision"]
        ))

        email_content = json.loads(_clean(raw))

        return {
            "success": True,
            "data": {
                "candidate_name"      : candidate_data.get("candidate_name"),
                "candidate_email"     : candidate_data.get("candidate_email"),
                "next_step"           : schedule["next_step"],
                "decision"            : schedule["decision"],
                "scheduled_time"      : schedule["scheduled_time"],
                "role_level"          : schedule["role_level"],
                "overall_score"       : overall_score,
                "hiring_recommendation": hiring_recommendation,
                "notification_email"  : email_content
            }
        }

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e), "raw_response": raw}
