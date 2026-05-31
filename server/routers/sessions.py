"""
server/routers/sessions.py
Module — Exam Session Management

Handles the lifecycle of a student's exam attempt:
    POST /sessions/start                    — student starts an exam session
    POST /sessions/{session_id}/submit      — student submits exam
    GET  /sessions/{session_id}             — get session details
    GET  /sessions/{session_id}/answers     — get student's answers
    GET  /exams/{exam_id}/sessions          — examiner views all sessions for exam
    POST /sessions/{session_id}/terminate   — examiner force-terminates a session
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from pydantic import BaseModel, Field

from server.database import get_db
from server.models.models import Exam, ExamSession, Enrollment, Answer, Question, Class, ProctoringEvent, ExamAccessRequest
from server.dependencies import get_current_user, require_examiner, require_student
from server.models.models import User
from server.services.integrity import (
    integrity_recommendation,
    proctoring_event_counts,
    refresh_essay_score,
    refresh_integrity_score,
)
from server.websocket.manager import manager
from shared.constants import ExamStatus, SessionStatus, Role, QuestionType, WSMessageType

router = APIRouter(tags=["sessions"])


# ── Schemas ────────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    exam_id: str

class TerminateSessionRequest(BaseModel):
    reason: str = "Terminated by examiner"

class AnswerReviewRequest(BaseModel):
    examiner_score: Optional[float] = None
    examiner_comment: Optional[str] = None

class FinalizeAnswer(BaseModel):
    question_id: str
    selected_option: Optional[str] = None
    answer_text: Optional[str] = None


class FinalizeSessionRequest(BaseModel):
    reason: str = "manual_submit"
    message: Optional[str] = None
    client_time: Optional[datetime] = None
    answers: List[FinalizeAnswer] = []


class FinalizeAnswer(BaseModel):
    question_id: str
    selected_option: Optional[str] = None
    answer_text: Optional[str] = None


class FinalizeSessionRequest(BaseModel):
    reason: str = "manual_submit"
    message: Optional[str] = None
    client_time: Optional[datetime] = None
    answers: List[FinalizeAnswer] = Field(default_factory=list)


# ── Student Routes ─────────────────────────────────────────────────────────

@router.post("/sessions/start", status_code=201)
def start_session(
    req: StartSessionRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student starts an exam session.

    Checks:
    1. Exam exists and is LIVE
    2. Student has approved access through class enrollment or direct exam access
    3. Student doesn't already have an active session for this exam
    4. Student has face enrolled (required for proctoring)
    """
    # 1. Exam must exist and be LIVE
    exam = db.query(Exam).filter(Exam.id == req.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.status != ExamStatus.LIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Exam is not live. Current status: {exam.status}",
        )

    question_count = db.query(Question).filter(Question.exam_id == exam.id).count()
    if question_count == 0:
        raise HTTPException(
            status_code=400,
            detail="This exam cannot be started because it has no questions yet.",
        )

    # 2. Student must have approved access
    # Access can come from:
    #   A) approved enrollment in the exam's class
    #   B) approved direct access request for this exam
    approved_class_enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.class_id == exam.class_id,
        Enrollment.approved == True,
    ).first()

    approved_exam_access = db.query(ExamAccessRequest).filter(
        ExamAccessRequest.student_id == current_user.id,
        ExamAccessRequest.exam_id == exam.id,
        ExamAccessRequest.approved == True,
    ).first()

    if not approved_class_enrollment and not approved_exam_access:
        raise HTTPException(
            status_code=403,
            detail="You do not have approved access to this exam.",
        )

    # 3. Check for existing session
    existing_session = db.query(ExamSession).filter(
        ExamSession.exam_id == req.exam_id,
        ExamSession.student_id == current_user.id,
    ).first()

    if existing_session:
        if existing_session.status in (SessionStatus.ACTIVE, SessionStatus.LOCKED, SessionStatus.VERIFYING):
            # Return existing active session so client can reconnect
            return {
                "session_id": existing_session.id,
                "exam_id": existing_session.exam_id,
                "status": existing_session.status,
                "started_at": existing_session.started_at,
                "message": "Reconnected to existing session",
            }
        if existing_session.status in (SessionStatus.SUBMITTED, SessionStatus.TERMINATED):
            raise HTTPException(
                status_code=409,
                detail="You have already completed this exam.",
            )

    # 4. Face must be enrolled
    if not current_user.face_enrolled:
        raise HTTPException(
            status_code=403,
            detail="Face enrollment required before starting an exam.",
        )

    # Create new session
    session = ExamSession(
        exam_id=req.exam_id,
        student_id=current_user.id,
        status=SessionStatus.VERIFYING,  # Face verification happens first
        started_at=None,                 # Timer starts only after activation
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": session.id,
        "exam_id": exam.id,
        "student_id": current_user.id,
        "status": session.status,
        "started_at": session.started_at,
        "duration_minutes": exam.duration_minutes,
        "message": "Session created. Complete face verification to begin.",
    }


@router.post("/sessions/{session_id}/activate")
def activate_session(
    session_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Called after face verification passes at exam entry.
    Transitions session from VERIFYING → ACTIVE.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.VERIFYING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate session with status: {session.status}",
        )

    session.status = SessionStatus.ACTIVE
    session.started_at = datetime.utcnow()
    db.commit()

    return {
        "session_id": session.id,
        "status": session.status,
        "message": "Session activated. Exam has begun.",
    }


@router.post("/sessions/{session_id}/submit")
def submit_session(
    session_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student submits exam. Transitions session to SUBMITTED.
    Auto-grades MCQ answers immediately.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in (SessionStatus.ACTIVE, SessionStatus.LOCKED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit session with status: {session.status}",
        )

    # Auto-grade MCQ answers
    mcq_score = _grade_mcq(session_id, db)
    integrity_score = refresh_integrity_score(session_id, db)

    session.status = SessionStatus.SUBMITTED
    session.submitted_at = datetime.utcnow()
    session.mcq_score = mcq_score
    db.commit()

    return {
        "session_id": session_id,
        "status": session.status,
        "submitted_at": session.submitted_at,
        "mcq_score": mcq_score,
        "integrity_score": integrity_score,
        "integrity_recommendation": integrity_recommendation(integrity_score),
        "message": "Exam submitted successfully.",
    }

@router.post("/sessions/{session_id}/finalize")
def finalize_session(
    session_id: str,
    req: FinalizeSessionRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Finalizes a student exam attempt with the latest client-side answers.

    Used for:
      - manual submit
      - timer expiry
      - examiner end exam
      - examiner terminate session
      - server hard termination
      - network lockdown timeout after reconnect

    Unlike /submit, this endpoint accepts answers in the request body,
    upserts them first, then grades/finalizes the session.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == current_user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    reason = (req.reason or "manual_submit").strip().lower()

    submitted_reasons = {
        "manual_submit",
        "time_up",
        "examiner_end",
    }

    terminated_reasons = {
        "examiner_terminate",
        "server_terminate",
        "network_timeout",
    }

    valid_reasons = submitted_reasons | terminated_reasons

    if reason not in valid_reasons:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid finalize reason: {reason}",
        )

    # Idempotent behavior:
    # If it is already submitted, do not mutate answers again.
    # This protects against accidental late overwrite after a successful final submit.
    if session.status == SessionStatus.SUBMITTED:
        integrity_score = refresh_integrity_score(session_id, db)
        db.commit()
        return {
            "session_id": session.id,
            "status": session.status,
            "submitted_at": session.submitted_at,
            "terminated_at": session.terminated_at,
            "termination_reason": session.termination_reason,
            "mcq_score": session.mcq_score,
            "integrity_score": integrity_score,
            "integrity_recommendation": integrity_recommendation(integrity_score),
            "message": "Session already finalized.",
        }

    # Allow finalization from active/locked sessions.
    # Also allow TERMINATED because examiner/server termination may hit backend
    # before the student client gets a chance to upload final local answers.
    allowed_statuses = {
        SessionStatus.ACTIVE,
        SessionStatus.LOCKED,
        SessionStatus.TERMINATED,
    }

    if session.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize session with status: {session.status}",
        )

    # Validate that submitted answers belong to this exam.
    questions = db.query(Question).filter(
        Question.exam_id == session.exam_id
    ).all()
    question_ids = {q.id for q in questions}

    now = datetime.utcnow()

    for item in req.answers:
        if item.question_id not in question_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Question does not belong to this exam: {item.question_id}",
            )

        answer = db.query(Answer).filter(
            Answer.session_id == session.id,
            Answer.question_id == item.question_id,
        ).first()

        if not answer:
            answer = Answer(
                session_id=session.id,
                question_id=item.question_id,
            )
            db.add(answer)

        answer.selected_option = item.selected_option
        answer.answer_text = item.answer_text
        answer.last_updated_at = now

    db.commit()

    # Grade after answers are definitely in DB.
    mcq_score = _grade_mcq(session_id, db)
    integrity_score = refresh_integrity_score(session_id, db)

    session.mcq_score = mcq_score

    # Final status decision.
    # If backend already marked it TERMINATED, keep it terminated.
    if session.status == SessionStatus.TERMINATED:
        session.terminated_at = session.terminated_at or now
        session.termination_reason = session.termination_reason or req.message or reason
        session.submitted_at = session.submitted_at or now

    elif reason in submitted_reasons:
        session.status = SessionStatus.SUBMITTED
        session.submitted_at = now

    else:
        session.status = SessionStatus.TERMINATED
        session.terminated_at = now
        session.termination_reason = req.message or reason
        session.submitted_at = now

    db.commit()

    return {
        "session_id": session.id,
        "status": session.status,
        "submitted_at": session.submitted_at,
        "terminated_at": session.terminated_at,
        "termination_reason": session.termination_reason,
        "mcq_score": mcq_score,
        "integrity_score": integrity_score,
        "integrity_recommendation": integrity_recommendation(integrity_score),
        "message": "Session finalized successfully.",
    }


@router.post("/sessions/{session_id}/finalize")
def finalize_session(
    session_id: str,
    req: FinalizeSessionRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Finalize a session with the latest client-side answers.

    Used for manual submit, timer expiry, examiner end, terminate, or reconnect recovery.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    reason = (req.reason or "manual_submit").strip().lower()
    submitted_reasons = {"manual_submit", "time_up", "examiner_end"}
    terminated_reasons = {"examiner_terminate", "server_terminate", "network_timeout"}
    valid_reasons = submitted_reasons | terminated_reasons

    if reason not in valid_reasons:
        raise HTTPException(status_code=422, detail=f"Invalid finalize reason: {reason}")

    if session.status == SessionStatus.SUBMITTED:
        integrity_score = refresh_integrity_score(session_id, db)
        db.commit()
        return {
            "session_id": session.id,
            "status": session.status,
            "submitted_at": session.submitted_at,
            "terminated_at": session.terminated_at,
            "termination_reason": session.termination_reason,
            "mcq_score": session.mcq_score,
            "integrity_score": integrity_score,
            "integrity_recommendation": integrity_recommendation(integrity_score),
            "message": "Session already finalized.",
        }

    if session.status not in {SessionStatus.ACTIVE, SessionStatus.LOCKED, SessionStatus.TERMINATED}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize session with status: {session.status}",
        )

    questions = db.query(Question).filter(Question.exam_id == session.exam_id).all()
    question_ids = {q.id for q in questions}
    now = datetime.utcnow()

    for item in req.answers:
        if item.question_id not in question_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Question does not belong to this exam: {item.question_id}",
            )

        answer = db.query(Answer).filter(
            Answer.session_id == session.id,
            Answer.question_id == item.question_id,
        ).first()
        if not answer:
            answer = Answer(session_id=session.id, question_id=item.question_id)
            db.add(answer)

        answer.selected_option = item.selected_option
        answer.answer_text = item.answer_text
        answer.last_updated_at = now

    db.commit()

    mcq_score = _grade_mcq(session_id, db)
    integrity_score = refresh_integrity_score(session_id, db)
    session.mcq_score = mcq_score

    if session.status == SessionStatus.TERMINATED:
        session.terminated_at = session.terminated_at or now
        session.termination_reason = session.termination_reason or req.message or reason
        session.submitted_at = session.submitted_at or now
    elif reason in submitted_reasons:
        session.status = SessionStatus.SUBMITTED
        session.submitted_at = now
    else:
        session.status = SessionStatus.TERMINATED
        session.terminated_at = now
        session.termination_reason = req.message or reason
        session.submitted_at = now

    db.commit()

    return {
        "session_id": session.id,
        "status": session.status,
        "submitted_at": session.submitted_at,
        "terminated_at": session.terminated_at,
        "termination_reason": session.termination_reason,
        "mcq_score": mcq_score,
        "integrity_score": integrity_score,
        "integrity_recommendation": integrity_recommendation(integrity_score),
        "message": "Session finalized successfully.",
    }


@router.get("/sessions/my-performance")
def get_my_performance(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student performance summary for dashboard cards.
    """
    sessions = db.query(ExamSession).filter(
        ExamSession.student_id == current_user.id
    ).all()

    total_sessions = len(sessions)
    completed_sessions = sum(1 for s in sessions if s.status == SessionStatus.SUBMITTED)
    active_sessions = sum(1 for s in sessions if s.status in (SessionStatus.ACTIVE, SessionStatus.LOCKED, SessionStatus.VERIFYING))

    mcq_scores = [float(s.mcq_score) for s in sessions if s.mcq_score is not None]
    integrity_scores = [float(s.integrity_score) for s in sessions if s.integrity_score is not None]
    avg_mcq = round(sum(mcq_scores) / len(mcq_scores), 2) if mcq_scores else 0.0
    avg_integrity = round(sum(integrity_scores) / len(integrity_scores), 2) if integrity_scores else 0.0

    # Total proctoring events across all student sessions.
    total_events = (
        db.query(func.count())
        .select_from(ExamSession)
        .join(ExamSession.events)
        .filter(ExamSession.student_id == current_user.id)
        .scalar()
    ) or 0

    return {
        "student_id": current_user.id,
        "full_name": current_user.full_name,
        "total_sessions": total_sessions,
        "completed_sessions": completed_sessions,
        "active_sessions": active_sessions,
        "average_mcq_score": avg_mcq,
        "average_integrity_score": avg_integrity,
        "total_proctoring_events": int(total_events),
    }


@router.get("/sessions/my-history")
def get_my_history(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student session history for analysis view.
    """
    rows = (
        db.query(ExamSession, Exam, Class)
        .join(Exam, Exam.id == ExamSession.exam_id)
        .outerjoin(Class, Class.id == Exam.class_id)
        .filter(ExamSession.student_id == current_user.id)
        .order_by(ExamSession.started_at.desc(), ExamSession.submitted_at.desc())
        .all()
    )

    history = []
    for session, exam, class_ in rows:
        mcq_score = float(session.mcq_score) if session.mcq_score is not None else 0.0
        essay_score = float(session.essay_score) if session.essay_score is not None else 0.0
        total_score = round(mcq_score + essay_score, 2)
        questions = db.query(Question).filter(Question.exam_id == session.exam_id).all()
        has_essays = any(q.question_type == QuestionType.ESSAY for q in questions)
        max_marks = sum(q.marks for q in questions)
        is_graded = session.essay_score is not None if has_essays else True
        history.append(
            {
                "session_id": session.id,
                "exam_id": exam.id,
                "class_id": exam.class_id,
                "class_name": class_.name if class_ else "Unknown class",
                "exam_title": exam.title,
                "exam_status": exam.status,
                "session_status": session.status,
                "scheduled_start": exam.scheduled_start,
                "scheduled_end": exam.scheduled_end,
                "started_at": session.started_at,
                "submitted_at": session.submitted_at,
                "mcq_score": session.mcq_score,
                "essay_score": session.essay_score,
                "total_score": total_score,
                "max_marks": max_marks,
                "integrity_score": session.integrity_score,
                "integrity_recommendation": integrity_recommendation(session.integrity_score),
                "is_graded": is_graded,
            }
        )

    return history


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get session details. Accessible by the student who owns it or an examiner."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Students can only see their own session
    if current_user.role == Role.STUDENT and session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    integrity_score = refresh_integrity_score(session_id, db)
    event_counts = proctoring_event_counts(session_id, db)
    db.commit()

    return {
        "session_id": session.id,
        "exam_id": session.exam_id,
        "student_id": session.student_id,
        "status": session.status,
        "started_at": session.started_at,
        "submitted_at": session.submitted_at,
        "terminated_at": session.terminated_at,
        "termination_reason": session.termination_reason,
        "mcq_score": session.mcq_score,
        "essay_score": session.essay_score,
        "integrity_score": integrity_score,
        "integrity_recommendation": integrity_recommendation(integrity_score),
        "proctoring_event_counts": event_counts,
        "gaze_away_count": event_counts.get("gaze_away", 0),
    }


@router.get("/sessions/{session_id}/answers")
def get_session_answers(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all answers for a session.
    Students can only see their own answers.
    Examiners can see any session's answers.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role == Role.STUDENT and session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == Role.EXAMINER:
        exam = db.query(Exam).filter(
            Exam.id == session.exam_id,
            Exam.creator_id == current_user.id,
        ).first()
        if not exam:
            raise HTTPException(status_code=403, detail="Not allowed to view this session")
        if session.status not in (SessionStatus.SUBMITTED, SessionStatus.TERMINATED):
            raise HTTPException(status_code=400, detail="Answers are reviewable only after the session is done")

    answers = db.query(Answer).filter(Answer.session_id == session_id).all()

    return [
        {
            "answer_id": a.id,
            "question_id": a.question_id,
            "selected_option": a.selected_option,
            "answer_text": a.answer_text,
            "is_correct": a.is_correct,
            "examiner_score": a.examiner_score,
            "examiner_comment": a.examiner_comment,
            "last_updated_at": a.last_updated_at,
        }
        for a in answers
    ]


@router.get("/sessions/{session_id}/proctoring-events")
def get_session_proctoring_events(
    session_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """
    Proctoring events for one student session. Examiner must own the exam for that session.
    Ordered newest first.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    exam = db.query(Exam).filter(
        Exam.id == session.exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=403, detail="Not allowed to view this session")

    events = (
        db.query(ProctoringEvent)
        .filter(ProctoringEvent.session_id == session_id)
        .order_by(ProctoringEvent.timestamp.desc())
        .all()
    )

    def _sev(s):
        return s.value if hasattr(s, "value") else str(s)

    def _et(t):
        return t.value if hasattr(t, "value") else str(t)

    return [
        {
            "event_id": ev.id,
            "session_id": ev.session_id,
            "event_type": _et(ev.event_type),
            "severity": _sev(ev.severity),
            "timestamp": ev.timestamp,
            "server_received_at": ev.server_received_at,
            "metadata": ev.metadata_,
            "snapshot_path": ev.snapshot_path,
            "examiner_note": ev.examiner_note,
            "dismissed": ev.dismissed,
        }
        for ev in events
    ]


# ── Examiner Routes ────────────────────────────────────────────────────────

@router.get("/exams/{exam_id}/sessions")
def get_exam_sessions(
    exam_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner views all student sessions for an exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")

    sessions = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id
    ).all()
    for session in sessions:
        refresh_integrity_score(session.id, db)
    db.commit()

    has_essays = any(q.question_type.value == "essay" for q in exam.questions)

    rows = []
    for s in sessions:
        event_counts = proctoring_event_counts(s.id, db)
        student_name = s.student.full_name if s.student else "Unknown Student"
        is_graded = s.essay_score is not None if has_essays else True
        rows.append({
            "session_id": s.id,
            "student_id": s.student_id,
            "student_name": student_name,
            "status": s.status,
            "is_graded": is_graded,
            "started_at": s.started_at,
            "submitted_at": s.submitted_at,
            "terminated_at": s.terminated_at,
            "mcq_score": s.mcq_score,
            "essay_score": s.essay_score,
            "integrity_score": s.integrity_score,
            "integrity_recommendation": integrity_recommendation(s.integrity_score),
            "proctoring_event_counts": event_counts,
            "gaze_away_count": event_counts.get("gaze_away", 0),
        })
    return rows


from fastapi import BackgroundTasks
from server.websocket.manager import manager
from shared.constants import WSMessageType

@router.post("/sessions/{session_id}/terminate")
def terminate_session(
    session_id: str,
    req: TerminateSessionRequest,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner force-terminates an active student session."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status in (SessionStatus.SUBMITTED, SessionStatus.TERMINATED):
        raise HTTPException(
            status_code=400,
            detail="Session is already completed or terminated",
        )

    session.status = SessionStatus.TERMINATED
    session.terminated_at = datetime.utcnow()
    session.termination_reason = req.reason
    integrity_score = refresh_integrity_score(session_id, db)
    db.commit()

    termination_message = {
        "type": WSMessageType.EXAMINER_TERMINATE,
        "reason": req.reason,
    }
    status_update = {
        "type": WSMessageType.STUDENT_STATUS_UPDATE,
        "session_id": session_id,
        "state": SessionStatus.TERMINATED.value,
        "reason": req.reason,
    }

    if background_tasks is not None:
        background_tasks.add_task(manager.send_to_student, session_id, termination_message)
        background_tasks.add_task(manager.broadcast_to_examiners, session.exam_id, status_update)
    else:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            loop.create_task(manager.send_to_student(session_id, termination_message))
            loop.create_task(manager.broadcast_to_examiners(session.exam_id, status_update))

    return {
        "session_id": session_id,
        "status": session.status,
        "reason": req.reason,
        "integrity_score": integrity_score,
        "integrity_recommendation": integrity_recommendation(integrity_score),
    }


@router.patch("/sessions/{session_id}/answers/{question_id}/review")
def review_answer(
    session_id: str,
    question_id: str,
    req: AnswerReviewRequest,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner score/comment for one answer in a session they own."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    exam = db.query(Exam).filter(
        Exam.id == session.exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=403, detail="Not allowed to review this session")
    if session.status not in (SessionStatus.SUBMITTED, SessionStatus.TERMINATED):
        raise HTTPException(status_code=400, detail="Answers can be graded only after the session is done")

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.exam_id == session.exam_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found for this exam")

    answer = db.query(Answer).filter(
        Answer.session_id == session_id,
        Answer.question_id == question_id,
    ).first()
    if not answer:
        answer = Answer(session_id=session_id, question_id=question_id)
        db.add(answer)

    answer.examiner_score = req.examiner_score
    answer.examiner_comment = req.examiner_comment
    essay_score = refresh_essay_score(session_id, db)
    db.commit()
    db.refresh(answer)

    return {
        "answer_id": answer.id,
        "question_id": answer.question_id,
        "selected_option": answer.selected_option,
        "answer_text": answer.answer_text,
        "is_correct": answer.is_correct,
        "examiner_score": answer.examiner_score,
        "examiner_comment": answer.examiner_comment,
        "session_essay_score": essay_score,
        "last_updated_at": answer.last_updated_at,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _grade_mcq(session_id: str, db: Session) -> float:
    """
    Auto-grade all MCQ answers for a session.
    Marks each answer as correct/incorrect and returns total MCQ score.
    """
    answers = db.query(Answer).filter(Answer.session_id == session_id).all()
    total_score = 0.0

    for answer in answers:
        question = db.query(Question).filter(
            Question.id == answer.question_id
        ).first()

        if not question or question.question_type.value != "mcq":
            continue

        is_correct = (
            answer.selected_option is not None and
            answer.selected_option == question.correct_option
        )
        answer.is_correct = is_correct
        if is_correct:
            total_score += question.marks

    db.commit()
    return round(total_score, 2)
