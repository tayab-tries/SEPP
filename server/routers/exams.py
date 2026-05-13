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
from pydantic import BaseModel

from server.database import get_db
from server.models.models import Class, Enrollment, Exam, Question, User
from server.dependencies import get_current_user, require_examiner, require_student
from shared.constants import ExamStatus, QuestionType, Role

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

    exam = Exam(
        class_id=req.class_id,
        creator_id=current_user.id,
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
        "title": exam.title,
        "status": exam.status.value if hasattr(exam.status, "value") else str(exam.status),
    }


@router.get("/exams")
def list_student_exams(
    class_id: Optional[str] = None,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    """
    Student-visible exam listing.
    If class_id is provided, return exams for that approved class only.
    Otherwise return exams across all approved classes.
    """
    approved_enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.approved == True,
    ).all()
    approved_class_ids = {e.class_id for e in approved_enrollments}

    if class_id:
        if class_id not in approved_class_ids:
            raise HTTPException(status_code=403, detail="Not enrolled in this class")
        exams = db.query(Exam).filter(Exam.class_id == class_id).all()
    else:
        if not approved_class_ids:
            return []
        exams = db.query(Exam).filter(Exam.class_id.in_(approved_class_ids)).all()

    return [
        {
            "exam_id": e.id,
            "class_id": e.class_id,
            "title": e.title,
            "description": e.description,
            "status": e.status,
            "duration_minutes": e.duration_minutes,
            "scheduled_start": e.scheduled_start,
            "scheduled_end": e.scheduled_end,
        }
        for e in exams
    ]


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

    exam.status = req.status
    db.commit()
    return {
        "exam_id": exam_id,
        "new_status": req.status.value if hasattr(req.status, "value") else str(req.status),
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

    questions = db.query(Question).filter(
        Question.exam_id == exam_id
    ).order_by(Question.order_index).all()

    is_examiner = (current_user.role) == Role.EXAMINER

    return [
        {
            "question_id": q.id,
            "order_index": q.order_index,
            "question_type": q.question_type,
            "text": q.text,
            "marks": q.marks,
            "options": q.options,
            "correct_option": q.correct_option if is_examiner else None,
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
