# ExamApp — Secure Desktop Examination Platform

A comprehensive, secure, and modern examination platform featuring a FastAPI backend and a fully-featured PyQt6 desktop client. It supports separate workflows for **Students** and **Examiners**, complete with real-time exam management, proctoring/liveness checks, and detailed grading and reporting.

## 🏗️ Project Structure

```text
exam_app/
├── server/                      # FastAPI Backend
│   ├── main.py                  # API Entry point
│   ├── config.py                # Environment configuration
│   ├── database.py              # SQLAlchemy engine & session management
│   ├── dependencies.py          # Auth & Role dependencies (Examiner/Student)
│   ├── models/                  # SQLAlchemy DB models (Exam, User, Session, etc.)
│   ├── routers/                 # API Endpoints
│   │   ├── auth.py              # Registration, Login, Face Enrollment
│   │   ├── exams.py             # Exam creation, Questions, Enrollment
│   │   └── sessions.py          # Exam attempts, Grading, Liveness, History
│   └── requirements.txt
│
├── client/                      # PyQt6 Windows Desktop App
│   ├── main.py                  # Entry point
│   ├── main_window.py           # Main Router & Window Controller
│   ├── auth/                    # Login & Registration UIs
│   ├── dashboard/               # Examiner and Student Main Dashboards
│   ├── exam/                    # Exam Management (Examiner side)
│   ├── student_exam_screen/     # Active Exam UI & Liveness verification
│   ├── review/                  # Examiner grading & essay review UI
│   ├── reports/                 # Student results, score breakdown, history
│   ├── Shared/                  # Shared UI components (InfoDialog, Constants)
│   ├── styles/                  # Global CSS stylesheets
│   └── core/                    # Security, heartbeat, caching mechanisms
│
└── shared/                      # Code shared between Client and Server
    └── constants.py             # Enums: Role, ExamStatus, SessionStatus, QuestionType
```

---

## 🚀 Key Features

### 👨‍🏫 For Examiners
- **Exam Creation:** Create and schedule exams, set time limits, and configure liveness checks.
- **Question Management:** Add multiple-choice (MCQ) and essay-based questions.
- **Review & Grading:** Review submitted exam sessions, manually grade essays, and evaluate integrity scores.
- **Dashboard Overview:** Monitor active, upcoming, and draft exams easily.

### 🎓 For Students
- **Dashboard:** View upcoming assessments and quick statistics.
- **Secure Exam Environment:** Start exams through a verification portal including face/liveness checks.
- **Interactive Exam UI:** Seamlessly navigate between questions, track time, and submit answers.
- **Detailed Reports:** View comprehensive report cards with MCQ/Essay breakdowns and "Trust Scores".

---

## 🛠️ Setup & Installation

### Backend Server

```bash
cd server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure Environment
copy .env.example .env
# Edit .env with your DB credentials & JWT secret

# Run Migrations (if Alembic is configured)
alembic upgrade head

# Start the Server
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### Desktop Client

```bash
cd client
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Start the Desktop Application
python -m client.main
```

---

## 🔒 Security & Architecture Decisions

- **Face Verification:** Pre-exam liveness checks required before accessing LIVE exams.
- **Session Management:** `ExamSession` tracks detailed states (`VERIFYING`, `ACTIVE`, `SUBMITTED`, `TERMINATED`).
- **Seamless Reconnects:** If a student disconnects or backs out during `VERIFYING` or `ACTIVE` states, they can safely resume their session without losing progress.
- **Centralized UI Router:** `MainWindow` securely manages the user state and acts as a central router to dynamically load views (Dashboard, Exams, Reports, Settings) without opening multiple windows.
- **Modern UI/UX:** Built with PyQt6 using modern, borderless cards, smooth interactions, and rich typography for a premium native feel.

---

## 📋 Remaining TODOs Before Production

- [ ] Add JWT dependency injection to all protected routes (replace remaining stubs).
- [ ] Add HTTPS / TLS to server for secure communications.
- [ ] Implement deeper activity monitoring (cursor tracking, clipboard locking).
- [ ] Package client as a Windows installer (e.g., PyInstaller + NSIS or InnoSetup).
- [ ] Expand the `dashboard` to include live Proctoring alerts for the Examiner.
- [ ] Add rate limiting to auth endpoints (brute force protection).
