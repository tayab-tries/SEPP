# ExamApp — Secure Desktop Examination Platform

## Project Structure

```
exam_app/
├── server/                      # FastAPI backend
│   ├── main.py                  # Entry point, WebSocket endpoints
│   ├── config.py                # Settings (reads from .env)
│   ├── database.py              # SQLAlchemy engine + session
│   ├── models/models.py         # All DB models
│   ├── routers/
│   │   ├── auth.py              # M1: Registration, login, face enrollment
│   │   └── exams.py             # M2: Classes, enrollments, exams, questions
│   ├── websocket/manager.py     # Real-time WS: heartbeat, events, answers
│   └── requirements.txt
│
├── client/                      # PyQt6 Windows desktop app
│   ├── config.py                # Server URL, local paths
│   ├── core/
│   │   ├── local_cache.py       # M8: Encrypted SQLite (SQLCipher)
│   │   ├── heartbeat.py         # M8: WS connection, lockdown state machine
│   │   └── input_hooks.py       # M7: Python wrapper for C++ DLL
│   ├── modules/
│   │   ├── auth/                # M1: Login + registration windows
│   │   ├── exam_engine/
│   │   │   ├── exam_window.py   # M3: Main exam UI + lockdown overlay
│   │   │   └── mcq_widget.py    # M3: MCQ + Essay widgets
│   │   ├── proctoring/
│   │   │   ├── camera_monitor.py  # M4b: OpenCV + MediaPipe + DeepFace
│   │   │   ├── activity_monitor.py # M4a: Window/cursor/process/clipboard
│   │   │   └── event_logger.py    # M4c: Event batching + cadence analysis
│   │   ├── dashboard/           # M5: Examiner live dashboard
│   │   └── results/             # M6: Results + essay review
│   └── requirements.txt
│
├── native/                      # C++ DLLs
│   └── hooks/
│       ├── input_hooks.cpp      # M7: Low-level keyboard hooks DLL
│       └── CMakeLists.txt
│
└── shared/
    └── constants.py             # Shared enums + config (used by both sides)
```

---

## Module Map

| Module | What it does | Key files |
|--------|-------------|-----------|
| M1 — Auth | Registration, login, JWT, face enrollment | `server/routers/auth.py` |
| M2 — Exam Management | Classes, enrollments, exam CRUD, questions | `server/routers/exams.py` |
| M3 — Exam Engine | Exam UI, MCQ, Essay, lockdown overlay | `client/modules/exam_engine/` |
| M4a — Activity Monitor | Window, cursor, process, clipboard | `client/modules/proctoring/activity_monitor.py` |
| M4b — Camera Monitor | Face detection, head pose, re-verification | `client/modules/proctoring/camera_monitor.py` |
| M4c — Event Logger | Aggregation, keystroke cadence, batching | `client/modules/proctoring/event_logger.py` |
| M5 — Dashboard | Live examiner view, alerts, controls | `client/modules/dashboard/` |
| M6 — Results | Grading, essay review, integrity score | `client/modules/results/` |
| M7 — Security | Keyboard hooks DLL, VM detection | `native/hooks/`, `client/core/input_hooks.py` |
| M8 — Sync/Offline | Heartbeat, 120s lockdown, local cache | `client/core/heartbeat.py`, `client/core/local_cache.py` |

---

## Setup

### Server

```bash
cd server
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit environment variables
copy .env.example .env

# Run database migrations
alembic upgrade head

# Start server
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

### Client

```bash
cd client
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# Copy and edit environment variables  
copy .env.example .env

python main.py
```

### C++ DLL (input_hooks)

Requires: CMake 3.20+, MSVC or MinGW

```bash
cd native/hooks
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
# -> DLL is copied to client/native/input_hooks.dll
```

---

## Build Order (Recommended)

1. **M1 Auth** — get login/register working end to end
2. **M2 Exam Management** — examiners create exams, students enroll
3. **M3 Exam Engine** — working exam flow (no proctoring yet)
4. **M8 Heartbeat** — wire up WebSocket, test lockdown
5. **M4a Activity Monitor** — window + cursor + process tracking
6. **M4b Camera Monitor** — add AI layer
7. **M7 Security DLL** — compile and integrate keyboard hooks
8. **M5 Dashboard** — examiner live view
9. **M6 Results** — grading + integrity score
10. **Hardening** — review all TODOs, tighten auth, add JWT to all routes

---

## Key Design Decisions

- **Face embeddings, not photos** — 128-dim vectors stored server-side, no raw images
- **SQLCipher local cache** — answers and events are encrypted at rest on student machine
- **Chain-hashed event log** — each event is linked to the previous via SHA256, tamper-evident
- **Clock reconciliation** — server checks client-reported time against server clock on reconnect
- **C++ keyboard hooks** — harder to bypass than Python-level key filtering; runs as a native DLL
- **120s lockdown** — network drop freezes exam but doesn't immediately terminate; recoverable

---

## TODOs Before Production

- [ ] Add JWT dependency injection to all protected routes (replace `TODO_FROM_JWT` stubs)
- [ ] Add proper OAuth2 bearer token scheme to FastAPI
- [ ] Implement `client/modules/auth/` login + registration windows
- [ ] Implement `client/modules/dashboard/` examiner live view
- [ ] Implement `client/modules/results/` essay review UI
- [ ] Implement liveness check (blink / head turn) at exam entry
- [ ] Set up Alembic migrations
- [ ] Add HTTPS / TLS to server (Let's Encrypt or self-signed for LAN)
- [ ] Add rate limiting to auth endpoints (brute force protection)
- [ ] Write integration tests for lockdown + reconnect flow
- [ ] Package client as a Windows installer (PyInstaller + NSIS)
