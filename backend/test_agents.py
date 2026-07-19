import requests
import json

BASE = "http://127.0.0.1:5000/api"

# ── Sample data ──────────────────────────────────────────────────────────────
JD_TEXT = """
We are hiring a Python Backend Developer with 2+ years of experience.
Required Skills: Python, Flask, REST APIs, MongoDB, Docker.
Responsibilities: Build scalable APIs, manage databases, write clean code.
Qualifications: B.Sc Computer Science or equivalent.
Job Type: Full Time. Location: Hyderabad, India.
"""

RESUME_TEXT = """
Name: Charan B.
Skills: Python, Flask, REST APIs, MongoDB, Git, Linux.
Experience: 1.5 years building Flask APIs and MongoDB integrations.
Education: B.Sc Computer Science, NIAT Hyderabad.
Projects: IPL Win Predictor, CodeBuddy Chrome Extension.
"""

CANDIDATE_DATA = {
    "candidate_name" : "Charan B.",
    "candidate_email": "charan@example.com"
}

COMPANY_NAME = "RecruitMate"

def pretty(label, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2))

# ── Agent 1: JD Parser ────────────────────────────────────────────────────────
def test_jd_parser():
    r = requests.post(f"{BASE}/parse-jd", json={"jd_text": JD_TEXT})
    data = r.json()
    pretty("AGENT 1 — JD Parser", data)
    return data.get("data", {})

# ── Agent 2: Resume Screener ──────────────────────────────────────────────────
def test_resume_screener(job_data):
    r = requests.post(f"{BASE}/screen-resume", json={
        "resume_text": RESUME_TEXT,
        "job_data"   : job_data
    })
    data = r.json()
    pretty("AGENT 2 — Resume Screener", data)
    return data.get("data", {})

# ── Agent 3: Question Generator ───────────────────────────────────────────────
def test_question_generator(job_data, screen_data):
    r = requests.post(f"{BASE}/generate-questions", json={
        "candidate_data": CANDIDATE_DATA,
        "job_data"      : job_data,
        "screen_data"   : screen_data
    })
    data = r.json()
    pretty("AGENT 3 — Question Generator", data)
    return data.get("data", {})

# ── Agent 4: Email Sender ─────────────────────────────────────────────────────
def test_email_sender(job_data, screen_data):
    r = requests.post(f"{BASE}/send-email", json={
        "candidate_data": CANDIDATE_DATA,
        "job_data"      : job_data,
        "screen_data"   : screen_data,
        "company_name"  : COMPANY_NAME,
        "from_email"    : "onboarding@resend.dev"
    })
    data = r.json()
    pretty("AGENT 4 — Email Sender", data)
    return data

# ── Agent 5: Answer Evaluator ─────────────────────────────────────────────────
def test_answer_evaluator(job_data):
    r = requests.post(f"{BASE}/evaluate-answers", json={
        "candidate_data": CANDIDATE_DATA,
        "job_data"      : job_data,
        "answer_type"   : "speech",
        "answers"       : {
            "qa_pairs": [
                {"question": "Explain REST APIs", "answer": "REST APIs use HTTP methods like GET POST PUT DELETE to perform CRUD operations on resources."},
                {"question": "How does MongoDB differ from SQL?", "answer": "MongoDB stores data as JSON documents while SQL uses tables and rows with fixed schema."}
            ]
        }
    })
    data = r.json()
    pretty("AGENT 5 — Answer Evaluator", data)
    return data.get("data", {})

# ── Agent 6: AI Interviewer ───────────────────────────────────────────────────
def test_ai_interviewer(job_data, questions):
    # Start
    r = requests.post(f"{BASE}/interview/start", json={
        "candidate_data": CANDIDATE_DATA,
        "job_data"      : job_data,
        "company_name"  : COMPANY_NAME,
        "questions"     : questions.get("questions", {})
    })
    data = r.json()
    pretty("AGENT 6 — AI Interviewer (Start)", data)

    # Next question
    r2 = requests.post(f"{BASE}/interview/next", json={
        "current_question" : "Tell me about yourself",
        "candidate_answer" : "I am a CS student with Flask and MongoDB experience.",
        "next_question"    : {"id": 2, "question": "What is a REST API?"}
    })
    data2 = r2.json()
    pretty("AGENT 6 — AI Interviewer (Next)", data2)

    # Close
    r3 = requests.post(f"{BASE}/interview/close", json={
        "candidate_data" : CANDIDATE_DATA,
        "job_data"       : job_data,
        "company_name"   : COMPANY_NAME,
        "total_questions": 8
    })
    data3 = r3.json()
    pretty("AGENT 6 — AI Interviewer (Close)", data3)

# ── Agent 7: Scheduler ────────────────────────────────────────────────────────
def test_scheduler(job_data, eval_data):
    r = requests.post(f"{BASE}/schedule", json={
        "candidate_data": CANDIDATE_DATA,
        "job_data"      : job_data,
        "eval_data"     : eval_data,
        "company_name"  : COMPANY_NAME,
        "role_level"    : "junior"
    })
    data = r.json()
    pretty("AGENT 7 — Scheduler", data)

# ── Run all ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀 Testing all 7 RecruitMate AI Agents...\n")

    job_data    = test_jd_parser()
    screen_data = test_resume_screener(job_data)
    questions   = test_question_generator(job_data, screen_data)
    test_email_sender(job_data, screen_data)
    eval_data   = test_answer_evaluator(job_data)
    test_ai_interviewer(job_data, questions)
    test_scheduler(job_data, eval_data)

    print("\n✅ All agents tested successfully!")