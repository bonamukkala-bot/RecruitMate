import os
import sys
import json
import re
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

# ── Prompts ──────────────────────────────────────────────────────────────────
_SYSTEM = "You are an expert technical recruiter. Return ONLY valid JSON. No markdown, no explanation."

_TEMPLATE = """Compare the resume below against the job requirements and score the candidate.

JOB TITLE: {job_title}
REQUIRED SKILLS: {required_skills}
EXPERIENCE REQUIRED: {experience_required}
{weights_section}
RESUME:
{resume_text}

Scoring rubric (use this exactly — do not deviate):
  90-100 = Exceptional match
  70-89  = Strong match
  50-69  = Partial match
  below 50 = Weak match

Return ONLY this JSON shape — no extra keys, no markdown fences:
{{
  "match_score": 0,
  "matched_skills": ["string"],
  "missing_skills": ["string"],
  "experience_match": true,
  "recommendation": "Shortlist",
  "reasoning": "string"
}}

recommendation must be exactly "Shortlist" or "Reject" — no other value."""

# ── Required fields for validation ──────────────────────────────────────────
_REQUIRED = {"match_score", "matched_skills", "missing_skills", "recommendation", "reasoning"}

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

# ── Main public function ─────────────────────────────────────────────────────
def screen_resume(resume_text: str, job_data: dict, scoring_weights: dict = None, company_id: str = None) -> dict:
    """
    Input  : resume_text (str), job_data (dict from parse_jd),
             optional scoring_weights (dict with skills, experience, education, projects)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    weights_section = ""
    if scoring_weights and isinstance(scoring_weights, dict):
        weights_section = (
            f"SCORING WEIGHTS TO FACTOR IN:\n"
            f"- Skills match: {scoring_weights.get('skills', 40)}%\n"
            f"- Experience match: {scoring_weights.get('experience', 30)}%\n"
            f"- Education match: {scoring_weights.get('education', 15)}%\n"
            f"- Projects: {scoring_weights.get('projects', 15)}%\n"
        )

    res = call_llm(
        company_id=company_id,
        agent_name="resume_screener",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _TEMPLATE.format(
                job_title=job_data.get("job_title", ""),
                required_skills=", ".join(job_data.get("required_skills", [])),
                experience_required=job_data.get("experience_required", ""),
                weights_section=weights_section,
                resume_text=resume_text
            )}
        ],
        heavy=True,
        temperature=0.1,
        expect_json=True,
        required_keys=_REQUIRED
    )
    if not res["success"]:
        return res

    parsed = res["data"]
    # Clamp score to valid range
    parsed["match_score"] = max(0, min(100, int(parsed["match_score"])))
    return {"success": True, "data": parsed}

