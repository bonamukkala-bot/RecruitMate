import os
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ── LLM singleton (higher temperature = creative, varied questions) ──────────
_llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile",
    temperature=0.7
)

_SYSTEM = "You are a senior technical interviewer. Return ONLY valid JSON. No markdown, no explanation."

_TEMPLATE = """Generate 8 personalized interview questions for this specific candidate.
DO NOT generate generic questions — tailor every question to their profile.

CANDIDATE NAME: {candidate_name}
JOB TITLE: {job_title}
MATCHED SKILLS: {matched_skills}
MISSING SKILLS: {missing_skills}
SCREENING REASONING: {reasoning}

Question categories:
- technical    : test their strong/matched skills deeply
- behavioral   : assess soft skills and teamwork
- gap_focused  : probe their missing skills without being harsh

Return ONLY this JSON shape — exactly 8 questions total, no markdown fences:
{{
  "candidate_name": "{candidate_name}",
  "job_title": "{job_title}",
  "questions": {{
    "technical": [
      {{"id": 1, "question": "string"}},
      {{"id": 2, "question": "string"}},
      {{"id": 3, "question": "string"}}
    ],
    "behavioral": [
      {{"id": 4, "question": "string"}},
      {{"id": 5, "question": "string"}},
      {{"id": 6, "question": "string"}}
    ],
    "gap_focused": [
      {{"id": 7, "question": "string"}},
      {{"id": 8, "question": "string"}}
    ]
  }}
}}"""

_REQUIRED   = {"candidate_name", "job_title", "questions"}
_CATEGORIES = {"technical", "behavioral", "gap_focused"}

_FENCE = re.compile(r"```(?:json)?\s*|\s*```")

def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip()

# ── Main public function ─────────────────────────────────────────────────────
def generate_questions(candidate_data: dict, job_data: dict, screen_data: dict) -> dict:
    """
    Input  : candidate_data, job_data (from parse_jd), screen_data (from screen_resume)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    raw = ""
    try:
        raw = _llm.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": _TEMPLATE.format(
                    candidate_name=candidate_data.get("candidate_name", "Candidate"),
                    job_title=job_data.get("job_title", ""),
                    matched_skills=", ".join(screen_data.get("matched_skills", [])),
                    missing_skills=", ".join(screen_data.get("missing_skills", [])),
                    reasoning=screen_data.get("reasoning", "")
                )}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        missing = _REQUIRED - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        missing_cats = _CATEGORIES - parsed["questions"].keys()
        if missing_cats:
            raise ValueError(f"LLM omitted question categories: {missing_cats}")

        total = sum(len(parsed["questions"][c]) for c in _CATEGORIES)
        if total != 8:
            raise ValueError(f"Expected 8 questions, got {total}")

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e), "raw_response": raw}
