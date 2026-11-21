import os
import sys
import json
import re
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

_SYSTEM = "You are a senior technical interviewer. Return ONLY valid JSON. No markdown, no explanation."

def _get_category_distribution(total_count: int, question_types: str) -> dict:
    """Determine how many questions belong to each category based on settings."""
    q_type = (question_types or "mixed").lower()
    if q_type == "technical":
        return {"technical": total_count, "behavioral": 0, "gap_focused": 0}
    if q_type == "behavioral":
        return {"technical": 0, "behavioral": total_count, "gap_focused": 0}

    # "mixed" mode distribution:
    gap_count = max(1, total_count // 4)
    remaining = total_count - gap_count
    tech_count = remaining // 2 + (remaining % 2)
    beh_count = remaining - tech_count
    return {
        "technical": tech_count,
        "behavioral": beh_count,
        "gap_focused": gap_count
    }

def _build_prompt(
    candidate_name: str,
    job_title: str,
    matched_skills: str,
    missing_skills: str,
    reasoning: str,
    question_count: int,
    difficulty: str,
    question_types: str
) -> str:
    dist = _get_category_distribution(question_count, question_types)
    cat_desc = []
    if dist["technical"] > 0:
        cat_desc.append(f"- technical: {dist['technical']} questions probing deep technical and matched skills")
    if dist["behavioral"] > 0:
        cat_desc.append(f"- behavioral: {dist['behavioral']} questions evaluating teamwork, communication, and soft skills")
    if dist["gap_focused"] > 0:
        cat_desc.append(f"- gap_focused: {dist['gap_focused']} questions constructively exploring missing skills or growth areas")

    categories_text = "\n".join(cat_desc)

    return f"""Generate exactly {question_count} personalized interview questions for this specific candidate.
DO NOT generate generic questions — tailor every question to their profile.

CANDIDATE NAME: {candidate_name}
JOB TITLE: {job_title}
MATCHED SKILLS: {matched_skills}
MISSING SKILLS: {missing_skills}
SCREENING REASONING: {reasoning}
INTERVIEW DIFFICULTY: {difficulty} (calibrate question complexity, technical depth, and evaluation rigor accordingly)
QUESTION TYPES FOCUS: {question_types}

Required question distribution:
{categories_text}

Return ONLY this JSON shape — exactly {question_count} questions total, no markdown fences:
{{
  "candidate_name": "{candidate_name}",
  "job_title": "{job_title}",
  "difficulty": "{difficulty}",
  "questions": {{
    "technical": [
      {{"id": 1, "question": "string"}}
    ],
    "behavioral": [
      {{"id": 2, "question": "string"}}
    ],
    "gap_focused": [
      {{"id": 3, "question": "string"}}
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
def generate_questions(
    candidate_data: dict,
    job_data: dict,
    screen_data: dict,
    question_count: int = 8,
    difficulty: str = "medium",
    question_types: str = "mixed",
    interview_settings: dict = None
) -> dict:
    """
    Input  : candidate_data, job_data (from parse_jd), screen_data (from screen_resume),
             optional question_count (3-20), difficulty (easy/medium/hard/adaptive),
             question_types (technical/behavioral/mixed), or interview_settings dict.
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "...", "raw_response": "..."}
    """
    raw = ""
    try:
        candidate_data = candidate_data or {}
        job_data = job_data or {}
        screen_data = screen_data or {}

        if interview_settings and isinstance(interview_settings, dict):
            question_count = interview_settings.get("question_count", question_count)
            difficulty = interview_settings.get("difficulty", difficulty)
            question_types = interview_settings.get("question_types", question_types)

        # Enforce bounds
        count = max(3, min(20, int(question_count or 8)))
        diff = (difficulty or "medium").lower()
        if diff not in ["easy", "medium", "hard", "adaptive"]:
            diff = "medium"
        q_types = (question_types or "mixed").lower()
        if q_types not in ["technical", "behavioral", "mixed"]:
            q_types = "mixed"

        prompt = _build_prompt(
            candidate_name=candidate_data.get("candidate_name", "Candidate"),
            job_title=job_data.get("job_title", ""),
            matched_skills=", ".join(screen_data.get("matched_skills", [])),
            missing_skills=", ".join(screen_data.get("missing_skills", [])),
            reasoning=screen_data.get("reasoning", ""),
            question_count=count,
            difficulty=diff,
            question_types=q_types
        )

        res = call_llm(
            company_id=candidate_data.get("company_id"),
            agent_name="question_generator",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": prompt}
            ],
            heavy=False,
            temperature=0.7,
            max_tokens=4096,
            expect_json=True,
            required_keys=_REQUIRED
        )
        if not res["success"]:
            return res

        parsed = res["data"]

        if not isinstance(parsed.get("questions"), dict):
            return {
                "success": False,
                "error": "LLM response questions field must be a dictionary of categories",
                "raw_response": res.get("raw", "")
            }

        # Normalize categories to ensure all exist
        for cat in _CATEGORIES:
            if cat not in parsed["questions"] or not isinstance(parsed["questions"][cat], list):
                parsed["questions"][cat] = []

        # Count questions
        total = sum(len(parsed["questions"][c]) for c in _CATEGORIES)
        if total == 0:
            return {
                "success": False,
                "error": "LLM did not generate any interview questions",
                "raw_response": res.get("raw", "")
            }

        parsed["total"] = total
        parsed["question_count"] = count
        parsed["difficulty"] = diff
        parsed["question_types"] = q_types

        return {"success": True, "data": parsed}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [question_generator] Error: {e}")
        return {"success": False, "error": str(e), "raw_response": raw}

