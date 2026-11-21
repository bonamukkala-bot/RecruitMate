import os
import sys
import json
import re
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

_SYSTEM = "You are an AI interviewer conducting a professional job interview. Return ONLY valid JSON. No markdown, no explanation."

# ── Templates ────────────────────────────────────────────────────────────────
_INTRO_TEMPLATE = """Generate a warm, professional interview introduction for this candidate.

CANDIDATE NAME : {candidate_name}
JOB TITLE      : {job_title}
COMPANY NAME   : {company_name}
TOTAL QUESTIONS: {total_questions}

Return ONLY this JSON shape — no markdown fences:
{{
  "introduction": "string",
  "instructions": "string"
}}"""

_FOLLOWUP_TEMPLATE = """You are conducting a live interview. Based on the candidate's answer, 
generate a natural follow-up response before moving to the next question.

CURRENT QUESTION : {current_question}
CANDIDATE ANSWER : {candidate_answer}
NEXT QUESTION    : {next_question}
IS LAST QUESTION : {is_last}

Rules:
- Acknowledge the answer briefly and professionally
- If last question, thank the candidate and close the interview
- If not last, transition smoothly to the next question
- Keep it concise (2-3 sentences max)

Return ONLY this JSON shape — no markdown fences:
{{
  "acknowledgment": "string",
  "transition": "string",
  "is_interview_complete": {is_last}
}}"""

_CLOSE_TEMPLATE = """Generate a professional closing statement for this interview.

CANDIDATE NAME : {candidate_name}
JOB TITLE      : {job_title}
COMPANY NAME   : {company_name}
QUESTIONS ASKED: {total_questions}

Return ONLY this JSON shape — no markdown fences:
{{
  "closing_statement": "string",
  "next_steps": "string"
}}"""

# ── Utility ──────────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    if not text:
        return ""
    # Strip <think> or <thought> reasoning blocks from reasoning models
    cleaned = re.sub(r"<(think|thought)>[\s\S]*?</\1>", "", text, flags=re.IGNORECASE).strip()

    # Extract JSON inside markdown code fence if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        return fence_match.group(1).strip()

    # Otherwise find outer JSON bounds ({...} or [...])
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")

    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        if last_brace != -1 and last_brace > first_brace:
            return cleaned[first_brace:last_brace + 1].strip()
    elif first_bracket != -1:
        if last_bracket != -1 and last_bracket > first_bracket:
            return cleaned[first_bracket:last_bracket + 1].strip()

    return cleaned.strip()

def _invoke(content: str, company_id: str = None) -> str:
    res = call_llm(
        company_id=company_id,
        agent_name="ai_interview",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": content}
        ],
        heavy=False,
        temperature=0.3,
        expect_json=False
    )
    return res.get("raw", "") if res.get("success") else ""

# ── Public functions ─────────────────────────────────────────────────────────
def start_interview(candidate_data: dict, job_data: dict, company_name: str, questions: dict) -> dict:
    """
    Generates the interview introduction and returns the first question.
    Input  : candidate_data, job_data, company_name, questions (from question_generator)
    Output : {"success": True, "data": {"introduction": "...", "first_question": {...}}}
    """
    raw = ""
    try:
        # Flatten all questions into ordered list
        all_questions = (
            questions.get("technical",  []) +
            questions.get("behavioral", []) +
            questions.get("gap_focused",[])
        )

        if not all_questions:
            raise ValueError("No questions provided to start interview.")

        raw = _invoke(_INTRO_TEMPLATE.format(
            candidate_name=candidate_data.get("candidate_name", "Candidate"),
            job_title=job_data.get("job_title", ""),
            company_name=company_name,
            total_questions=len(all_questions)
        ))

        parsed = json.loads(_clean(raw))

        return {
            "success": True,
            "data": {
                "introduction" : parsed.get("introduction", ""),
                "instructions" : parsed.get("instructions", ""),
                "first_question": all_questions[0],
                "total_questions": len(all_questions),
                "all_questions"  : all_questions
            }
        }

    except json.JSONDecodeError as e:
        print(f"❌ [ai_interview:start_interview] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        print(f"❌ [ai_interview:start_interview] Error: {e}")
        return {"success": False, "error": str(e)}


def next_question(current_question: str, candidate_answer: str, next_q: dict | None) -> dict:
    """
    Generates acknowledgment + transition to next question.
    Input  : current_question (str), candidate_answer (str), next_q (dict or None if last)
    Output : {"success": True, "data": {"acknowledgment": "...", "transition": "...", "is_interview_complete": bool}}
    """
    raw = ""
    try:
        is_last = next_q is None

        raw = _invoke(_FOLLOWUP_TEMPLATE.format(
            current_question=current_question,
            candidate_answer=candidate_answer,
            next_question=next_q.get("question", "") if next_q else "N/A",
            is_last=str(is_last).lower()
        ))

        parsed = json.loads(_clean(raw))

        return {
            "success": True,
            "data": {
                "acknowledgment"       : parsed.get("acknowledgment", ""),
                "transition"           : parsed.get("transition", ""),
                "next_question"        : next_q,
                "is_interview_complete": is_last
            }
        }

    except json.JSONDecodeError as e:
        print(f"❌ [ai_interview:start_interview] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        print(f"❌ [ai_interview:start_interview] Error: {e}")
        return {"success": False, "error": str(e)}


def close_interview(candidate_data: dict, job_data: dict, company_name: str, total_questions: int) -> dict:
    """
    Generates a professional closing statement.
    Input  : candidate_data, job_data, company_name, total_questions
    Output : {"success": True, "data": {"closing_statement": "...", "next_steps": "..."}}
    """
    raw = ""
    try:
        raw = _invoke(_CLOSE_TEMPLATE.format(
            candidate_name=candidate_data.get("candidate_name", "Candidate"),
            job_title=job_data.get("job_title", ""),
            company_name=company_name,
            total_questions=total_questions
        ))

        parsed = json.loads(_clean(raw))

        return {
            "success": True,
            "data": {
                "closing_statement": parsed.get("closing_statement", ""),
                "next_steps"       : parsed.get("next_steps", "")
            }
        }

    except json.JSONDecodeError as e:
        print(f"❌ [ai_interview:start_interview] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        print(f"❌ [ai_interview:start_interview] Error: {e}")
        return {"success": False, "error": str(e)}

