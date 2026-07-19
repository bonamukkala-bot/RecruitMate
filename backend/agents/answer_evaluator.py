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
    temperature=0.2
)

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

_FENCE = re.compile(r"```(?:json)?\s*|\s*```")

def _clean(text: str) -> str:
    return _FENCE.sub("", text).strip()

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

        raw = _llm.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": content}
            ]
        ).content

        parsed = json.loads(_clean(raw))

        # Validate required fields
        missing = _REQUIRED[answer_type] - parsed.keys()
        if missing:
            raise ValueError(f"LLM omitted required fields: {missing}")

        # Clamp overall score to 0-100
        parsed["overall_score"] = max(0, min(100, int(parsed["overall_score"])))

        # Clamp per-question scores too
        if answer_type == "speech":
            for q in parsed.get("per_question", []):
                q["score"] = max(0, min(100, int(q.get("score", 0))))

        return {"success": True, "data": parsed}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON parse failed: {e}", "raw_response": raw}
    except Exception as e:
        return {"success": False, "error": str(e), "raw_response": raw}