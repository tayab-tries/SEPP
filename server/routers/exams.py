"""
server/routers/exams.py
Module 2 — Class & Exam Management

Endpoints:
    POST   /classes                                        — examiner creates a class
    GET    /classes                                        — examiner views their classes
    POST   /classes/join-by-code/{code}                   — student joins via code
    POST   /classes/{class_id}/enroll                     — student requests enrollment
    PUT    /classes/{class_id}/enrollments/{id}/approve   — examiner approves enrollment
    GET    /classes/{class_id}/enrollments                — examiner views enrollments

    POST   /exams                                         — examiner creates exam
    GET    /exams/{exam_id}                               — get exam details
    PATCH  /exams/{exam_id}/status                        — examiner transitions exam status
    POST   /exams/{exam_id}/questions                     — examiner adds question
    GET    /exams/{exam_id}/questions                     — get questions (strips answers for students)
    DELETE /exams/{exam_id}/questions/{question_id}       — examiner removes question
"""

import random
import string
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import case, or_
from pydantic import BaseModel

from server.database import get_db
from server.models.models import Class, Enrollment, Exam, Question, User, ExamSession, ExamAccessRequest
from server.dependencies import get_current_user, require_examiner, require_student
from shared.constants import ExamStatus, QuestionType, Role, SessionStatus

router = APIRouter(tags=["exams"])


# ── Schemas ────────────────────────────────────────────────────────────────


class ClassCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ExamCreate(BaseModel):
    class_id: str
    title: str
    description: Optional[str] = None
    duration_minutes: int
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    max_window_switches: int = 3
    max_face_absent_seconds: int = 10
    allow_paste_in_essay: bool = False
    require_liveness_check: bool = True
    face_recheck_interval_minutes: int = 5

class QuestionCreate(BaseModel):
    question_type: QuestionType
    text: str
    marks: float = 1.0
    options: Optional[List[str]] = None       # MCQ: ["Option A", "Option B", ...]
    correct_option: Optional[str] = None      # MCQ: "A"
    max_words: Optional[int] = None           # Essay
    min_words: Optional[int] = None           # Essay

class ExamStatusUpdate(BaseModel):
    status: ExamStatus


# ── Helpers ────────────────────────────────────────────────────────────────

def generate_join_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_unique_exam_join_code(db: Session, length: int = 6) -> str:
    code = generate_join_code(length)

    while db.query(Exam).filter(Exam.join_code == code).first():
        code = generate_join_code(length)

    return code

def serialize_exam_access_request(req: ExamAccessRequest) -> dict:
    exam = req.exam

    return {
        "request_id": req.id,
        "exam_id": req.exam_id,
        "exam_name": exam.title if exam else "Unknown exam",
        "request_date": req.requested_at.isoformat() if req.requested_at else None,
        "status": "Approved" if req.approved else "Awaiting Approval",

        # Extra raw fields for future screens/debugging
        "approved": req.approved,
        "requested_at": req.requested_at.isoformat() if req.requested_at else None,
        "class_id": exam.class_id if exam else None,
        "scheduled_start": exam.scheduled_start.isoformat() if exam and exam.scheduled_start else None,
        "scheduled_end": exam.scheduled_end.isoformat() if exam and exam.scheduled_end else None,
    }

def serialize_student_exam(e: Exam) -> dict:
    question_count = len(e.questions or [])
    is_live = e.status == ExamStatus.LIVE
    return {
        "id": e.id,
        "exam_id": e.id,

        "class_id": e.class_id,
        "course_code": e.class_.join_code if e.class_ else None,

        "title": e.title,
        "description": e.description,
        "status": e.status.value if hasattr(e.status, "value") else str(e.status),

        "duration_minutes": e.duration_minutes,
        "start_time": e.scheduled_start.isoformat() if e.scheduled_start else None,
        "end_time": e.scheduled_end.isoformat() if e.scheduled_end else None,
        "question_count": question_count,
        "check_in_open": is_live and question_count > 0,

        "exam_type": "Proctored" if e.require_liveness_check else "Open Book",
    }
    
def get_student_access_ids(
    current_user: User,
    db: Session,
) -> tuple[set[str], set[str]]:
    """
    Returns:
      approved_class_ids — classes student is approved in
      approved_exam_ids  — exams student has direct approved access to
    """
    approved_class_ids = {
        e.class_id
        for e in db.query(Enrollment).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.approved == True,
        ).all()
    }

    approved_exam_ids = {
        r.exam_id
        for r in db.query(ExamAccessRequest).filter(
            ExamAccessRequest.student_id == current_user.id,
            ExamAccessRequest.approved == True,
        ).all()
    }

    return approved_class_ids, approved_exam_ids

# ── Class Routes ───────────────────────────────────────────────────────────

@router.post("/classes", status_code=201)
def create_class(
    req: ClassCreate,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner creates a class. Generates a unique 6-char join code."""
    code = generate_join_code()
    while db.query(Class).filter(Class.join_code == code).first():
        code = generate_join_code()

    class_ = Class(
        name=req.name,
        description=req.description,
        join_code=code,
        creator_id=current_user.id,
    )
    db.add(class_)
    db.commit()
    db.refresh(class_)
    return {
        "class_id": class_.id,
        "join_code": class_.join_code,
        "name": class_.name,
    }


@router.get("/classes")
def get_my_classes(
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner views all classes they created."""
    classes = db.query(Class).filter(Class.creator_id == current_user.id).all()
    return [
        {
            "class_id": c.id,
            "name": c.name,
            "description": c.description,
            "join_code": c.join_code,
            "created_at": c.created_at,
        }
        for c in classes
    ]


@router.get("/classes/enrolled")
def get_enrolled_classes(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Student views classes they requested/joined, including approval status."""
    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id
    ).all()

    if not enrollments:
        return []

    class_rows = db.query(Class).filter(
        Class.id.in_([e.class_id for e in enrollments])
    ).all()
    class_map: dict[str, Class] = {c.id: c for c in class_rows}

    return [
        {
            "class_id": e.class_id,
            "name": class_map[e.class_id].name if e.class_id in class_map else "Unknown class",
            "description": class_map[e.class_id].description if e.class_id in class_map else None,
            "approved": e.approved,
            "enrollment_id": e.id,
            "enrolled_at": e.enrolled_at,
        }
        for e in enrollments
    ]


@router.post("/classes/join-by-code/{code}")
def join_by_code(
    code: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student joins a class using the 6-char join code.
    Automatically creates a pending enrollment request.
    """
    class_ = db.query(Class).filter(Class.join_code == code.upper()).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Invalid join code")

    # Check if already enrolled or pending
    existing = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.class_id == class_.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already enrolled or pending approval")

    enrollment = Enrollment(
        student_id=current_user.id,
        class_id=class_.id,
        approved=False,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return {
        "class_id": class_.id,
        "class_name": class_.name,
        "enrollment_id": enrollment.id,
        "approved": enrollment.approved,
        "message": "Enrollment request submitted. Awaiting examiner approval.",
    }


@router.post("/classes/{class_id}/enroll")
def request_enrollment(
    class_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """Student requests to join a class by class ID. Examiner must approve."""
    class_ = db.query(Class).filter(Class.id == class_id).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")

    existing = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.class_id == class_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already enrolled or pending")

    enrollment = Enrollment(
        student_id=current_user.id,
        class_id=class_id,
        approved=False,
    )
    db.add(enrollment)
    db.commit()
    return {
        "message": "Enrollment request submitted. Awaiting examiner approval.",
        "enrollment_id": enrollment.id,
    }


@router.put("/classes/{class_id}/enrollments/{enrollment_id}/approve")
def approve_enrollment(
    class_id: str,
    enrollment_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner approves a pending student enrollment."""
    # Verify the class belongs to this examiner
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.creator_id == current_user.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found or not yours")

    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.class_id == class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    enrollment.approved = True
    db.commit()
    return {
        "message": "Enrollment approved",
        "enrollment_id": enrollment_id,
    }


@router.put("/classes/{class_id}/enrollments/{enrollment_id}/reject")
def reject_enrollment(
    class_id: str,
    enrollment_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner rejects and removes a pending enrollment."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.creator_id == current_user.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found or not yours")

    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.class_id == class_id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    db.delete(enrollment)
    db.commit()
    return {
        "message": "Enrollment rejected and removed",
        "enrollment_id": enrollment_id,
    }


@router.get("/classes/{class_id}/enrollments")
def get_enrollments(
    class_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner views all enrollments (pending and approved) for a class."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.creator_id == current_user.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found or not yours")

    enrollments = db.query(Enrollment).filter(
        Enrollment.class_id == class_id
    ).all()

    return [
        {
            "enrollment_id": e.id,
            "student_id": e.student_id,
            "approved": e.approved,
            "enrolled_at": e.enrolled_at,
        }
        for e in enrollments
    ]


@router.get("/classes/{class_id}/exams")
def list_class_exams(
    class_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Exams for a class owned by the current examiner."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.creator_id == current_user.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found or not yours")

    exams = (
        db.query(Exam)
        .filter(Exam.class_id == class_id)
        .order_by(Exam.created_at.desc())
        .all()
    )
    return [
        {
            "exam_id": e.id,
            "class_id": e.class_id,
            "title": e.title,
            "description": e.description,
            "status": e.status.value if hasattr(e.status, "value") else str(e.status),
            "duration_minutes": e.duration_minutes,
            "scheduled_start": e.scheduled_start,
            "scheduled_end": e.scheduled_end,
            "require_liveness_check": e.require_liveness_check,
            "face_recheck_interval_minutes": e.face_recheck_interval_minutes,
            "max_window_switches": e.max_window_switches,
            "max_face_absent_seconds": e.max_face_absent_seconds,
            "allow_paste_in_essay": e.allow_paste_in_essay,
        }
        for e in exams
    ]


# ── Exam Routes ────────────────────────────────────────────────────────────

@router.post("/exams", status_code=201)
def create_exam(
    req: ExamCreate,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner creates an exam inside one of their classes."""
    # Verify the class belongs to this examiner
    class_ = db.query(Class).filter(
        Class.id == req.class_id,
        Class.creator_id == current_user.id,
    ).first()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found or not yours")
    join_code = generate_unique_exam_join_code(db)

    exam = Exam(
        class_id=req.class_id,
        creator_id=current_user.id,
        join_code=join_code,
        title=req.title,
        description=req.description,
        duration_minutes=req.duration_minutes,
        scheduled_start=req.scheduled_start,
        scheduled_end=req.scheduled_end,
        max_window_switches=req.max_window_switches,
        max_face_absent_seconds=req.max_face_absent_seconds,
        allow_paste_in_essay=req.allow_paste_in_essay,
        require_liveness_check=req.require_liveness_check,
        face_recheck_interval_minutes=req.face_recheck_interval_minutes,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return {
    "exam_id": exam.id,
    "class_id": exam.class_id,
    "join_code": exam.join_code,
    "title": exam.title,
    "status": exam.status.value if hasattr(exam.status, "value") else str(exam.status),
    "duration_minutes": exam.duration_minutes,
    "scheduled_start": exam.scheduled_start,
    "scheduled_end": exam.scheduled_end,
}


@router.get("/exams")
def list_student_exams(
    class_id: Optional[str] = None,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student-visible exam listing.

    Supports both:
      1. Old access model: approved class enrollment
      2. New access model: approved direct exam access request
    """
    approved_class_ids, approved_exam_ids = get_student_access_ids(current_user, db)

    if class_id:
        # If student is approved in the whole class, show all exams in that class.
        if class_id in approved_class_ids:
            exams = (
                db.query(Exam)
                .filter(Exam.class_id == class_id)
                .order_by(Exam.scheduled_start.asc())
                .all()
            )
            return [serialize_student_exam(e) for e in exams]

        # Otherwise, show only directly approved exams from this class.
        if approved_exam_ids:
            exams = (
                db.query(Exam)
                .filter(
                    Exam.class_id == class_id,
                    Exam.id.in_(approved_exam_ids),
                )
                .order_by(Exam.scheduled_start.asc())
                .all()
            )

            if exams:
                return [serialize_student_exam(e) for e in exams]

        raise HTTPException(
            status_code=403,
            detail="You do not have approved access to exams in this class.",
        )

    if not approved_class_ids and not approved_exam_ids:
        return []

    access_filters = []

    if approved_class_ids:
        access_filters.append(Exam.class_id.in_(approved_class_ids))

    if approved_exam_ids:
        access_filters.append(Exam.id.in_(approved_exam_ids))

    exams = (
        db.query(Exam)
        .filter(or_(*access_filters))
        .order_by(Exam.scheduled_start.asc())
        .all()
    )

    return [serialize_student_exam(e) for e in exams]

@router.get("/exams/upcoming")
def list_upcoming_assessments(
    limit: int = 50,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Upcoming assessments for the authenticated student.

    Supports both:
      1. Approved class enrollment
      2. Approved direct exam access
    """
    approved_class_ids, approved_exam_ids = get_student_access_ids(current_user, db)

    if not approved_class_ids and not approved_exam_ids:
        return []

    access_filters = []

    if approved_class_ids:
        access_filters.append(Exam.class_id.in_(approved_class_ids))

    if approved_exam_ids:
        access_filters.append(Exam.id.in_(approved_exam_ids))

    exams = (
        db.query(Exam)
        .filter(
            or_(*access_filters),
            Exam.status != ExamStatus.CLOSED,
            ~Exam.id.in_(
                db.query(ExamSession.exam_id).filter(
                    ExamSession.student_id == current_user.id,
                    ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.TERMINATED]),
                )
            ),
        )
        .order_by(
            case(
                (Exam.status == ExamStatus.LIVE, 0),
                (Exam.status == ExamStatus.SCHEDULED, 1),
                (Exam.status == ExamStatus.DRAFT, 2),
                else_=3,
            ),
            Exam.scheduled_start.is_(None),
            Exam.scheduled_start.asc(),
            Exam.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    return [serialize_student_exam(e) for e in exams]

@router.get("/exams/next")
def get_next_exam(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Next immediate upcoming exam for the authenticated student.

    Supports both:
      1. Approved class enrollment
      2. Approved direct exam access
    """
    approved_class_ids, approved_exam_ids = get_student_access_ids(current_user, db)

    if not approved_class_ids and not approved_exam_ids:
        return None

    access_filters = []

    if approved_class_ids:
        access_filters.append(Exam.class_id.in_(approved_class_ids))

    if approved_exam_ids:
        access_filters.append(Exam.id.in_(approved_exam_ids))

    live_exam = (
        db.query(Exam)
        .filter(
            or_(*access_filters),
            Exam.status == ExamStatus.LIVE,
            ~Exam.id.in_(
                db.query(ExamSession.exam_id).filter(
                    ExamSession.student_id == current_user.id,
                    ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.TERMINATED]),
                )
            ),
        )
        .order_by(Exam.scheduled_start.asc())
        .first()
    )

    if live_exam:
        return serialize_student_exam(live_exam)

    scheduled_exam = (
        db.query(Exam)
        .filter(
            or_(*access_filters),
            Exam.status == ExamStatus.SCHEDULED,
            Exam.scheduled_start.isnot(None),
            ~Exam.id.in_(
                db.query(ExamSession.exam_id).filter(
                    ExamSession.student_id == current_user.id,
                    ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.TERMINATED]),
                )
            ),
        )
        .order_by(Exam.scheduled_start.asc())
        .first()
    )

    if scheduled_exam:
        return serialize_student_exam(scheduled_exam)

    draft_or_other_exam = (
        db.query(Exam)
        .filter(
            or_(*access_filters),
            Exam.status != ExamStatus.CLOSED,
        )
        .order_by(
            case(
                (Exam.status == ExamStatus.DRAFT, 0),
                else_=1,
            ),
            Exam.created_at.desc(),
        )
        .first()
    )

    if not draft_or_other_exam:
        return None

    return serialize_student_exam(draft_or_other_exam)

@router.get("/exams/examiner/owned")
def list_examiner_exams(
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """All exams created by the current examiner (any class they own)."""
    exams = (
        db.query(Exam)
        .filter(Exam.creator_id == current_user.id)
        .order_by(Exam.created_at.desc())
        .all()
    )
    class_ids = {e.class_id for e in exams}
    class_map = {
        c.id: c
        for c in db.query(Class).filter(Class.id.in_(class_ids)).all()
    } if class_ids else {}

    rows = []
    for e in exams:
        c = class_map.get(e.class_id)
        rows.append(
            {
                "exam_id": e.id,
                "join_code": e.join_code,
                "class_id": e.class_id,
                "class_name": c.name if c else "Unknown class",
                "title": e.title,
                "description": e.description,
                "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                "duration_minutes": e.duration_minutes,
                "scheduled_start": e.scheduled_start,
                "scheduled_end": e.scheduled_end,
            }
        )
    return rows

@router.get("/exams/access-requests/me")
def get_my_exam_access_requests(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student views their exam-level access requests.
    Used by the Exams page pending requests panel.
    """
    requests = (
        db.query(ExamAccessRequest)
        .join(Exam, Exam.id == ExamAccessRequest.exam_id)
        .filter(
            ExamAccessRequest.student_id == current_user.id,
            ExamAccessRequest.approved == False,
        )
        .order_by(ExamAccessRequest.requested_at.desc())
        .all()
    )

    return [serialize_exam_access_request(r) for r in requests]

@router.post("/exams/join-by-code/{code}", status_code=201)
def join_exam_by_code(
    code: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student requests access to an exam using the exam join code.
    Creates a pending exam-level access request.
    """
    normalized_code = code.strip().upper()

    exam = db.query(Exam).filter(Exam.join_code == normalized_code).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Invalid exam join code")

    existing = db.query(ExamAccessRequest).filter(
        ExamAccessRequest.student_id == current_user.id,
        ExamAccessRequest.exam_id == exam.id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="You have already requested access to this exam.",
        )

    access_request = ExamAccessRequest(
        student_id=current_user.id,
        exam_id=exam.id,
        approved=False,
    )

    db.add(access_request)
    db.commit()
    db.refresh(access_request)

    return {
        "request_id": access_request.id,
        "exam_id": exam.id,
        "exam_name": exam.title,
        "request_date": access_request.requested_at.isoformat(),
        "status": "Awaiting Approval",

        "approved": access_request.approved,
        "requested_at": access_request.requested_at.isoformat(),
        "message": "Exam access request submitted. Awaiting examiner approval.",
    }

@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get exam details. Accessible by both examiners and students."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    return {
        "exam_id": exam.id,
        "class_id": exam.class_id,
        "title": exam.title,
        "description": exam.description,
        "status": exam.status.value if hasattr(exam.status, "value") else str(exam.status),
        "duration_minutes": exam.duration_minutes,
        "scheduled_start": exam.scheduled_start,
        "scheduled_end": exam.scheduled_end,
        "allow_paste_in_essay": exam.allow_paste_in_essay,
        "require_liveness_check": exam.require_liveness_check,
        "face_recheck_interval_minutes": exam.face_recheck_interval_minutes,
        "max_window_switches": exam.max_window_switches,
        "max_face_absent_seconds": exam.max_face_absent_seconds,
    }


@router.patch("/exams/{exam_id}/status")
def update_exam_status(
    exam_id: str,
    req: ExamStatusUpdate,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """
    Examiner transitions exam through its lifecycle:
    DRAFT → SCHEDULED → LIVE → CLOSED
    """
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")

    valid_transitions = {
        ExamStatus.DRAFT:     [ExamStatus.SCHEDULED, ExamStatus.LIVE],
        ExamStatus.SCHEDULED: [ExamStatus.LIVE, ExamStatus.DRAFT],
        ExamStatus.LIVE:      [ExamStatus.CLOSED],
        ExamStatus.CLOSED:    [],
    }

    if req.status not in valid_transitions.get(exam.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {exam.status} to {req.status}",
        )

    if req.status == ExamStatus.LIVE:
        question_count = db.query(Question).filter(Question.exam_id == exam_id).count()
        if question_count == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot move this exam live until it has at least one question.",
            )

    exam.status = req.status
    db.commit()
    return {
        "exam_id": exam_id,
        "new_status": req.status.value if hasattr(req.status, "value") else str(req.status),
    }


@router.delete("/exams/{exam_id}")
def delete_exam(
    exam_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner deletes one of their draft exams."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")
    if exam.status != ExamStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft exams can be deleted")

    existing_sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id).count()
    if existing_sessions:
        raise HTTPException(
            status_code=400,
            detail="This exam already has sessions and cannot be deleted as a draft.",
        )

    db.query(ExamAccessRequest).filter(
        ExamAccessRequest.exam_id == exam_id
    ).delete(synchronize_session=False)
    db.query(Question).filter(
        Question.exam_id == exam_id
    ).delete(synchronize_session=False)
    db.delete(exam)
    db.commit()

    return {
        "message": "Draft exam deleted.",
        "exam_id": exam_id,
    }


@router.post("/exams/{exam_id}/questions", status_code=201)
def add_question(
    exam_id: str,
    req: QuestionCreate,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner adds a question to a DRAFT exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")
    if exam.status != ExamStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Cannot modify a non-draft exam")

    # Validate MCQ fields
    if req.question_type == QuestionType.MCQ:
        if not req.options or not req.correct_option:
            raise HTTPException(
                status_code=422,
                detail="MCQ requires options and correct_option",
            )

    order = db.query(Question).filter(Question.exam_id == exam_id).count()
    question = Question(
        exam_id=exam_id,
        order_index=order,
        question_type=req.question_type,
        text=req.text,
        marks=req.marks,
        options=req.options,
        correct_option=req.correct_option,
        max_words=req.max_words,
        min_words=req.min_words,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return {
        "question_id": question.id,
        "order_index": question.order_index,
        "question_type": question.question_type,
    }


@router.get("/exams/{exam_id}/questions")
def get_questions(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all questions for an exam.
    Examiners see full data including correct_option.
    Students get correct_option stripped — answers are never exposed.
    """
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if current_user.role == Role.EXAMINER:
        if exam.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not allowed to view this exam")
    else:
        approved_class_ids, approved_exam_ids = get_student_access_ids(current_user, db)
        has_access = exam.class_id in approved_class_ids or exam.id in approved_exam_ids
        has_session = db.query(ExamSession).filter(
            ExamSession.exam_id == exam_id,
            ExamSession.student_id == current_user.id,
        ).first()
        if not has_access and not has_session:
            raise HTTPException(status_code=403, detail="You do not have access to this exam")

    questions = db.query(Question).filter(
        Question.exam_id == exam_id
    ).order_by(Question.order_index).all()

    is_examiner = (current_user.role) == Role.EXAMINER
    show_correct = is_examiner

    if not is_examiner:
        completed = db.query(ExamSession).filter(
            ExamSession.exam_id == exam_id,
            ExamSession.student_id == current_user.id,
            ExamSession.status.in_([SessionStatus.SUBMITTED, SessionStatus.TERMINATED]),
        ).first()
        if completed:
            show_correct = True

    return [
        {
            "question_id": q.id,
            "order_index": q.order_index,
            "question_type": q.question_type,
            "text": q.text,
            "marks": q.marks,
            "options": q.options,
            "correct_option": q.correct_option if show_correct else None,
            "max_words": q.max_words,
            "min_words": q.min_words,
        }
        for q in questions
    ]


@router.delete("/exams/{exam_id}/questions/{question_id}")
def delete_question(
    exam_id: str,
    question_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """Examiner removes a question from a DRAFT exam."""
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")
    if exam.status != ExamStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Cannot modify a non-draft exam")

    question = db.query(Question).filter(
        Question.id == question_id,
        Question.exam_id == exam_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    db.delete(question)
    db.commit()

    # Re-index remaining questions
    remaining = db.query(Question).filter(
        Question.exam_id == exam_id
    ).order_by(Question.order_index).all()
    for i, q in enumerate(remaining):
        q.order_index = i
    db.commit()

    return {"message": "Question deleted"}

@router.get("/results/recent")
def list_recent_results(
    limit: int = 5,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Recent submitted exam results for the authenticated student.
    """
    sessions = (
        db.query(ExamSession)
        .join(Exam, ExamSession.exam_id == Exam.id)
        .filter(
            ExamSession.student_id == current_user.id,
            ExamSession.submitted_at.isnot(None),
        )
        .order_by(ExamSession.submitted_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for s in sessions:
        # Check if the exam has any essay questions
        has_essays = db.query(Question).filter(
            Question.exam_id == s.exam_id,
            Question.question_type == QuestionType.ESSAY
        ).count() > 0

        # It is graded if it has no essays OR if the essay_score has been assigned (i.e. not None)
        is_graded = s.essay_score is not None if has_essays else True

        results.append({
            "session_id": s.id,
            "exam_id": s.exam_id,

            "class_id": s.exam.class_id if s.exam else None,
            "course_code": s.exam.class_.join_code if s.exam and s.exam.class_ else None,

            "title": s.exam.title if s.exam else "Untitled Exam",
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,

            "mcq_score": s.mcq_score,
            "essay_score": s.essay_score,
            "total_score": (s.mcq_score or 0) + (s.essay_score or 0),
            "max_marks": sum(q.marks for q in db.query(Question).filter(Question.exam_id == s.exam_id).all()),
            "integrity_score": s.integrity_score,
            "is_graded": is_graded,

            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
        })

    return results

@router.delete("/exams/access-requests/{request_id}")
def cancel_my_exam_access_request(
    request_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student cancels their own pending exam access request.
    Approved requests should not be deleted from the student side.
    """
    access_request = db.query(ExamAccessRequest).filter(
        ExamAccessRequest.id == request_id,
        ExamAccessRequest.student_id == current_user.id,
    ).first()

    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")

    if access_request.approved:
        raise HTTPException(
            status_code=400,
            detail="Approved exam access cannot be cancelled from this page.",
        )

    db.delete(access_request)
    db.commit()

    return {
        "message": "Exam access request cancelled.",
        "request_id": request_id,
    }

@router.get("/exams/{exam_id}/access-requests")
def get_exam_access_requests(
    exam_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """
    Examiner views all access requests for one of their exams.
    """
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")

    requests = (
        db.query(ExamAccessRequest)
        .filter(ExamAccessRequest.exam_id == exam_id)
        .order_by(ExamAccessRequest.requested_at.desc())
        .all()
    )

    return [
        {
            "request_id": r.id,
            "exam_id": r.exam_id,
            "student_id": r.student_id,
            "student_name": r.student.full_name if r.student else None,
            "student_email": r.student.email if r.student else None,
            "approved": r.approved,
            "status": "Approved" if r.approved else "Awaiting Approval",
            "requested_at": r.requested_at,
        }
        for r in requests
    ]

@router.put("/exams/{exam_id}/access-requests/{request_id}/approve")
def approve_exam_access_request(
    exam_id: str,
    request_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """
    Examiner approves a student's exam-level access request.
    """
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")

    access_request = db.query(ExamAccessRequest).filter(
        ExamAccessRequest.id == request_id,
        ExamAccessRequest.exam_id == exam_id,
    ).first()

    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")

    access_request.approved = True
    db.commit()
    db.refresh(access_request)

    return {
        "message": "Exam access request approved.",
        "request_id": access_request.id,
        "exam_id": exam_id,
        "student_id": access_request.student_id,
        "approved": access_request.approved,
        "status": "Approved",
    }
    
@router.put("/exams/{exam_id}/access-requests/{request_id}/reject")
def reject_exam_access_request(
    exam_id: str,
    request_id: str,
    current_user: User = Depends(require_examiner),
    db: Session = Depends(get_db),
):
    """
    Examiner rejects/removes a student's exam-level access request.
    """
    exam = db.query(Exam).filter(
        Exam.id == exam_id,
        Exam.creator_id == current_user.id,
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found or not yours")

    access_request = db.query(ExamAccessRequest).filter(
        ExamAccessRequest.id == request_id,
        ExamAccessRequest.exam_id == exam_id,
    ).first()

    if not access_request:
        raise HTTPException(status_code=404, detail="Access request not found")

    db.delete(access_request)
    db.commit()

    return {
        "message": "Exam access request rejected and removed.",
        "request_id": request_id,
        "exam_id": exam_id,
    }
