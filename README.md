<div align="center">

# 🤖 RecruitMate AI

**A full-stack, multi-tenant AI recruitment platform that screens, interviews, evaluates, and shortlists candidates — end to end, with almost zero manual HR effort.**

[![Live Frontend](https://img.shields.io/badge/Frontend-Live-brightgreen)](https://recruit-mate-chi.vercel.app)
[![Backend Status](https://img.shields.io/badge/Backend-Render-blue)](https://recruitmate-backend-zkru.onrender.com/api/health)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](#license)

[Live Demo](https://recruit-mate-chi.vercel.app) · [Report Bug](https://github.com/bonamukkala-bot/RecruitMate/issues) · [Request Feature](https://github.com/bonamukkala-bot/RecruitMate/issues)

</div>

---

## 📖 Overview

**RecruitMate AI** replaces the manual, repetitive parts of hiring — reading resumes, drafting interview questions, running interviews, scoring answers, sending emails, comparing shortlists — with a pipeline of **7 cooperating AI agents** built on Groq's `llama-3.3-70b-versatile`.

An HR user posts a job (or generates one from a single line), uploads resumes, and the platform takes it from there: it screens candidates against the job description, auto-rejects weak matches, generates a personalized interview question set per candidate, runs a **voice-based AI interview** through a secure public link, evaluates the answers, decides whether to shortlist or reject, and keeps everything visible on a live Kanban pipeline and analytics dashboard.

Built solo by [Charan Reddy](https://github.com/bonamukkala-bot) — a first-year B.Sc CS (NIAT Hyderabad, BITS Pilani-affiliated) student — as a production-deployed, real-world SaaS project.

---

## ✨ Features

### Core hiring pipeline
- **AI JD Generator** — HR types one line ("Senior React Developer, Hyderabad"), the AI writes a complete, structured job description
- **Job Posting** — post via plain text or upload a JD as PDF / Word
- **Resume Screening (Agent 1: JD Parser + Agent 2: Resume Screener)** — parses the JD into structured requirements, then scores every uploaded resume against it; candidates scoring below the auto-reject threshold are automatically sent a rejection email
- **Personalized Question Generation (Agent 3)** — generates a tailored question set per candidate based on their matched/missing skills, not generic questions
- **Voice AI Interview Portal (Agent 4: AI Interviewer)** — candidate receives a unique, token-secured interview link (no login required); the AI asks questions by voice, the candidate answers by voice, and the interview auto-progresses
- **Answer Evaluation (Agent 5)** — scores every answer and an overall score out of 100, with a strict, explainable rubric
- **Auto-Decisioning** — score ≥ threshold → auto-shortlisted; below threshold → auto-rejection email, no human intervention needed
- **Scheduler (Agent 6)** — decides and communicates next steps (next round / HR call / offline interview) based on score and role seniority
- **Offline Interview Scheduling** — HR manually sets date, time, and location; candidate gets a confirmation email
- **Candidate Comparator (Agent 7)** — select 2–3 shortlisted candidates and get an AI-backed recommendation with evidence-based reasoning (matched/missing skills, scores) — not generic praise
- **Email Sender Agent** — drafts and sends interview links, shortlist notices, rejection emails, and scheduling confirmations via Brevo

### Pipeline & insights
- **Kanban Pipeline Board** — 5 stages: Screened → Shortlisted → Invited → Hired / Rejected
- **Analytics Dashboard** — hiring funnel, score distributions, skills-in-demand, per-job stats
- **Interview Performance Heatmap** — surfaces the weakest interview questions across candidates, a radar chart, per-question breakdowns, and skill-gap patterns
- **Smart Candidate Search** — filter by skill, status, score range, and date
- **CSV Export** — export the current filtered candidate view

### Auth & security
- **Custom JWT auth** (PyJWT + bcrypt) with email OTP verification on signup — no third-party auth library
- **Cloudflare Turnstile CAPTCHA on Registration** — the sign-up page is protected against bot/scripted signups:
  - The frontend renders a Turnstile widget (Managed mode) and blocks submission until a token is issued
  - The backend independently verifies that token server-side against Cloudflare's `siteverify` endpoint as the *first* check in `/api/auth/register`, before any database write or OTP email — so the check can't be bypassed by calling the API directly
  - Scoped deliberately to Registration only; Login and all other routes are untouched
- **Public interview routes are token-secured, not auth-walled** — candidates never need an account; the unique interview token *is* the access control

---

## 🏗️ Architecture

```
┌─────────────────┐        REST / JSON         ┌──────────────────────┐
│   React (CRA)    │ ─────────────────────────▶ │   Flask API (Blueprints)│
│  Tailwind CSS     │ ◀───────────────────────── │  auth / jobs /          │
│  React Router v6  │        JWT (Bearer)        │  candidates / pipeline  │
│  Recharts, Framer  │                            └──────────┬───────────┘
└─────────────────┘                                          │
                                                               │
                     ┌─────────────────────────────────────────┼───────────────────────┐
                     ▼                                         ▼                        ▼
          ┌────────────────────┐               ┌────────────────────────┐   ┌──────────────────┐
          │  MongoDB Atlas      │               │  7 AI Agents (LangChain)│   │  Brevo (Email)     │
          │  companies / jobs /  │               │  → Groq llama-3.3-70b    │   │  Cloudflare Turnstile│
          │  candidates / pipeline│               │    versatile              │   └──────────────────┘
          └────────────────────┘               └────────────────────────┘
```

**The 7 agents**, each an isolated LangChain + Groq module with a strict JSON-only contract:

| # | Agent | File | Responsibility |
|---|-------|------|-----------------|
| 1 | JD Parser | `agents/jd_parser.py` | Extracts structured requirements (skills, experience, responsibilities) from a raw JD |
| 2 | Resume Screener | `agents/resume_screener.py` | Scores a resume against the parsed JD (0–100), returns matched/missing skills |
| 3 | Question Generator | `agents/question_generator.py` | Generates 8 personalized questions (technical / behavioral / gap-focused) per candidate |
| 4 | AI Interviewer | `agents/ai_interview.py` | Drives the live voice interview — intro, follow-ups, closing |
| 5 | Answer Evaluator | `agents/answer_evaluator.py` | Scores each answer and computes an overall interview score |
| 6 | Scheduler | `agents/scheduler.py` | Decides next step by score + role seniority; drafts scheduling emails |
| 7 | Candidate Comparator | `agents/candidate_comparator.py` | Recommends the best of 2–3 shortlisted candidates, with reasoning |
| — | Email Sender | `agents/email_sender.py` | Drafts and sends all transactional emails (interview link, shortlist, rejection, scheduling) via Brevo |

---

## 🛠️ Tech Stack

**Backend**
- Python 3.11, Flask 3, Flask-CORS
- PyMongo → MongoDB Atlas (custom TLS handling for cross-platform SSL issues)
- LangChain + `langchain-groq` → Groq `llama-3.3-70b-versatile`
- PyJWT + bcrypt (custom auth, no third-party JWT framework)
- Brevo (`sib-api-v3-sdk`) for transactional email
- PyPDF2 / python-docx for resume & JD file parsing
- Gunicorn (production WSGI server)

**Frontend**
- React 18 (Create React App), Tailwind CSS 3
- React Router v6, Axios
- Framer Motion (animation), Recharts (analytics charts)
- React Hot Toast, Lucide React (icons)
- `react-turnstile` (Cloudflare Turnstile CAPTCHA)
- TensorFlow.js + face-api.js / coco-ssd (client-side interview integrity checks)

**Infra & Ops**
- **Backend hosting:** Render
- **Frontend hosting:** Vercel
- **Database:** MongoDB Atlas
- **Uptime monitoring:** UptimeRobot (pings `/api/health` every 5 minutes)
- **Bot protection:** Cloudflare Turnstile

---

## 📂 Project Structure

```
RecruitMate/
├── backend/
│   ├── agents/                  # The 7 AI agents + email sender
│   │   ├── jd_parser.py
│   │   ├── resume_screener.py
│   │   ├── question_generator.py
│   │   ├── ai_interview.py
│   │   ├── answer_evaluator.py
│   │   ├── scheduler.py
│   │   ├── candidate_comparator.py
│   │   └── email_sender.py
│   ├── routes/                  # Flask blueprints
│   │   ├── auth.py              # register / verify-otp / login / me
│   │   ├── jobs.py               # CRUD + AI JD generation + analytics
│   │   ├── candidates.py         # screening, search, export, compare
│   │   └── pipeline.py           # emails, interviews, scheduling, heatmap
│   ├── utils/
│   │   ├── db.py                 # MongoDB client + indexes
│   │   ├── auth_helper.py        # JWT decorator + current-company resolver
│   │   └── file_extractor.py     # PDF/DOCX text extraction
│   ├── config.py
│   ├── app.py                    # App factory + blueprint registration
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── api/                  # Axios wrappers per resource
    │   ├── context/AuthContext.jsx
    │   ├── components/
    │   │   ├── ui/                # Button, Input, Badge, Modal, LoadingSpinner
    │   │   └── layout/            # Sidebar, TopBar, DashboardLayout
    │   ├── pages/
    │   │   ├── auth/              # Login, Register (+ Turnstile), VerifyOTP
    │   │   ├── dashboard/
    │   │   ├── jobs/
    │   │   ├── candidates/        # list, detail, comparison
    │   │   ├── pipeline/          # Kanban board
    │   │   ├── analytics/         # Analytics + Heatmap
    │   │   └── interview/         # Public voice InterviewPortal
    │   └── App.js
    └── package.json
```

---

## 🔌 API Overview

All endpoints are prefixed under `/api`. Authenticated routes require `Authorization: Bearer <JWT>`.

**Auth** (`/api/auth`)
| Method | Route | Description |
|---|---|---|
| POST | `/register` | Create company account (Turnstile-verified) |
| POST | `/verify-otp` | Verify signup OTP |
| POST | `/login` | Log in, receive JWT |
| GET | `/me` | Current authenticated company |

**Jobs** (`/api/jobs`)
| Method | Route | Description |
|---|---|---|
| POST | `/` | Create a job posting |
| GET | `/` | List all jobs |
| GET | `/<job_id>` | Job detail |
| PATCH | `/<job_id>/status` | Update job status |
| DELETE | `/<job_id>` | Delete a job |
| POST | `/generate-jd` | AI-generate a full JD from one line |
| GET | `/analytics` | Hiring funnel + per-job stats |

**Candidates** (`/api/candidates`)
| Method | Route | Description |
|---|---|---|
| GET | `/` | List candidates |
| POST | `/<job_id>/screen` | Screen resume(s) against a job |
| GET | `/search` | Filtered search (skill, status, score, date) |
| GET | `/export` | CSV export |
| POST | `/compare` | AI comparison of 2–3 candidates |
| GET | `/<job_id>` | Candidates for a job |
| GET | `/detail/<candidate_id>` | Candidate detail |
| PATCH | `/detail/<candidate_id>/status` | Update pipeline status |
| DELETE | `/detail/<candidate_id>` | Delete candidate |

**Pipeline** (`/api/pipeline`)
| Method | Route | Description |
|---|---|---|
| POST | `/send-email/<candidate_id>` | Send shortlist/interview-link email |
| POST | `/evaluate/<candidate_id>` | Evaluate submitted interview answers |
| POST | `/interview/start/<candidate_id>` | Start an AI interview session |
| POST | `/interview/next` | Advance to next interview question |
| POST | `/interview/close/<candidate_id>` | Close out an interview |
| POST | `/schedule/<candidate_id>` | AI-driven next-step scheduling |
| GET | `/logs/<candidate_id>` | Agent run history for a candidate |
| POST | `/interview/create/<candidate_id>` | Generate a public interview token/link |
| GET | `/interview/public/<token>` | *(no auth)* Load interview by token |
| POST | `/interview/public/<token>/submit` | *(no auth)* Submit interview answers |
| POST | `/schedule-offline/<candidate_id>` | Manually schedule an offline round |
| GET | `/heatmap/jobs` | Jobs with heatmap data available |
| GET | `/heatmap` | Interview performance heatmap data |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11
- Node.js 18+
- A MongoDB Atlas cluster
- API keys: [Groq](https://console.groq.com), [Brevo](https://www.brevo.com), [Cloudflare Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile)

### Backend setup
```bash
cd backend
python -m venv venv311
venv311\Scripts\activate        # Windows
# source venv311/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env            # then fill in real values
python app.py                   # runs on http://localhost:5000
```

### Frontend setup
```bash
cd frontend
npm install
cp .env.example .env            # then fill in real values
npm start                       # runs on http://localhost:3000
```

### Environment variables

**`backend/.env`**
```env
GROQ_API_KEY=
MONGO_URI=
JWT_SECRET=
BREVO_API_KEY=
BREVO_SENDER_EMAIL=
BREVO_SENDER_NAME=
TURNSTILE_SECRET_KEY=
FRONTEND_URL=http://localhost:3000
```

**`frontend/.env`**
```env
REACT_APP_API_URL=http://localhost:5000/api
REACT_APP_TURNSTILE_SITE_KEY=
```

> Turnstile site/secret keys are generated per-domain from the Cloudflare dashboard — register both `localhost` and your production frontend hostname on the same widget for local + prod to both work.

---

## 🌐 Live Deployment

| Service | Provider | URL |
|---|---|---|
| Frontend | Vercel | https://recruit-mate-chi.vercel.app |
| Backend | Render | https://recruitmate-backend-zkru.onrender.com |
| Health check | — | `/api/health` |
| Uptime monitor | UptimeRobot | pings `/api/health` every 5 min |

> `REACT_APP_*` variables are baked in at build time on Vercel — updating them requires a manual redeploy, not just an env var change.

---

## 🗺️ Roadmap

- [ ] **One-click Offer Letter Generator** — AI-drafted offer letter for shortlisted candidates, downloadable as PDF, optional email send
- [x] **Interview Performance Heatmap** — weakest questions, radar chart, skill-gap breakdown
- [x] **Cloudflare Turnstile on Registration** — bot-protected signup
- [ ] React error boundaries
- [ ] Rate limiting on public (unauthenticated) interview routes
- [ ] Remove dead code paths in `ai_interview.py`
- [ ] README screenshots / demo GIF

---

## 👤 Author

**Bonamukkala Charan Reddy**
First-year B.Sc Computer Science, NIAT Hyderabad (BITS Pilani-affiliated) · Freelance web & AI developer

- GitHub: [@bonamukkala-bot](https://github.com/bonamukkala-bot)
- Portfolio: [charan-me.vercel.app](https://charan-me.vercel.app)
- LinkedIn: [bonamukkala-charan](https://linkedin.com/in/bonamukkala-charan)
- Instagram: [@charan.insights](https://instagram.com/charan.insights) · [@trending.tech.ai](https://instagram.com/trending.tech.ai)
- YouTube: [charanreddysinsights](https://youtube.com/@charanreddysinsights)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.

---

<div align="center">
Built with Flask, React, LangChain, and Groq LLaMA 3.3 — end-to-end, solo, and in production.
</div>
