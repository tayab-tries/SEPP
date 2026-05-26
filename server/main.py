"""
server/main.py
Server entry point.
Run with: uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from server.config import get_settings
from server.database import engine, Base, get_db
from server.routers import auth, exams
from server.routers import sessions
from server.websocket.manager import manager
from shared.constants import WSMessageType, SessionStatus

settings = get_settings()


# ── Startup / Shutdown ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup (use Alembic migrations in production)
    Base.metadata.create_all(bind=engine)
    _ensure_dev_schema()

    # Start background task: sweep for timed-out heartbeats
    heartbeat_task = asyncio.create_task(heartbeat_monitor())

    exam_tasks: list[asyncio.Task] = []
    if settings.EXAM_AUTO_SCHEDULER:
        exam_tasks.append(asyncio.create_task(exam_schedule_monitor()))

    yield  # Server is running

    heartbeat_task.cancel()
    for t in exam_tasks:
        t.cancel()


def _ensure_dev_schema():
    """
    Development schema patching for nullable columns added after create_all.
    This keeps existing local SQLite databases usable without a migration stack.
    """
    inspector = inspect(engine)
    if "answers" not in inspector.get_table_names():
        return
    answer_columns = {column["name"] for column in inspector.get_columns("answers")}
    with engine.begin() as conn:
        if "examiner_comment" not in answer_columns:
            conn.execute(text("ALTER TABLE answers ADD COLUMN examiner_comment TEXT"))
        if "exams" in inspector.get_table_names():
            exam_columns = {column["name"] for column in inspector.get_columns("exams")}
            if "join_code" not in exam_columns:
                conn.execute(text("ALTER TABLE exams ADD COLUMN join_code VARCHAR"))


async def heartbeat_monitor():
    """
    Runs every 5 seconds.
    Finds sessions with expired heartbeats and alerts examiner dashboards.
    """
    from server.models.models import ExamSession
    from server.database import SessionLocal

    while True:
        await asyncio.sleep(5)
        timed_out = manager.get_timed_out_sessions()

        if timed_out:
            db = SessionLocal()
            try:
                for session_id in timed_out:
                    session = db.query(ExamSession).filter(
                        ExamSession.id == session_id
                    ).first()

                    if session and session.status == SessionStatus.ACTIVE:
                        exam_id = manager.session_exam_map.get(session_id)
                        if exam_id:
                            await manager.broadcast_to_examiners(exam_id, {
                                "type": WSMessageType.STUDENT_STATUS_UPDATE,
                                "session_id": session_id,
                                "state": "connection_lost",
                            })
            finally:
                db.close()


async def exam_schedule_monitor():
    """
    When EXAM_AUTO_SCHEDULER is enabled, promotes SCHEDULED exams to LIVE
    once scheduled_start is reached (naive UTC comparison with DB datetimes).
    """
    from server.database import SessionLocal
    from server.models.models import Exam
    from shared.constants import ExamStatus

    while True:
        await asyncio.sleep(60)
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            due = (
                db.query(Exam)
                .filter(
                    Exam.status == ExamStatus.SCHEDULED,
                    Exam.scheduled_start.isnot(None),
                    Exam.scheduled_start <= now,
                )
                .all()
            )
            for exam in due:
                exam.status = ExamStatus.LIVE
            if due:
                db.commit()
        finally:
            db.close()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(exams.router)
app.include_router(sessions.router)


# ── WebSocket Endpoints ────────────────────────────────────────────────────

@app.websocket("/ws/student/{session_id}/{exam_id}")
async def student_websocket(
    websocket: WebSocket,
    session_id: str,
    exam_id: str,
    db: Session = Depends(get_db),
):
    """
    Persistent WebSocket for an active student session.

    Auth flow:
      1. Connection accepted
      2. Client sends {"type": "auth", "token": "..."}
      3. Server validates JWT → sends auth_ok or closes 4001
      4. Normal message loop begins

    Handles: heartbeats, answer syncs, event batches.
    """
    # Verify session exists and belongs to correct exam before accepting
    from server.models.models import ExamSession
    db_session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.exam_id == exam_id,
    ).first()

    if not db_session:
        await websocket.close(code=4004, reason="Session not found")
        return

    if db_session.status not in (SessionStatus.ACTIVE, SessionStatus.LOCKED, SessionStatus.VERIFYING):
        await websocket.close(code=4005, reason="Session is not active")
        return

    authenticated = await manager.connect_student(websocket, session_id, exam_id)
    if not authenticated:
        return  # connect_student already closed the connection

    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_student_message(session_id, data, exam_id, db)
    except WebSocketDisconnect:
        manager.disconnect_student(session_id)


@app.websocket("/ws/examiner/{exam_id}")
async def examiner_websocket(
    websocket: WebSocket,
    exam_id: str,
    db: Session = Depends(get_db),
):
    """
    Persistent WebSocket for examiner dashboard.

    Auth flow same as student WS.
    Receives live alerts when students are flagged.
    Can send: EXAMINER_TERMINATE, EXAM_PAUSE, EXAM_END
    """
    # Verify exam exists
    from server.models.models import Exam
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        await websocket.close(code=4004, reason="Exam not found")
        return

    authenticated = await manager.connect_examiner(websocket, exam_id)
    if not authenticated:
        return

    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_examiner_message(websocket, exam_id, data)
    except WebSocketDisconnect:
        manager.disconnect_examiner(websocket, exam_id)


@app.get("/health")
def health_check():
    return {"status": "ok", "gpu": _check_gpu()}


def _check_gpu() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        return "cpu"
    except Exception:
        return "unknown"
