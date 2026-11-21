import os
import sys
import json
import re
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils.llm import call_llm

load_dotenv()

_SYSTEM = "You are a senior technical recruiter comparing shortlisted candidates for a role. Return ONLY valid JSON. No markdown, no explanation."

_TEMPLATE = """Compare these candidates for the same job and recommend which one the company should move forward with.
Be specific and evidence-based — reference actual matched/missing skills and scores, not generic praise.

JOB TITLE : {job_title}
JOB SKILLS REQUIRED : {job_skills}

CANDIDATES:
{candidates_block}

STRICT RULES:
- Pick exactly ONE candidate as the top recommendation by their "candidate_id" (matching the id given in the block above)
- Give clear reasoning referencing specific matched skills, missing skills, and scores from what's provided
- Also give a short one-line verdict for each of the OTHER (non-recommended) candidates, explaining why they ranked lower
- Do not invent skills or facts not present in the candidate data given
- Keep reasoning concise: 3-5 sentences for the main recommendation

Return ONLY this JSON shape — no markdown fences:
{{
  "recommended_candidate_id": "string",
  "recommendation_reasoning": "string",
  "other_candidates": [
    {{"candidate_id": "string", "verdict": "string"}}
  ]
}}"""

_REQUIRED = {"recommended_candidate_id", "recommendation_reasoning", "other_candidates"}

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

def _build_candidates_block(candidates: list) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f"- candidate_id: {c.get('_id')}\n"
            f"  name: {c.get('candidate_name')}\n"
            f"  match_score: {c.get('match_score', 0)}\n"
            f"  matched_skills: {', '.join(c.get('matched_skills', []))}\n"
            f"  missing_skills: {', '.join(c.get('missing_skills', []))}\n"
            f"  interview_score: {(c.get('evaluation') or {}).get('overall_score', 'N/A')}\n"
            f"  status: {c.get('status')}"
        )
    return "\n".join(lines)

def _compute_skill_overlap(candidates: list) -> dict:
    """
    Returns which skills are shared across ALL candidates, and which are
    unique to each candidate — used for the frontend's Venn-style visualization.
    """
    skill_sets = {
        str(c.get("_id")): set(s.lower() for s in c.get("matched_skills", []))
        for c in candidates
    }

    if not skill_sets:
        return {"shared_by_all": [], "unique": {}}

    common = set.intersection(*skill_sets.values()) if skill_sets else set()

    unique = {}
    for cid, skills in skill_sets.items():
        others = set()
        for other_id, other_skills in skill_sets.items():
            if other_id != cid:
                others |= other_skills
        unique[cid] = sorted(skills - others)

    return {
        "shared_by_all": sorted(common),
        "unique": unique
    }

def compare_candidates(candidates: list, job_data: dict, company_id: str = None) -> dict:
    """
    candidates: list of 2-3 candidate dicts (must include _id, candidate_name,
                match_score, matched_skills, missing_skills, evaluation, status)
    job_data: the job dict (must include job_title, and ideally required_skills)
    """
    if len(candidates) < 2:
        return {"success": False, "error": "At least 2 candidates are required to compare"}
    if len(candidates) > 3:
        return {"success": False, "error": "A maximum of 3 candidates can be compared at once"}

    job_skills = ", ".join(job_data.get("required_skills", []) or job_data.get("skills", []) or [])
    cid = company_id or (candidates[0].get("company_id") if candidates else None)

    res = call_llm(
        company_id=cid,
        agent_name="candidate_comparator",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": _TEMPLATE.format(
                job_title=job_data.get("job_title", ""),
                job_skills=job_skills,
                candidates_block=_build_candidates_block(candidates)
            )}
        ],
        heavy=False,
        temperature=0.4,
        expect_json=True,
        required_keys=_REQUIRED
    )
    if not res["success"]:
        return res

    parsed = res["data"]
    overlap = _compute_skill_overlap(candidates)

    return {
        "success": True,
        "data": {
            "recommended_candidate_id" : parsed["recommended_candidate_id"],
            "recommendation_reasoning" : parsed["recommendation_reasoning"],
            "other_candidates"         : parsed["other_candidates"],
            "skill_overlap"            : overlap
        }
    }
