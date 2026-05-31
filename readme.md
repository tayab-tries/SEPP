# ExamApp — Secure Desktop Examination Platform

A fully-featured, secure examination platform built for academic use. It pairs a **FastAPI** REST + WebSocket backend with a **PySide6** (Qt6) desktop client. The system supports two distinct roles — **Examiners** and **Students** — with end-to-end workflows covering exam creation, proctored delivery, manual grading, and scored reporting.

---

## 🏗️ Project Structure

```text
EXAM/
├── server/                          # FastAPI Backend
│   ├── main.py                      # App entry point, CORS, DB migration shims
│   ├── config.py                    # Environment configuration (JWT, DB URL)
│   ├── database.py                  # SQLAlchemy engine & session
│   ├── dependencies.py              # JWT auth, role guards (require_examiner / require_student)
│   ├── models/
│   │   └── models.py                # ORM: User, Class, Enrollment, Exam, Question,
│   │                                #       ExamSession, Answer, ProctoringEvent, ExamAccessRequest
│   ├── routers/
│   │   ├── auth.py                  # Register, login, face enrollment, /auth/me
│   │   ├── exams.py                 # Classes, enrollment, exam CRUD, questions, status transitions
│   │   └── sessions.py              # Session lifecycle, answer submission, grading PATCH,
│   │                                #   proctoring events, liveness, integrity scoring
│   ├── services/                    # Integrity scoring, liveness helpers
│   ├── websocket/                   # WebSocket manager (real-time examiner ↔ student events)
│   └── requirements.txt
│
├── client/                          # PySide6 Desktop Application
│   ├── main.py                      # Entry point
│   ├── main_window.py               # Central QMainWindow router — manages all pages & auth state
│   ├── config.py                    # BASE_URL, environment config
│   │
│   ├── auth/                        # Login & Signup UI + controllers
│   ├── Shared/                      # Shared UI primitives (InfoDialog, constants)
│   ├── styles/                      # Global stylesheet
│   ├── layouts/                     # Reusable layout helpers
│   │
│   ├── core/                        # Background infrastructure
│   │   ├── api_worker.py            # QThread-based HTTP worker
│   │   └── heartbeat.py             # Session keepalive & reconnect logic
│   │
│   ├── dashboard/                   # Student home dashboard (upcoming exams, quick stats)
│   ├── exam/                        # Student exam listing & access-request flow
│   ├── student_exam_screen/         # Full-screen proctored exam UI
│   │   ├── exam_window.py           # ExamWindow (liveness, MCQ/Essay engine, submission)
│   │   └── ...
│   │
│   ├── review/                      # Student post-exam review (read-only with examiner comments)
│   │   ├── services/api_client.py   # Fetches session + answers + examiner comments
│   │   └── views/                   # ReviewScreenWidget, sidebar showing examiner remarks
│   │
│   ├── reports/                     # Student exam history & report cards
│   │   ├── views/all_results_list.py
│   │   └── views/report_card_dialog.py
│   │
│   └── modules/                     # Examiner-side feature modules
│       ├── auth/                    # Examiner login
│       ├── common/                  # Shared spinner, loading states
│       ├── exam_engine/             # MCQ & Essay widgets (shared between exam & grading views)
│       ├── proctoring/              # Proctoring event display
│       └── examiner_dashboard/      # Full examiner dashboard orchestrator
│           ├── examiner_dashboard_orchestrator.py   # Central controller + all API workers
│           └── views/
│               ├── dashboard_shell.py               # Shell/nav layout
│               ├── class_view_examiner.py           # Class & enrollment management
│               ├── exam_creation_view.py            # Exam + question builder UI
│               ├── examiner_exam_monitor_view.py    # Live session monitor
│               ├── exam_access_requests_view.py     # Approve/reject access requests
│               └── assessments/ (via modules/assessments/)
│                   ├── assessments_panel.py         # Exam selector for grading
│                   ├── assessment_details_view.py   # Student attempt list
│                   ├── assessment_attempt_card.py   # Per-student attempt card (PENDING / GRADED tag)
│                   ├── student_logs_view.py         # Proctoring event log viewer
│                   └── examinergradingview/         # Full grading interface
│                       ├── grading_cache.py         # Local JSON draft cache (.grading_cache.json)
│                       └── views/
│                           ├── review_screen_widget.py  # Main grading layout
│                           ├── question_widgets.py      # MCQ & Essay grading widgets (cache-aware)
│                           └── sidebar.py               # Examiner comment sidebar
│
├── shared/
│   └── constants.py                 # Enums: Role, ExamStatus, SessionStatus, QuestionType
│
├── ai_microservice/                 # Placeholder AI microservice (stub)
│   └── main.py
│
├── native/                          # Native platform helpers (window management, etc.)
├── assets/                          # App icons and images
├── diagrams/                        # Architecture & flow diagrams
└── tests/                           # Test suite
```

---

## 🚀 Key Features

### 👨‍🏫 Examiner Workflow
| Feature | Details |
|---|---|
| **Class & Enrollment Management** | Create classes, generate join codes, approve enrollment requests |
| **Exam Builder** | Create draft exams with MCQ and essay questions; configure duration, scheduling, integrity rules |
| **Exam Lifecycle** | Transition exams through `DRAFT → SCHEDULED → LIVE → CLOSED` |
| **Live Monitoring** | Real-time view of active student sessions via WebSocket; force-terminate sessions |
| **Grading Dashboard** | Browse submitted sessions per exam; manually grade essays with per-question scores and comments |
| **Offline Draft Grading** | Grades saved locally in `.grading_cache.json`; "PENDING" tag shown until synced to server |
| **Integrity Scoring** | Automatic integrity score computed from proctoring events (gaze, window switches, face absence) |
| **Proctoring Log Viewer** | Per-session event timeline for audit |

### 🎓 Student Workflow
| Feature | Details |
|---|---|
| **Dashboard** | Upcoming exams, quick statistics |
| **Exam Access** | Join by class code or direct exam access request |
| **Liveness Check** | Face enrollment required; optional liveness re-check at exam start |
| **Secure Exam Environment** | Borderless fullscreen; window-switch and gaze tracking; paste restrictions for essays |
| **Seamless Reconnect** | Disconnect recovery for `VERIFYING` / `ACTIVE` sessions |
| **Post-Exam Review** | Read-only answer review with examiner comments shown per question |
| **Report Cards** | Score breakdown (MCQ + essay), trust score, exam history |

---

## ⚙️ Setup & Running

### Prerequisites
- Python 3.11+
- A virtual environment (`.venv`) in the repo root or `client/`

### 1. Start the Backend Server

```bash
# From the repo root
python -m venv .venv
.venv\Scripts\activate

pip install -r server/requirements.txt

# Configure environment
# Edit .env at root: DATABASE_URL, SECRET_KEY

uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

The server auto-creates the SQLite DB (`exam_dev.db`) and runs lightweight migration shims on startup.

### 2. Start the Desktop Client

```bash
# From the repo root (with .venv active)
pip install -r client/requirements.txt

python -m client.main
```

> **Note:** The client reads `API_BASE_URL` from the environment (defaults to `http://127.0.0.1:8000`).

---

## 🔒 Security & Architecture Notes

- **JWT Auth** — All protected routes require a Bearer token. `require_examiner` / `require_student` dependency guards enforce role-based access.
- **Face Enrollment** — Required for students before joining any exam session. Stored as an embedding, validated at session start.
- **Integrity Scoring** — Composite score derived from gaze-away events, window switches, and face-absent seconds tracked during the exam.
- **Grading Cache** — Examiner draft grades live in `.grading_cache.json` locally and are only cleared after a successful `PATCH /sessions/{id}/answers/{qid}/review` sync. The UI shows **PENDING** (amber) until synced, then **GRADED** (green).
- **WebSocket Manager** — Bidirectional real-time channel between examiner monitors and student sessions for live status updates and force-terminate signals.
- **Central Router** — `MainWindow` owns all page instances and manages auth state, preventing duplicate windows and ensuring clean teardown.

---

## 📡 API Surface (Summary)

| Method | Route | Description |
|---|---|---|
| `POST` | `/auth/register` | Create student or examiner account |
| `POST` | `/auth/login` | Obtain JWT token |
| `POST` | `/auth/face-enroll` | Upload face embedding |
| `GET` | `/auth/me` | Validate token, get profile |
| `POST` | `/classes` | Examiner creates a class |
| `POST` | `/classes/join-by-code/{code}` | Student joins class |
| `POST` | `/exams` | Examiner creates exam |
| `PATCH` | `/exams/{exam_id}/status` | Transition exam status |
| `POST` | `/exams/{exam_id}/questions` | Add question |
| `GET` | `/exams/{exam_id}/sessions` | Examiner fetches all student sessions |
| `POST` | `/sessions/start` | Student starts exam session |
| `POST` | `/sessions/{id}/answers` | Student submits an answer |
| `POST` | `/sessions/{id}/submit` | Student submits exam |
| `PATCH` | `/sessions/{id}/answers/{qid}/review` | Examiner grades one answer |
| `POST` | `/sessions/{id}/terminate` | Examiner force-terminates session |
| `GET` | `/sessions/{id}/history` | Student fetches past sessions |
| `WS` | `/ws/{session_id}` | Real-time proctoring channel |

---

## 🗂️ Notable Files

| File | Purpose |
|---|---|
| `client/main_window.py` | Central page router, auth lifecycle, review/exam launch |
| `client/modules/examiner_dashboard/examiner_dashboard_orchestrator.py` | All examiner API workers, page state machine |
| `client/modules/assessments/examinergradingview/grading_cache.py` | Local offline draft cache |
| `client/modules/assessments/assessment_attempt_card.py` | Attempt card with PENDING / GRADED / SUBMITTED status tags |
| `server/routers/sessions.py` | Session lifecycle, grading, integrity, liveness |
| `server/routers/exams.py` | Exam & class management, enrollment |
| `shared/constants.py` | Single source of truth for all enums |
| `client_backend_contract.md` | Informal API contract between client and server teams |
