# RecruitMate AI

> A multi-tenant recruitment platform that screens resumes, generates personalized interview questions, runs proctored AI interviews with adaptive follow-up questions, and recommends shortlist/reject outcomes. It is configurable per company through a full Settings system and powered by Groq-backed agents.

**Live App:** https://recruit-mate-chi.vercel.app
**Backend Health:** https://recruitmate-backend-zkru.onrender.com/api/health
**Issues:** https://github.com/bonamukkala-bot/RecruitMate/issues

---

## Snapshot

| | |
|---|---|
| **Status** | Live, single-maintainer, actively developed |
| **Category** | Full-stack SaaS: AI-assisted recruitment |
| **Backend** | Python 3.11, Flask, MongoDB Atlas |
| **Frontend** | React (CRA), Tailwind CSS |
| **AI** | Groq (`openai/gpt-oss-20b` default, `openai/gpt-oss-120b` heavy) via a central LLM helper |
| **Deployment** | Render (API), Vercel (SPA) |
| **Tests** | pytest suite (backend) |

---

## The problem

Screening resumes, writing role-specific interview questions, running first-round interviews, scoring answers consistently, and notifying candidates at every stage is slow and inconsistent when done manually. Hiring rules also differ between companies, so a hardcoded pipeline does not fit everyone.

## The approach

Each step of early-stage hiring is a discrete, auditable agent call: parse the JD, score the resume, generate tailored questions, run the interview (fixed or adaptive), evaluate the answers, recommend the next step, and notify the candidate. Every agent call is logged per candidate. Companies tune the behavior of the whole pipeline from a **Settings** area instead of changing code.

---

## Key features

### Hiring pipeline
- **AI JD generation:** a one-line role description becomes a structured job posting.
- **Resume screening:** resumes (typed, PDF or DOCX) are scored 0-100 against the JD using company-configurable scoring weights.
- **Per-candidate question generation:** questions come from the candidate's matched and missing skills, with configurable count, difficulty and type.
- **Token-secured interview portal:** candidates use a unique link with no account. Interviews are proctored (face detection, full-screen and tab-switch rules) with configurable strictness and a consent step.
- **Adaptive follow-up interviews:** after each answer the agent evaluates it and decides to probe deeper, probe a gap, ask an easier related question, restate once, or move to the next core question. Core questions stay identical for every candidate.
- **Answer evaluation and recommendation:** a final evaluation over the full transcript produces scores and a hiring recommendation.
- **Role-aware scheduling:** next-step recommendations use configurable thresholds per seniority level (senior, mid, junior).
- **Human approval mode:** optionally, reject decisions go to a "Needs Review" queue instead of rejecting automatically.
- **AI candidate comparison**, **Kanban pipeline**, **analytics and interview heatmap**.

### Account security
- Bot-gated registration (Cloudflare Turnstile, verified server-side).
- Email OTP verification with resend, and opt-in TOTP two-factor authentication.

---

## Settings system

Open **Settings** to configure the platform per company. Every setting has defaults that reproduce the original behavior, so a company with no saved settings works exactly as before. Saving validates input server-side, and each section has a Reset to Defaults action.

| Tab | What you can configure |
|---|---|
| **Security** | Two-factor authentication (TOTP). |
| **Hiring Rules** | Score thresholds per role level (L2 and HR rounds), resume scoring weights (skills, experience, education, projects; must total 100), per-job weight override, and "reject requires human approval" mode with a Needs Review queue. |
| **Interview** | Duration, question count, difficulty (easy, medium, hard, adaptive), question types, proctoring rules (face detection, full-screen, tab-switch violations allowed, no-face grace period, terminate on violation), and follow-up mode (off or adaptive), max follow-ups per question and probe depth. |
| **Email** | Sender name, reply-to, editable templates (interview invite, shortlist, rejection, OTP footer) with whitelisted variables, live preview, test email, and notification preferences. |
| **AI** | Default and heavy model from an allow-list, candidate-facing language, tone, temperature, monthly token budget, and a usage dashboard (calls, tokens, estimated cost, latency, failure rate). |
| **Team & Roles** | Invite members by email, roles, enable/disable, resend invite, remove, and an activity (audit) log. |
| **Company** | Display name, website, logo (PNG/JPG, validated by content, max 1 MB), brand color, support email. Shown on the interview page and in emails. |
| **Privacy** | Data retention period, editable consent text with a required checkbox, proctoring event recording, candidate data export, and hard delete. |
| **Integrations** | Slack notifications, signed outgoing webhooks, API keys with scopes for the public v1 API, and optional Google Calendar/Meet. |

### Roles

| Capability | Owner | Admin | Recruiter | Viewer |
|---|:-:|:-:|:-:|:-:|
| View jobs, candidates, transcripts | Yes | Yes | Yes | Yes |
| Create/edit jobs, change candidate status, schedule | Yes | Yes | Yes | No |
| Change settings, manage team and integrations | Yes | Yes | No | No |
| Export candidate data | Yes | Yes | No | No |
| Delete candidate data, run retention purge | Yes | Yes (delete only) | No | No |

The backend enforces permissions on every protected endpoint. The frontend only hides or disables controls. The owner cannot be removed or demoted, and older tokens without a role are treated as owner.

---

## Adaptive follow-up interview

Enable it in **Settings > Interview > Follow-up mode**. With follow-up mode **off** (the default), the interview behaves exactly as the original fixed-question flow.

1. The server serves one turn at a time and enforces all limits: total questions, overall duration, max follow-ups per question, and one restate per question.
2. After each answer, one combined evaluator and decider call (5 second timeout) returns a verdict (`strong`, `partial`, `weak`, `off_topic`) and the next action. A timeout or invalid output falls back safely to the next core question.
3. Candidate answers are treated strictly as data (wrapped in delimited tags, with instructions inside them ignored), so "ignore previous instructions" has no effect.
4. Candidates never receive scores, verdicts or internal reasoning. Recruiters see a threaded transcript with per-turn verdicts, reasons and fallback badges.
5. The final evaluation uses the heavy model over the whole transcript, scores every candidate on the same core questions, and does not penalize harder follow-ups. Terminated interviews are evaluated on the transcript so far.
6. Code-type questions never receive follow-ups. Refreshing the page resumes from the stored transcript, and submitting the same turn twice does not create duplicates.

---

## How it works

```
Candidate resume (text/PDF/DOCX)
        |
        v
 JD Parser --> structured job requirements
        |
        v
 Resume Screener (company weights) --> match_score, matched/missing skills
        |
        +-- below threshold --> reject (or Needs Review if approval mode is on)
        |
        +-- above threshold
                |
                v
        Question Generator (count, difficulty, types)
                |
                v
        Public interview link (token, consent, proctoring)
                |
                v
        Interview: fixed questions OR adaptive follow-up loop
                |
                v
        Final evaluation (heavy model) --> overall_score
                |
                v
        Scheduler (company thresholds) --> recommended next step
                |
                v
        Email (company templates) + Slack / webhooks
```

Every agent call is logged to the `pipeline` collection. Every LLM call goes through a central helper that applies the company's model, language, tone and temperature, retries once on transient errors, enforces the token budget, and records usage.

---

## Architecture

```
HR User --> React SPA <-- Candidate (token link, no auth)
              |
              v  (JWT Bearer, role-checked)
          Flask API
              |
   +----------+-----------+-----------+----------+
   v          v           v           v          v
 auth      jobs      candidates   pipeline    settings
   |          |           |           |          |
   +----------+-----------+-----------+----------+
              v
       MongoDB Atlas

agents --> central LLM helper --> Groq
pipeline --> Brevo email, Slack, outgoing webhooks
auth --> Cloudflare Turnstile
public v1 API (API key) --> jobs, candidates
```

The frontend never calls Groq, MongoDB or Brevo directly. The Flask API owns authentication, the database connection and all agent calls.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React (CRA), Tailwind CSS, React Router v6, Axios, Recharts, Framer Motion |
| Bot protection | Cloudflare Turnstile (client widget and server verification) |
| Client-side vision | TensorFlow.js, face-api.js, coco-ssd (interview integrity checks) |
| Backend | Flask 3, PyJWT, bcrypt, pyotp, qrcode |
| Database | MongoDB Atlas (PyMongo) |
| AI | Groq via LangChain and a central LLM helper |
| Email | Brevo (sib-api-v3-sdk) |
| File parsing | PyPDF2, python-docx |
| Hosting | Render (API, Gunicorn), Vercel (SPA) |
| Monitoring | UptimeRobot polling `/api/health` |

---

## Project structure

```
RecruitMate/
├── backend/
│   ├── agents/        (jd_parser, resume_screener, question_generator,
│   │                   ai_interview, answer_evaluator, scheduler,
│   │                   candidate_comparator, email_sender)
│   ├── routes/        (auth, jobs, candidates, pipeline, settings, ...)
│   ├── utils/         (db, auth_helper, settings, llm, file_extractor)
│   ├── tests/         (pytest suite)
│   ├── config.py
│   └── app.py
├── scripts/           (seed_dev_user.py, retention purge)
└── frontend/
    └── src/
        ├── api/, context/, components/
        └── pages/     (auth, settings, jobs, candidates, pipeline,
                        analytics, interview)
```

---

## Quick start

### Prerequisites
- Python 3.11, Node.js 18+
- A MongoDB Atlas cluster
- Credentials: Groq, Brevo, Cloudflare Turnstile

### Backend

```bash
git clone https://github.com/bonamukkala-bot/RecruitMate.git
cd RecruitMate/backend

python -m venv venv311
venv311\Scripts\activate        # Windows
# source venv311/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env
python app.py                   # http://localhost:5000
```

### Frontend

```bash
cd ../frontend
npm install
cp .env.example .env
npm start                       # http://localhost:3000
```

### Local development against a separate database

Never develop against the production database. Set `MONGO_DB=recruitmate_dev` in `backend/.env`, then create a test account:

```bash
python scripts/seed_dev_user.py
```

The seed script refuses to run against the production database name. For local Turnstile, put Cloudflare's test site key in `frontend/.env.local` and the matching test secret in `backend/.env`. Never use test keys on production.

Flask does not reload `.env`, so stop and restart the backend after changing it.

---

## Environment variables

Names only. Never commit real values. See `backend/config.py` for the full list and defaults.

**backend/.env**

```
GROQ_API_KEY=
MONGO_URI=
MONGO_DB=
JWT_SECRET=
BREVO_API_KEY=
BREVO_SENDER_EMAIL=
BREVO_SENDER_NAME=
TURNSTILE_SECRET_KEY=
FRONTEND_URL=
GROQ_MODEL=
GROQ_MODEL_HEAVY=
GROQ_ALLOWED_MODELS=
GOOGLE_CALENDAR_ENABLED=
```

**frontend/.env**

```
REACT_APP_API_URL=
REACT_APP_TURNSTILE_SITE_KEY=
```

Notes:
- Set `MONGO_DB=recruitmate` on the production backend. It is the database name your live data uses.
- `REACT_APP_*` values are baked in at build time, so changing them on Vercel needs a redeploy.
- `.env` and `.env.local` must stay out of git.

---

## API reference

Base path: `/api`. Lock = requires `Authorization: Bearer <JWT>`. Link = unauthenticated and token-secured. Key = API key.

**Auth**

| Method | Route | Description |
|---|---|---|
| POST | /auth/register | Create company account (Turnstile-verified); re-sends OTP if the email is unverified |
| POST | /auth/verify-otp | Verify signup OTP |
| POST | /auth/resend-otp | Send a fresh OTP to an unverified account |
| POST | /auth/login | Log in (owner or team member); handles 2FA |
| GET | /auth/me (Lock) | Current user |
| POST/GET | /auth/2fa/* (Lock) | Set up, enable, check and disable TOTP |

**Jobs / Candidates / Pipeline** (Lock, role-checked)

Jobs: create, list, detail, status, delete, AI-generate JD, analytics. Candidates: list, screen, search, export, compare, detail, status, delete. Pipeline: send email, evaluate, schedule (returns a *recommended* decision), logs, create interview link, heatmap.

**Public interview (Link)**

| Method | Route | Description |
|---|---|---|
| GET | /pipeline/interview/public/\<token\> | Load the interview (fixed list, or the active turn in adaptive mode) |
| POST | /pipeline/interview/public/\<token\>/turn | Submit an answer and receive the next turn (adaptive mode) |
| POST | /pipeline/interview/public/\<token\>/submit | Finish the interview and submit the integrity log |

**Settings** (Lock, admin+ for writes)

| Method | Route | Description |
|---|---|---|
| GET | /settings | All sections merged with defaults |
| PUT | /settings/\<section\> | Validate and save a section |
| POST | /settings/\<section\>/reset | Restore defaults |
| POST | /settings/email/preview | Render an email template with sample data |
| GET | /settings/ai/usage | AI usage metrics |

**Privacy** (Lock)

| Method | Route | Description |
|---|---|---|
| GET | /privacy/candidates/\<id\>/export | JSON export of everything stored for a candidate |
| DELETE | /candidates/\<id\>/data | Hard delete a candidate and related records |

**Public v1 API (Key)**

List jobs and create candidates with `Authorization: Bearer <api key>`. Keys carry scopes (`read:candidates`, `write:jobs`), are rate limited, and can never reach settings, team or deletion endpoints.

---

## AI system details

- **Models:** configurable per company from an allow-list (defaults `openai/gpt-oss-20b` and `openai/gpt-oss-120b`). The default model handles fast tasks (JD parsing, questions, per-turn decisions) and the heavy model handles deep resume screening and final evaluation.
- **Central LLM helper:** applies company language, tone and temperature, handles reasoning-model quirks (minimum token limits, empty responses, JSON extraction), retries once, logs usage and enforces the monthly token budget.
- **Usage dashboard:** calls, tokens, estimated cost (clearly an estimate), per-agent and per-model breakdown, latency and failure rate.
- **Orchestration:** each agent is a standalone call with JSON-only output. Flask route handlers orchestrate the pipeline, not the LLM.
- **No RAG:** resume and JD text go directly into the prompt.
- **Contract:** every agent returns `{"success": bool, "data": {...}}`.
- **Safety:** candidate text is always treated as data, LLM output is schema-validated, and failures fall back to safe defaults.

---

## Security

- **Authentication:** custom JWT (PyJWT, 8-hour expiry), bcrypt password hashing, email OTP verification and opt-in TOTP 2FA.
- **Authorization:** role-based access control (owner, admin, recruiter, viewer) enforced server-side, and disabled members are blocked on their next request.
- **Invites:** single-use tokens stored only as hashes, expiring after 72 hours.
- **API keys:** shown once, stored only as hashes, scoped and revocable.
- **Outgoing webhooks:** HMAC-SHA256 signatures, HTTPS only, SSRF protection (private, loopback and link-local addresses blocked, redirects not followed).
- **Slack webhook URLs** are never returned by the API.
- **Uploads:** logos are validated by file content, size-limited, and PNG/JPG only.
- **Privacy:** consent is recorded before interviews, configurable retention, candidate export and hard delete, and an audit log of administrative actions.
- **Environment isolation:** development uses a separate database, and standalone scripts refuse to run against the production database.
- **Bot protection:** Cloudflare Turnstile verified server-side before any registration write.

---

## Testing

```bash
cd backend
pytest
```

Tests cover settings validation and defaults, role permissions, the scheduler and approval flow, email rendering and escaping, LLM helper behavior with a mocked client, the adaptive interview loop (limits, fallbacks, prompt injection, no leakage of internal fields), SSRF blocking, webhook signing, and API key scoping.

Frontend build check:

```bash
cd frontend && npm run build
```

---

## What changed in this release

- Added the full **Settings system** (Security, Hiring Rules, Interview, Email, AI, Team & Roles, Company, Privacy, Integrations).
- Scheduler thresholds, screening weights, interview limits, proctoring rules and email content are now configurable instead of hardcoded.
- Added **human approval mode** and clearer wording: scheduling now returns a *recommended* decision, and scheduling a candidate with no evaluation returns a clear error instead of crashing.
- Moved to **gpt-oss models** with a central LLM helper, usage logging, cost estimates and a monthly token budget.
- Added **team roles, invites and an audit log**.
- Added **company branding**, consent, data export, hard delete and retention purge.
- Added **Slack, signed webhooks and API keys** with a public v1 API.
- Added the **adaptive follow-up interview** with a threaded recruiter transcript and fairness-normalized final evaluation.
- Fixed unverified-account lockout with **resend OTP** and a safer register flow, and added better Brevo and Turnstile error logging.
- Added a **pytest suite** and separated dev and production databases.

---

## Limitations

- No rate limiting yet on login, register, OTP and public interview routes (API keys are rate limited).
- MongoDB TLS certificate validation is relaxed in `utils/db.py`; tightening it is a planned follow-up.
- Single LLM provider (Groq) with no fallback provider.
- The daily digest email setting is stored but the digest job is not implemented.
- Google Calendar/Meet is optional and off by default; it needs Google Cloud setup.
- No React error boundaries and no CI pipeline yet.
- No 2FA recovery codes.
- Offer letter generation is not yet built.

---

## Roadmap

- [ ] Rate limiting (Flask-Limiter) on authentication and public interview routes
- [ ] CI pipeline running pytest and the frontend build
- [ ] Voice interviews with speech-to-text and text-to-speech
- [ ] Bias-blind resume screening mode
- [ ] Talent pool re-matching with vector search
- [ ] One-click AI-generated offer letter
- [ ] React error boundaries
- [ ] Tighten MongoDB TLS configuration
- [ ] 2FA recovery codes
- [x] Settings system with roles, privacy and integrations
- [x] Adaptive follow-up interviews
- [x] Interview performance heatmap
- [x] Cloudflare Turnstile on registration
- [x] Opt-in TOTP two-factor authentication

---

## Author

**Bonamukkala Charan Reddy**
Second-year B.Sc Computer Science (Generative AI), NIAT Hyderabad (BITS Pilani-affiliated)

- GitHub: bonamukkala-bot
- Portfolio: charan-me.vercel.app
- LinkedIn: bonamukkala-charan
