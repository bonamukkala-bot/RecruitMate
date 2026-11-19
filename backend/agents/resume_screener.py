import os
import sys
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

load_dotenv()

# ── LLM singleton ────────────────────────────────────────────────────────────
_llm = ChatGroq(
    api_key=Config.GROQ_API_KEY,
    model_name=Config.GROQ_MODEL_HEAVY,
    temperature=0.1,
    max_tokens=2048
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
def screen_resume(resume_text: str, job_data: dict) -> dict:
    """
    Input  : resume_text (str), job_data (dict from parse_jd)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    raw = ""
    try:
        resp = _llm.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _TEMPLATE.format(
                    job_title=job_data.get("job_title", ""),
                    required_skills=", ".join(job_data.get("required_skills", [])),
                    experience_required=job_data.get("experience_required", ""),
                    resume_text=resume_text
                )}
            ]
        )
        raw = resp.content or ""
        cleaned = _clean(raw)
        if not cleaned:
            raise ValueError("Empty response received from LLM.")

        parsed = json.loads(cleaned)

        # Validate critical fields
        missing = _REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        # Clamp score to valid range
        parsed["match_score"] = max(0, min(100, int(parsed["match_score"])))

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        print(f"❌ [resume_screener] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        print(f"❌ [resume_screener] Error: {e}")
        return {"success": False, "error": str(e), "raw_response": raw}

