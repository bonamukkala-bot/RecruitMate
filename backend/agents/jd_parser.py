import os
import sys
import json
import re
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

# ── Exact schema shown inline so the model never guesses the shape ───────────
_SYSTEM = "You are an expert HR analyst. Return ONLY valid JSON. No markdown, no explanation."

_TEMPLATE = """Extract structured data from the job description below.

Return ONLY this JSON shape — no extra keys, no markdown fences:
{{
  "job_title": "string",
  "required_skills": ["string"],
  "experience_required": "string",
  "responsibilities": ["string"],
  "qualifications": ["string"],
  "job_type": "string",
  "location": "string"
}}

Rules for the "location" field specifically:
- Only put a location if the job description actually names a real city, region, or "Remote" / "Hybrid" / "On-site" arrangement.
- If no location is mentioned anywhere in the text, set "location" to the exact string "Not specified". Do not invent one.
- Never output a placeholder, template variable, or bracketed value such as [City], [Location], TBD, or similar. Either a real value or exactly "Not specified".

JOB DESCRIPTION:
{jd_text}"""

# ── Required fields for validation ──────────────────────────────────────────
_REQUIRED = {"job_title", "required_skills", "experience_required", "responsibilities"}

# ── Utility: strip ```json fences LLMs sometimes add ────────────────────────
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

# ── Utility: catch any placeholder-style value the LLM slips through with ───
# Matches things like [City], [Location], {City}, <City>, TBD, N/A, etc.
_PLACEHOLDER_PATTERN = re.compile(
    r"^\s*(\[.*\]|\{.*\}|<.*>|TBD|N/?A|TODO|XXX+)\s*$",
    re.IGNORECASE
)

def _sanitize_location(value) -> str:
    if not isinstance(value, str) or not value.strip():
        return "Not specified"
    if _PLACEHOLDER_PATTERN.match(value.strip()):
        return "Not specified"
    return value.strip()

# ── Main public function ─────────────────────────────────────────────────────
def parse_jd(jd_text: str, company_id: str = None) -> dict:
    """
    Input  : raw JD string (text / extracted from PDF or Word)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    res = call_llm(
        company_id=company_id,
        agent_name="jd_parser",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _TEMPLATE.format(jd_text=jd_text)}
        ],
        heavy=False,
        temperature=0.1,
        expect_json=True,
        required_keys=_REQUIRED
    )
    if not res["success"]:
        return res

    parsed = res["data"]
    parsed["location"] = _sanitize_location(parsed.get("location"))
    return {"success": True, "data": parsed}
