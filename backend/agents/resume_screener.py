import os
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ── LLM singleton ────────────────────────────────────────────────────────────
_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0.1
)

# ── Prompts ──────────────────────────────────────────────────────────────────
_SYSTEM = "You are an expert technical recruiter. Return ONLY valid JSON. No markdown, no explanation."

_TEMPLATE = """Compare the resume below against the job requirements and score the candidate.

JOB TITLE: {job_title}
REQUIRED SKILLS: {required_skills}
EXPERIENCE REQUIRED: {experience_required}

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
_FENCE = re.compile(r"```(?:json)?\s*|\s*```")

def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip()

# ── Main public function ─────────────────────────────────────────────────────
def screen_resume(resume_text: str, job_data: dict) -> dict:
    """
    Input  : resume_text (str), job_data (dict from parse_jd)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    raw = ""
    try:
        raw = _llm.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _TEMPLATE.format(
                    job_title=job_data.get("job_title", ""),
                    required_skills=", ".join(job_data.get("required_skills", [])),
                    experience_required=job_data.get("experience_required", ""),
                    resume_text=resume_text
                )}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        # Validate critical fields
        missing = _REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        # Clamp score to valid range
        parsed["match_score"] = max(0, min(100, int(parsed["match_score"])))

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e), "raw_response": raw}
