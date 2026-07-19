import os
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ── LLM singleton (loaded once, reused for every call) ──────────────────────
_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0.1
)

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

JOB DESCRIPTION:
{jd_text}"""

# ── Required fields for validation ──────────────────────────────────────────
_REQUIRED = {"job_title", "required_skills", "experience_required", "responsibilities"}

# ── Utility: strip ```json fences LLMs sometimes add ────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*|\s*```")

def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip()

# ── Main public function ─────────────────────────────────────────────────────
def parse_jd(jd_text: str) -> dict:
    """
    Input  : raw JD string (text / extracted from PDF or Word)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    raw = ""
    try:
        # Single LLM call — no chain overhead, minimal latency
        raw = _llm.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _TEMPLATE.format(jd_text=jd_text)}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        # Validate critical fields exist
        missing = _REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e), "raw_response": raw}
