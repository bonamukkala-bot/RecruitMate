import os
import sys
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

load_dotenv()

# ── LLM singleton (higher temperature = creative, varied questions) ──────────
_llm = ChatGroq(
    api_key=Config.GROQ_API_KEY,
    model_name=Config.GROQ_MODEL,
    temperature=0.7,
    max_tokens=2048
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
def generate_questions(candidate_data: dict, job_data: dict, screen_data: dict) -> dict:
    """
    Input  : candidate_data, job_data (from parse_jd), screen_data (from screen_resume)
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    raw = ""
    try:
        resp = _llm.invoke(
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
        )
        raw = resp.content or ""
        cleaned = _clean(raw)
        if not cleaned:
            raise ValueError("Empty response received from LLM.")

        parsed = json.loads(cleaned)

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
        print(f"❌ [question_generator] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        print(f"❌ [question_generator] Error: {e}")
        return {"success": False, "error": str(e), "raw_response": raw}

