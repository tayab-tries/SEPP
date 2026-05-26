"""
Repeatable in-process regression check for the core exam flow.

Covers:
  1. Student requests exam access by join code
  2. Examiner sees and approves the request
  3. Student sees approved upcoming/live exam
  4. Student starts and activates a session
  5. Runtime WebSocket flow: auth, heartbeat, answer sync, proctoring event
  6. Student reconnects to the same active session
  7. Student submits normally
  8. Examiner force-terminates a separate active session

This avoids live HTTP sockets so it can run in restricted environments.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.database import SessionLocal
from server.models.models import User
from server.routers.auth import hash_password, login
from server.routers.exams import (
    ClassCreate,
    ExamCreate,
    ExamStatusUpdate,
    QuestionCreate,
    add_question,
    approve_exam_access_request,
    create_class,
    create_exam,
    get_exam_access_requests,
    get_my_exam_access_requests,
    get_next_exam,
    join_exam_by_code,
    list_upcoming_assessments,
    update_exam_status,
)
from server.routers.sessions import (
    StartSessionRequest,
    TerminateSessionRequest,
    activate_session,
    get_session_answers,
    start_session,
    submit_session,
    terminate_session,
)
from server.websocket.manager import manager
from shared.constants import EventType, ExamStatus, QuestionType, Role, WSMessageType


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def status_value(value):
    return value.value if hasattr(value, "value") else value


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class FakeWebSocket:
    def __init__(self, token: str) -> None:
        self._incoming = [json.dumps({"type": "auth", "token": token})]
        self.sent_json: list[dict] = []
        self.accepted = False
        self.closed: dict | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if not self._incoming:
            raise RuntimeError("No more queued incoming websocket messages")
        return self._incoming.pop(0)

    async def send_json(self, message: dict) -> None:
        self.sent_json.append(message)

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.closed = {"code": code, "reason": reason}


def make_user(
    *,
    email: str,
    password: str,
    role: Role,
    first_name: str,
    last_name: str,
    face_enrolled: bool,
) -> User:
    return User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        face_enrolled=face_enrolled,
        face_embedding=[0.1, 0.2, 0.3] if face_enrolled else None,
    )


def issue_token(db, email: str, password: str) -> str:
    token_response = login(
        form=SimpleNamespace(username=email, password=password),
        db=db,
    )
    return token_response.access_token


async def main() -> None:
    db = SessionLocal()
    suffix = uuid4().hex[:8]

    examiner_password = "Examiner123!"
    student_password = "Student123!"
    examiner = make_user(
        email=f"e2e.examiner.{suffix}@sepp.local",
        password=examiner_password,
        role=Role.EXAMINER,
        first_name="E2E",
        last_name="Examiner",
        face_enrolled=False,
    )
    student = make_user(
        email=f"e2e.student.{suffix}@sepp.local",
        password=student_password,
        role=Role.STUDENT,
        first_name="E2E",
        last_name="Student",
        face_enrolled=True,
    )
    db.add_all([examiner, student])
    db.commit()
    db.refresh(examiner)
    db.refresh(student)

    examiner_token = issue_token(db, examiner.email, examiner_password)
    student_token = issue_token(db, student.email, student_password)
    print("STEP login OK")

    examiner_ws_1: FakeWebSocket | None = None
    student_ws_1: FakeWebSocket | None = None
    examiner_ws_2: FakeWebSocket | None = None
    student_ws_2: FakeWebSocket | None = None
    exam1_id: str | None = None
    exam2_id: str | None = None
    session1_id: str | None = None
    session2_id: str | None = None

    try:
        class_result = create_class(
            ClassCreate(name=f"E2E Class {suffix}", description="Regression harness"),
            current_user=examiner,
            db=db,
        )
        class_id = class_result["class_id"]
        print(f"SETUP class OK: {class_id}")

        exam1 = create_exam(
            ExamCreate(
                class_id=class_id,
                title=f"E2E Primary Exam {suffix}",
                description="Primary flow",
                duration_minutes=45,
                scheduled_start=utcnow() + timedelta(minutes=5),
                scheduled_end=utcnow() + timedelta(minutes=50),
                require_liveness_check=False,
            ),
            current_user=examiner,
            db=db,
        )
        exam1_id = exam1["exam_id"]
        print(f"SETUP exam1 OK: {exam1_id}")

        mcq_question = add_question(
            exam1_id,
            QuestionCreate(
                question_type=QuestionType.MCQ,
                text="Which layer handles routing?",
                marks=2.0,
                options=["Application", "Transport", "Network", "Data Link"],
                correct_option="C",
            ),
            current_user=examiner,
            db=db,
        )
        essay_question = add_question(
            exam1_id,
            QuestionCreate(
                question_type=QuestionType.ESSAY,
                text="Explain why least privilege matters.",
                marks=5.0,
                min_words=30,
                max_words=150,
            ),
            current_user=examiner,
            db=db,
        )

        update_exam_status(
            exam1_id,
            ExamStatusUpdate(status=ExamStatus.LIVE),
            current_user=examiner,
            db=db,
        )

        request_result = join_exam_by_code(
            exam1["join_code"],
            current_user=student,
            db=db,
        )
        request_id = request_result["request_id"]
        require(request_result["approved"] is False, "New request should start pending")
        print("STEP request access OK")

        pending_for_examiner = get_exam_access_requests(exam1_id, current_user=examiner, db=db)
        require(any(row["request_id"] == request_id for row in pending_for_examiner), "Examiner should see pending request")
        print("CHECK pending visible OK")

        pending_for_student = get_my_exam_access_requests(current_user=student, db=db)
        require(any(row["request_id"] == request_id for row in pending_for_student), "Student pending panel should contain request")
        print("CHECK student pending OK")

        approve_result = approve_exam_access_request(
            exam1_id,
            request_id,
            current_user=examiner,
            db=db,
        )
        require(approve_result["approved"] is True, "Approve route should mark request approved")
        print("STEP approve OK")

        pending_after_approval = get_my_exam_access_requests(current_user=student, db=db)
        require(not any(row["request_id"] == request_id for row in pending_after_approval), "Approved request should leave pending panel")

        upcoming = list_upcoming_assessments(current_user=student, db=db)
        require(any(row["exam_id"] == exam1_id for row in upcoming), "Approved live exam should appear in upcoming exams")

        next_exam = get_next_exam(current_user=student, db=db)
        require(next_exam is not None and next_exam["exam_id"] == exam1_id, "Next exam should resolve to approved live exam")
        print("STEP approved access visible OK")

        start_result = start_session(
            StartSessionRequest(exam_id=exam1_id),
            current_user=student,
            db=db,
        )
        session1_id = start_result["session_id"]
        require(status_value(start_result["status"]) == "verifying", "New session should start in verifying")

        activate_result = activate_session(session1_id, current_user=student, db=db)
        require(status_value(activate_result["status"]) == "active", "Activation should transition session to active")
        print("STEP start/activate OK")

        examiner_ws_1 = FakeWebSocket(examiner_token)
        student_ws_1 = FakeWebSocket(student_token)
        require(await manager.connect_examiner(examiner_ws_1, exam1_id), "Examiner websocket should authenticate")
        require(await manager.connect_student(student_ws_1, session1_id, exam1_id), "Student websocket should authenticate")

        await manager.handle_student_message(
            session1_id,
            {
                "type": WSMessageType.HEARTBEAT,
                "client_time": utcnow().isoformat(),
            },
            exam1_id,
            db,
        )
        await manager.handle_student_message(
            session1_id,
            {
                "type": WSMessageType.ANSWER_SYNC,
                "answers": [
                    {"question_id": mcq_question["question_id"], "selected_option": "C"},
                    {
                        "question_id": essay_question["question_id"],
                        "answer_text": "Least privilege reduces blast radius and limits misuse.",
                    },
                ],
            },
            exam1_id,
            db,
        )
        await manager.handle_student_message(
            session1_id,
            {
                "type": WSMessageType.EVENT_BATCH,
                "events": [
                    {
                        "event_type": EventType.MULTIPLE_FACES.value,
                        "timestamp": utcnow().isoformat(),
                        "metadata": {"faces": 2},
                    }
                ],
            },
            exam1_id,
            db,
        )
        await manager.handle_student_message(
            session1_id,
            {
                "type": WSMessageType.SESSION_STATE,
                "state": "active",
            },
            exam1_id,
            db,
        )

        answers_before_submit = get_session_answers(session1_id, current_user=student, db=db)
        require(len(answers_before_submit) == 2, "Answer sync should persist both answers")
        require(any(a["selected_option"] == "C" for a in answers_before_submit), "MCQ answer should persist")
        require(any((a["answer_text"] or "").startswith("Least privilege") for a in answers_before_submit), "Essay answer should persist")

        require(
            any(msg["type"] == WSMessageType.CONNECTIVITY_ACK for msg in student_ws_1.sent_json),
            "Student should receive connectivity ACK",
        )
        require(
            any(msg["type"] == WSMessageType.STUDENT_FLAG for msg in examiner_ws_1.sent_json),
            "Examiner should receive high-severity flag",
        )
        require(
            any(msg["type"] == WSMessageType.STUDENT_STATUS_UPDATE for msg in examiner_ws_1.sent_json),
            "Examiner should receive status update",
        )
        print("STEP runtime OK")

        reconnect_result = start_session(
            StartSessionRequest(exam_id=exam1_id),
            current_user=student,
            db=db,
        )
        require(reconnect_result["session_id"] == session1_id, "Reconnect should return existing session")
        require(reconnect_result["message"] == "Reconnected to existing session", "Reconnect message should be explicit")
        print("STEP reconnect OK")

        submit_result = submit_session(session1_id, current_user=student, db=db)
        require(status_value(submit_result["status"]) == "submitted", "Submit should transition to submitted")
        require(float(submit_result["mcq_score"]) == 2.0, "MCQ grading should match the correct answer")
        print("STEP submit OK")

        exam2 = create_exam(
            ExamCreate(
                class_id=class_id,
                title=f"E2E Terminate Exam {suffix}",
                description="Terminate flow",
                duration_minutes=30,
                scheduled_start=utcnow() + timedelta(minutes=10),
                scheduled_end=utcnow() + timedelta(minutes=40),
                require_liveness_check=False,
            ),
            current_user=examiner,
            db=db,
        )
        exam2_id = exam2["exam_id"]
        add_question(
            exam2_id,
            QuestionCreate(
                question_type=QuestionType.MCQ,
                text="2 + 2 = ?",
                marks=1.0,
                options=["1", "2", "3", "4"],
                correct_option="D",
            ),
            current_user=examiner,
            db=db,
        )
        update_exam_status(
            exam2_id,
            ExamStatusUpdate(status=ExamStatus.LIVE),
            current_user=examiner,
            db=db,
        )

        request2 = join_exam_by_code(exam2["join_code"], current_user=student, db=db)
        approve_exam_access_request(exam2_id, request2["request_id"], current_user=examiner, db=db)
        session2_start = start_session(StartSessionRequest(exam_id=exam2_id), current_user=student, db=db)
        session2_id = session2_start["session_id"]
        activate_session(session2_id, current_user=student, db=db)

        examiner_ws_2 = FakeWebSocket(examiner_token)
        student_ws_2 = FakeWebSocket(student_token)
        require(await manager.connect_examiner(examiner_ws_2, exam2_id), "Second examiner websocket should authenticate")
        require(await manager.connect_student(student_ws_2, session2_id, exam2_id), "Second student websocket should authenticate")

        reason = "Policy violation"
        await manager.handle_examiner_message(
            examiner_ws_2,
            exam2_id,
            {
                "type": WSMessageType.EXAMINER_TERMINATE,
                "session_id": session2_id,
                "reason": reason,
            },
        )
        terminate_result = terminate_session(
            session2_id,
            TerminateSessionRequest(reason=reason),
            current_user=examiner,
            db=db,
        )
        require(status_value(terminate_result["status"]) == "terminated", "Terminate route should transition session to terminated")
        require(
            any(msg["type"] == WSMessageType.EXAMINER_TERMINATE and msg["reason"] == reason for msg in student_ws_2.sent_json),
            "Student should receive terminate websocket message",
        )
        print("STEP forced terminate OK")

        print("ALL E2E CORE STEPS PASSED")
    finally:
        if session1_id:
            manager.disconnect_student(session1_id)
        if session2_id:
            manager.disconnect_student(session2_id)
        if examiner_ws_1 and exam1_id:
            manager.disconnect_examiner(examiner_ws_1, exam1_id)
        if examiner_ws_2 and exam2_id:
            manager.disconnect_examiner(examiner_ws_2, exam2_id)
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
