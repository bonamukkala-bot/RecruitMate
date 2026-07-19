import requests
import json

BASE = "http://127.0.0.1:5000/api"

# ── Global state shared across tests ────────────────────────────────────────
state = {
    "token"       : None,
    "job_id"      : None,
    "candidate_id": None,
    "job_data"    : None,
    "screen_data" : None,
    "questions"   : None,
    "eval_data"   : None
}

def pretty(label, data):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(json.dumps(data, indent=2))

def auth_header():
    return {"Authorization": f"Bearer {state['token']}"}

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 — HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────
def test_health():
    r = requests.get(f"{BASE}/health")
    pretty("HEALTH CHECK", r.json())
    assert r.json()["status"] == "ok"

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 — AUTH
# ─────────────────────────────────────────────────────────────────────────────
def test_register():
    r = requests.post(f"{BASE}/auth/register", json={
        "email"       : "testcompany@gmail.com",
        "password"    : "Test1234",
        "company_name": "Test Company",
        "full_name"   : "Test User"
    })
    pretty("AUTH — Register", r.json())

def test_verify_otp():
    otp = input("\n>>> Check your email and enter the OTP here: ").strip()
    r   = requests.post(f"{BASE}/auth/verify-otp", json={
        "email": "testcompany@gmail.com",
        "otp"  : otp
    })
    data = r.json()
    pretty("AUTH — Verify OTP", data)
    if data.get("success"):
        state["token"] = data["token"]
        print(f"\n✅ Token saved: {state['token'][:30]}...")

def test_login():
    r = requests.post(f"{BASE}/auth/login", json={
        "email"   : "testcompany@gmail.com",
        "password": "Test1234"
    })
    data = r.json()
    pretty("AUTH — Login", data)
    if data.get("success"):
        state["token"] = data["token"]
        print(f"\n✅ Token saved: {state['token'][:30]}...")

def test_me():
    r = requests.get(f"{BASE}/auth/me", headers=auth_header())
    pretty("AUTH — Me", r.json())

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 — JOBS
# ─────────────────────────────────────────────────────────────────────────────
def test_create_job():
    r = requests.post(f"{BASE}/jobs/", headers=auth_header(), json={
        "jd_text": """
        We are hiring a Python Backend Developer with 2+ years experience.
        Required Skills: Python, Flask, MongoDB, Docker, REST APIs.
        Responsibilities: Build scalable APIs, manage databases, write clean code.
        Qualifications: B.Sc Computer Science or equivalent.
        Job Type: Full Time. Location: Hyderabad, India.
        """
    })
    data = r.json()
    pretty("JOBS — Create Job", data)
    if data.get("success"):
        state["job_id"]   = data["job_id"]
        state["job_data"] = data["job"]
        print(f"\n✅ Job ID saved: {state['job_id']}")

def test_get_jobs():
    r = requests.get(f"{BASE}/jobs/", headers=auth_header())
    pretty("JOBS — Get All Jobs", r.json())

def test_get_single_job():
    r = requests.get(f"{BASE}/jobs/{state['job_id']}", headers=auth_header())
    pretty("JOBS — Get Single Job", r.json())

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 — CANDIDATES
# ─────────────────────────────────────────────────────────────────────────────
def test_screen_candidate():
    r = requests.post(
        f"{BASE}/candidates/{state['job_id']}/screen",
        headers=auth_header(),
        json={
            "candidate_name" : "Charan B.",
            "candidate_email": "bonamukkalacharan@gmail.com",
            "resume_text"    : """
            Name: Charan B.
            Skills: Python, Flask, REST APIs, MongoDB, Git, Linux.
            Experience: 1.5 years building Flask APIs and MongoDB integrations.
            Education: B.Sc Computer Science, NIAT Hyderabad.
            Projects: IPL Win Predictor, CodeBuddy Chrome Extension.
            """
        }
    )
    data = r.json()
    pretty("CANDIDATES — Screen Candidate", data)
    if data.get("success"):
        state["candidate_id"] = data["candidate_id"]
        state["screen_data"]  = data["candidate"]
        state["questions"]    = data["candidate"].get("interview_questions", {})
        print(f"\n✅ Candidate ID saved: {state['candidate_id']}")

def test_get_candidates():
    r = requests.get(
        f"{BASE}/candidates/{state['job_id']}",
        headers=auth_header()
    )
    pretty("CANDIDATES — Get All Candidates", r.json())

def test_get_single_candidate():
    r = requests.get(
        f"{BASE}/candidates/detail/{state['candidate_id']}",
        headers=auth_header()
    )
    pretty("CANDIDATES — Get Single Candidate", r.json())

def test_update_status():
    r = requests.patch(
        f"{BASE}/candidates/detail/{state['candidate_id']}/status",
        headers=auth_header(),
        json={"status": "shortlisted"}
    )
    pretty("CANDIDATES — Update Status", r.json())

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 — PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
def test_pipeline_evaluate():
    r = requests.post(
        f"{BASE}/pipeline/evaluate/{state['candidate_id']}",
        headers=auth_header(),
        json={
            "answer_type": "speech",
            "answers"    : {
                "qa_pairs": [
                    {
                        "question": "How would you optimize a Flask application?",
                        "answer"  : "I would use Redis caching, connection pooling for MongoDB, async processing with Celery, and run gunicorn with multiple workers."
                    },
                    {
                        "question": "Explain MongoDB vs SQL",
                        "answer"  : "MongoDB stores JSON documents with flexible schema while SQL uses rigid tables and rows with fixed columns."
                    },
                    {
                        "question": "How do you handle errors in Python?",
                        "answer"  : "I use try except blocks, Python logging module, and Flask global error handlers to return clean JSON responses."
                    }
                ]
            }
        }
    )
    data = r.json()
    pretty("PIPELINE — Evaluate Answers", data)
    if data.get("success"):
        state["eval_data"] = data["data"]
        print(f"\n✅ Score: {data['data'].get('overall_score')}/100")

def test_pipeline_interview_start():
    r = requests.post(
        f"{BASE}/pipeline/interview/start/{state['candidate_id']}",
        headers=auth_header()
    )
    pretty("PIPELINE — Interview Start", r.json())

def test_pipeline_interview_next():
    r = requests.post(
        f"{BASE}/pipeline/interview/next",
        headers=auth_header(),
        json={
            "current_question": "How would you optimize Flask?",
            "candidate_answer": "I would use Redis caching and gunicorn workers.",
            "next_question"   : {"id": 2, "question": "Explain MongoDB vs SQL"}
        }
    )
    pretty("PIPELINE — Interview Next", r.json())

def test_pipeline_interview_close():
    r = requests.post(
        f"{BASE}/pipeline/interview/close/{state['candidate_id']}",
        headers=auth_header(),
        json={"total_questions": 8}
    )
    pretty("PIPELINE — Interview Close", r.json())

def test_pipeline_schedule():
    r = requests.post(
        f"{BASE}/pipeline/schedule/{state['candidate_id']}",
        headers=auth_header(),
        json={"role_level": "junior"}
    )
    pretty("PIPELINE — Schedule Next Step", r.json())

def test_pipeline_logs():
    r = requests.get(
        f"{BASE}/pipeline/logs/{state['candidate_id']}",
        headers=auth_header()
    )
    pretty("PIPELINE — Audit Logs", r.json())

# ─────────────────────────────────────────────────────────────────────────────
# RUN ALL TESTS
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🚀 RecruitMate AI — Full Backend Test\n")

    print("\n--- SECTION 1: HEALTH ---")
    test_health()

    print("\n--- SECTION 2: AUTH ---")
    test_login()
    test_me()

    print("\n--- SECTION 3: JOBS ---")
    test_create_job()
    test_get_jobs()
    test_get_single_job()

    print("\n--- SECTION 4: CANDIDATES ---")
    test_screen_candidate()
    test_get_candidates()
    test_get_single_candidate()
    test_update_status()

    print("\n--- SECTION 5: PIPELINE ---")
    test_pipeline_evaluate()
    test_pipeline_interview_start()
    test_pipeline_interview_next()
    test_pipeline_interview_close()
    test_pipeline_schedule()
    test_pipeline_logs()

    print("\n✅ Full backend test complete!")