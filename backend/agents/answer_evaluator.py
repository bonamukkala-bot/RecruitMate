import os
import sys
import json
import re
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

_SYSTEM = "You are a senior technical interviewer and evaluator. Return ONLY valid JSON. No markdown, no explanation."

# ── Templates per answer type ────────────────────────────────────────────────
_SPEECH_TEMPLATE = """Evaluate this candidate's spoken interview answers.

JOB TITLE     : {job_title}
CANDIDATE     : {candidate_name}
QUESTIONS & ANSWERS:
{qa_pairs}

Scoring rules (STRICTLY follow this):
- Score EACH answer out of 100
- overall_score MUST be out of 100 (average of all answer scores)
- 90-100 = Exceptional
- 70-89  = Strong
- 50-69  = Satisfactory
- below 50 = Weak

Evaluate based on:
- Clarity and communication
- Technical accuracy
- Depth of knowledge
- Confidence and relevance

Return ONLY this JSON shape — no markdown fences:
{{
  "overall_score": 75,
  "evaluation_type": "speech",
  "per_question": [
    {{"question": "string", "answer": "string", "score": 75, "feedback": "string"}}
  ],
  "strengths": ["string"],
  "weaknesses": ["string"],
  "hiring_recommendation": "Strongly Recommend / Recommend / On the Fence / Do Not Recommend",
  "summary": "string"
}}

IMPORTANT: overall_score and per question scores MUST be between 0 and 100."""

_CODE_TEMPLATE = """Evaluate this candidate's code submission for the given problem.

JOB TITLE     : {job_title}
CANDIDATE     : {candidate_name}
PROBLEM       : {problem}
CODE SUBMITTED:
{code}

Scoring rules (STRICTLY follow this):
- overall_score MUST be out of 100
- 90-100 = Exceptional
- 70-89  = Strong
- 50-69  = Satisfactory
- below 50 = Weak

Evaluate based on:
- Correctness (does it solve the problem?)
- Time complexity
- Space complexity
- Code readability and style
- Edge case handling

Return ONLY this JSON shape — no markdown fences:
{{
  "overall_score": 75,
  "evaluation_type": "code",
  "correctness": true,
  "time_complexity": "O(?)",
  "space_complexity": "O(?)",
  "code_quality": "string",
  "edge_cases_handled": true,
  "strengths": ["string"],
  "weaknesses": ["string"],
  "hiring_recommendation": "Strongly Recommend / Recommend / On the Fence / Do Not Recommend",
  "summary": "string"
}}

IMPORTANT: overall_score MUST be between 0 and 100."""

# ── Required fields per type ─────────────────────────────────────────────────
_REQUIRED = {
    "speech": {"overall_score", "per_question", "strengths", "weaknesses", "hiring_recommendation", "summary"},
    "code"  : {"overall_score", "correctness", "time_complexity", "hiring_recommendation", "summary"}
}

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
def evaluate_answers(
    candidate_data: dict,
    job_data      : dict,
    answer_type   : str,
    answers       : dict
) -> dict:
    """
    Input  : candidate_data, job_data, answer_type ("speech"/"code"), answers dict
    Output : {"success": True,  "data": {...}}
           | {"success": False, "error": "..."}
    """
    raw = ""
    try:
        if answer_type not in ("speech", "code"):
            raise ValueError(f"Invalid answer_type '{answer_type}'. Must be 'speech' or 'code'.")

        if answer_type == "speech":
            qa_text = "\n".join(
                f"Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}"
                for i, qa in enumerate(answers.get("qa_pairs", []))
            )
            content = _SPEECH_TEMPLATE.format(
                job_title=job_data.get("job_title", ""),
                candidate_name=candidate_data.get("candidate_name", "Candidate"),
                qa_pairs=qa_text
            )
        else:
            content = _CODE_TEMPLATE.format(
                job_title=job_data.get("job_title", ""),
                candidate_name=candidate_data.get("candidate_name", "Candidate"),
                problem=answers.get("problem", ""),
                code=answers.get("code", "")
            )

        res = call_llm(
            company_id=candidate_data.get("company_id"),
            agent_name="answer_evaluator",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": content}
            ],
            heavy=True,
            temperature=0.2,
            max_tokens=2048,
            expect_json=True,
            required_keys=_REQUIRED[answer_type]
        )
        if not res["success"]:
            return res

        parsed = res["data"]

        # Clamp overall score to 0-100
        parsed["overall_score"] = max(0, min(100, int(parsed["overall_score"])))

        # Clamp per-question scores too
        if answer_type == "speech":
            for q in parsed.get("per_question", []):
                q["score"] = max(0, min(100, int(q.get("score", 0))))

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        print(f"❌ [answer_evaluator] JSON parse failed: {e}\nRaw output: {raw}")
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        print(f"❌ [answer_evaluator] Error: {e}")
        return {"success": False, "error": str(e), "raw_response": raw}
