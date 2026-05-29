"""
server/websocket/manager.py

WebSocket connection manager.
Handles: first-message authentication, heartbeats, event ingestion,
         examiner dashboard live feed.

Authentication flow (Option 2 — first message auth):
  1. Client connects (no token in URL)
  2. Client immediately sends: {"type": "auth", "token": "eyJ..."}
  3. Server validates JWT → sends {"type": "auth_ok"} or closes with 4001
  4. Normal message flow begins

Architecture:
  - One WS connection per active student session
  - One WS connection per examiner (for dashboard updates)
  - Students and examiners tracked separately
  - Examiner connections subscribed to a specific exam_id
"""
import asyncio
import hashlib
import json
from datetime import datetime
from typing import Dict, Set, Optional

from fastapi import WebSocket
from jose import jwt, JWTError

from shared.constants import WSMessageType, HEARTBEAT_TIMEOUT_SECONDS

# Auth timeout — client must send auth message within this many seconds
AUTH_TIMEOUT_SECONDS = 10


class ConnectionManager:
    def __init__(self):
        # session_id -> WebSocket (authenticated student connections)
        self.student_connections: Dict[str, WebSocket] = {}

        # exam_id -> set of WebSockets (authenticated examiner connections)
        self.examiner_connections: Dict[str, Set[WebSocket]] = {}

        # session_id -> last heartbeat datetime
        self.last_heartbeat: Dict[str, datetime] = {}

        # session_id -> exam_id mapping (needed for pause/broadcast scoping)
        self.session_exam_map: Dict[str, str] = {}

    # ── Authentication ─────────────────────────────────────────────────────

    async def authenticate(self, websocket: WebSocket) -> Optional[dict]:
        """
        Wait for the first message from the client.
        Expects: {"type": "auth", "token": "eyJ..."}

        Returns the decoded JWT payload on success.
        Closes the connection with code 4001 on failure.
        Returns None if authentication fails.
        """
        from server.config import get_settings
        settings = get_settings()

        try:
            # Wait for first message with timeout
            raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=AUTH_TIMEOUT_SECONDS,
            )
            data = json.loads(raw)

            if data.get("type") != "auth":
                await websocket.close(code=4001, reason="First message must be auth")
                return None

            token = data.get("token")
            if not token:
                await websocket.close(code=4001, reason="Missing token")
                return None

            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=4001, reason="Invalid token payload")
                return None

            return payload

        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="Auth timeout")
            return None
        except (JWTError, json.JSONDecodeError):
            await websocket.close(code=4001, reason="Invalid token")
            return None
        except Exception:
            await websocket.close(code=4001, reason="Auth failed")
            return None

    # ── Connection lifecycle ───────────────────────────────────────────────

    async def connect_student(
        self,
        websocket: WebSocket,
        session_id: str,
        exam_id: str,
        expected_student_id: Optional[str] = None,
    ) -> bool:
        """
        Accept connection, authenticate via first message.
        Returns True if authenticated successfully, False otherwise.
        """
        await websocket.accept()

        payload = await self.authenticate(websocket)
        if payload is None:
            return False
        
        if expected_student_id is not None and payload.get("sub") != expected_student_id:
            await websocket.close(code=4003, reason="Session ownership mismatch")
            return False

        self.student_connections[session_id] = websocket
        self.last_heartbeat[session_id] = datetime.utcnow()
        self.session_exam_map[session_id] = exam_id

        # Confirm auth success to client
        await websocket.send_json({
            "type": "auth_ok",
            "session_id": session_id,
            "server_time": datetime.utcnow().isoformat(),
        })

        return True

    def disconnect_student(self, session_id: str):
        self.student_connections.pop(session_id, None)
        self.last_heartbeat.pop(session_id, None)
        self.session_exam_map.pop(session_id, None)

    async def connect_examiner(
        self,
        websocket: WebSocket,
        exam_id: str,
        expected_examiner_id: Optional[str] = None,
    ) -> bool:
        """
        Accept examiner connection, authenticate via first message.
        Returns True if authenticated successfully, False otherwise.
        """
        await websocket.accept()

        payload = await self.authenticate(websocket)
        if payload is None:
            return False

        # Verify role is examiner
        if payload.get("role") != "examiner":
            await websocket.close(code=4003, reason="Examiner access required")
            return False

        if expected_examiner_id is not None and payload.get("sub") != expected_examiner_id:
            await websocket.close(code=4003, reason="Not allowed to monitor this exam")
            return False

        if exam_id not in self.examiner_connections:
            self.examiner_connections[exam_id] = set()
        self.examiner_connections[exam_id].add(websocket)

        await websocket.send_json({
            "type": "auth_ok",
            "exam_id": exam_id,
            "server_time": datetime.utcnow().isoformat(),
        })

        return True

    def disconnect_examiner(self, websocket: WebSocket, exam_id: str):
        if exam_id in self.examiner_connections:
            self.examiner_connections[exam_id].discard(websocket)

    # ── Sending messages ───────────────────────────────────────────────────

    async def send_to_student(self, session_id: str, message: dict):
        ws = self.student_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect_student(session_id)

    async def broadcast_to_examiners(self, exam_id: str, message: dict):
        """Push a message to all examiner dashboards watching this exam."""
        dead = set()
        for ws in self.examiner_connections.get(exam_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.examiner_connections[exam_id].discard(ws)

    async def broadcast_to_exam_students(self, exam_id: str, message: dict):
        """
        Broadcast to all students in a specific exam only.
        Fixes the original bug where EXAM_PAUSE went to ALL students
        across ALL exams.
        """
        # Find all session_ids belonging to this exam
        target_sessions = [
            sid for sid, eid in self.session_exam_map.items()
            if eid == exam_id
        ]
        for session_id in target_sessions:
            await self.send_to_student(session_id, message)

    # ── Heartbeat handling ─────────────────────────────────────────────────

    def record_heartbeat(self, session_id: str, client_time: datetime) -> float:
        self.last_heartbeat[session_id] = datetime.utcnow()
        server_time = datetime.utcnow()
        drift_seconds = abs((server_time - client_time).total_seconds())
        return drift_seconds

    def get_timed_out_sessions(self) -> list[str]:
        """Return session_ids whose heartbeat has expired."""
        now = datetime.utcnow()
        return [
            sid for sid, last in self.last_heartbeat.items()
            if (now - last).total_seconds() > HEARTBEAT_TIMEOUT_SECONDS
        ]

    # ── Incoming message dispatch ──────────────────────────────────────────

    async def handle_student_message(
        self,
        session_id: str,
        data: dict,
        exam_id: str,
        db,
    ):
        """Route an incoming WebSocket message from an authenticated student."""
        msg_type = data.get("type")

        if msg_type == WSMessageType.HEARTBEAT:
            from server.models.models import ExamSession, Exam

            client_time_str = data.get("client_time")
            client_time = (
                datetime.fromisoformat(client_time_str)
                if client_time_str
                else datetime.utcnow()
            )
            drift = self.record_heartbeat(session_id, client_time)

            # Flag suspicious clock drift (> 30 seconds)
            if drift > 30:
                await self.broadcast_to_examiners(exam_id, {
                    "type": WSMessageType.STUDENT_FLAG,
                    "session_id": session_id,
                    "reason": "clock_drift",
                    "drift_seconds": drift,
                })

            server_now = datetime.utcnow()

            await self.send_to_student(session_id, {
                "type": WSMessageType.CONNECTIVITY_ACK,
                "server_time": server_now.isoformat(),
            })

            session = db.query(ExamSession).filter(
                ExamSession.id == session_id,
                ExamSession.exam_id == exam_id,
            ).first()

            if session and session.started_at:
                exam = db.query(Exam).filter(Exam.id == session.exam_id).first()

                if exam and exam.duration_minutes:
                    from datetime import timedelta

                    exam_end_time = session.started_at + timedelta(
                        minutes=int(exam.duration_minutes)
                    )

                    await self.send_to_student(session_id, {
                        "type": WSMessageType.TIME_SYNC,
                        "server_time": server_now.isoformat(),
                        "exam_started_at": session.started_at.isoformat(),
                        "exam_end_time": exam_end_time.isoformat(),
                        "duration_minutes": exam.duration_minutes,
                    })

        elif msg_type == WSMessageType.EVENT_BATCH:
            events = data.get("events", [])
            await self._ingest_events(session_id, exam_id, events, db)

        elif msg_type == WSMessageType.ANSWER_SYNC:
            answers = data.get("answers", [])
            await self._sync_answers(session_id, answers, db)

        elif msg_type == WSMessageType.SESSION_STATE:
            await self.broadcast_to_examiners(exam_id, {
                "type": WSMessageType.STUDENT_STATUS_UPDATE,
                "session_id": session_id,
                "state": data.get("state"),
            })

    async def handle_examiner_message(
        self,
        websocket: WebSocket,
        exam_id: str,
        data: dict,
        db=None,
    ):
        """Route an incoming WebSocket message from an authenticated examiner."""
        msg_type = data.get("type")

        if msg_type == WSMessageType.EXAMINER_TERMINATE:
            from server.models.models import ExamSession
            from server.services.integrity import refresh_integrity_score
            from shared.constants import SessionStatus

            target_session: str | None = data.get("session_id")
            reason: str = data.get("reason", "Examiner terminated session")

            if not target_session:
                return

            if db is not None:
                from server.models.models import ExamSession
                from server.services.integrity import refresh_integrity_score
                from shared.constants import SessionStatus

                session = db.query(ExamSession).filter(
                    ExamSession.id == target_session,
                    ExamSession.exam_id == exam_id,
                ).first()

                if session and session.status not in (
                    SessionStatus.SUBMITTED,
                    SessionStatus.TERMINATED,
                ):
                    session.status = SessionStatus.TERMINATED
                    session.terminated_at = datetime.utcnow()
                    session.termination_reason = reason
                    refresh_integrity_score(session.id, db)
                    db.commit()

                    await self.broadcast_to_examiners(exam_id, {
                        "type": WSMessageType.STUDENT_STATUS_UPDATE,
                        "session_id": target_session,
                        "state": SessionStatus.TERMINATED.value,
                        "reason": reason,
                    })

            await self.send_to_student(target_session, {
                "type": WSMessageType.EXAMINER_TERMINATE,
                "reason": reason,   
            })

        elif msg_type == WSMessageType.EXAM_PAUSE:
            await self.broadcast_to_exam_students(exam_id, {
                "type": WSMessageType.EXAM_PAUSE,
            })

        elif msg_type == WSMessageType.EXAM_END:
            await self.broadcast_to_exam_students(exam_id, {
                "type": WSMessageType.EXAM_END,
            })
    # ── Event ingestion ────────────────────────────────────────────────────

    async def _ingest_events(
        self,
        session_id: str,
        exam_id: str,
        events: list,
        db,
    ):
        """
        Persist a batch of proctoring events and push high-severity ones
        to the examiner dashboard immediately.
        Builds SHA-256 chain hash for tamper evidence.
        """
        from server.models.models import ProctoringEvent
        from server.services.integrity import refresh_integrity_score
        from shared.constants import EventSeverity, EVENT_SEVERITY_MAP, EventType

        # Fetch last chain hash for this session
        last_event = (
            db.query(ProctoringEvent)
            .filter(ProctoringEvent.session_id == session_id)
            .order_by(ProctoringEvent.server_received_at.desc())
            .first()
        )
        prev_hash = last_event.chain_hash if last_event else "genesis"

        for event_data in events:
            try:
                event_type = EventType(event_data["event_type"])
            except ValueError:
                continue  # Skip unknown event types

            severity = EVENT_SEVERITY_MAP.get(event_type, EventSeverity.INFO)

            # Compute chain hash: SHA256(prev_hash + event_type + timestamp + session_id)
            raw = f"{prev_hash}{event_type}{event_data['timestamp']}{session_id}"
            chain_hash = hashlib.sha256(raw.encode()).hexdigest()

            event = ProctoringEvent(
                session_id=session_id,
                event_type=event_type,
                severity=severity,
                timestamp=datetime.fromisoformat(event_data["timestamp"]),
                metadata_=event_data.get("metadata"),
                snapshot_path=event_data.get("snapshot_path"),
                chain_hash=chain_hash,
            )
            db.add(event)
            prev_hash = chain_hash

            # Push high/critical events to examiner dashboard immediately
            if severity in (EventSeverity.HIGH, EventSeverity.CRITICAL):
                await self.broadcast_to_examiners(exam_id, {
                    "type": WSMessageType.STUDENT_FLAG,
                    "session_id": session_id,
                    "event_type": event_type,
                    "severity": severity,
                    "timestamp": event_data["timestamp"],
                    "metadata": event_data.get("metadata"),
                })

        score = refresh_integrity_score(session_id, db)
        db.commit()
        await self.broadcast_to_examiners(exam_id, {
            "type": WSMessageType.STUDENT_STATUS_UPDATE,
            "session_id": session_id,
            "integrity_score": score,
        })

    async def _sync_answers(self, session_id: str, answers: list, db):
        """
        Upsert student answers from local cache to the server.

        Security:
        - Only accepts answers for questions that belong to this session's exam.
        - Ignores malformed or foreign question IDs.
        """
        from server.models.models import Answer, ExamSession, Question

        session = db.query(ExamSession).filter(
            ExamSession.id == session_id,
        ).first()

        if not session:
            return

        valid_question_ids = {
            row[0]
            for row in db.query(Question.id).filter(
                Question.exam_id == session.exam_id,
            ).all()
        }

        now = datetime.utcnow()

        for ans_data in answers:
            question_id = ans_data.get("question_id")

            if not question_id or question_id not in valid_question_ids:
                continue

            existing = db.query(Answer).filter(
                Answer.session_id == session_id,
                Answer.question_id == question_id,
            ).first()

            if existing:
                existing.answer_text = ans_data.get("answer_text")
                existing.selected_option = ans_data.get("selected_option")
                existing.last_updated_at = now
            else:
                answer = Answer(
                    session_id=session_id,
                    question_id=question_id,
                    answer_text=ans_data.get("answer_text"),
                    selected_option=ans_data.get("selected_option"),
                    last_updated_at=now,
                )
                db.add(answer)

        db.commit()


# Singleton instance used across the entire server
manager = ConnectionManager()
