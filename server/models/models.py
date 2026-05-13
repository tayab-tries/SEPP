"""
server/models/models.py
Database models — all tables defined here.
Run `alembic revision --autogenerate` after any changes.

Uses SQLAlchemy 2.0 Mapped[] annotations throughout so Pylance
correctly infers Python types from ORM columns.
"""

import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from server.database import Base
from shared.constants import (
    Role, ExamStatus, SessionStatus,
    QuestionType, EventType, EventSeverity,
)


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:               Mapped[str]           = mapped_column(String, primary_key=True, default=gen_uuid)
    email:            Mapped[str]           = mapped_column(String, unique=True, nullable=False, index=True)

    # Split name
    first_name:       Mapped[str]           = mapped_column(String, nullable=False)
    last_name:        Mapped[str]           = mapped_column(String, nullable=False)

    hashed_password:  Mapped[str]           = mapped_column(String, nullable=False)
    role:             Mapped[Role]          = mapped_column(SAEnum(Role), nullable=False)
    is_active:        Mapped[bool]          = mapped_column(Boolean, default=True)

    # Profile — both roles
    institution:      Mapped[Optional[str]] = mapped_column(String, nullable=True)
    department:       Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Face
    face_enrolled:    Mapped[bool]          = mapped_column(Boolean, default=False)
    face_embedding:   Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    created_at:       Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    enrollments   = relationship("Enrollment",  back_populates="student")
    exam_sessions = relationship("ExamSession", back_populates="student")
    created_exams = relationship("Exam",        back_populates="creator")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

# ──────────────────────────────────────────────────────────────────
# Classes (Exam Rooms)
# ──────────────────────────────────────────────────────────────────

class Class(Base):
    __tablename__ = "classes"

    id:          Mapped[str]           = mapped_column(String, primary_key=True, default=gen_uuid)
    name:        Mapped[str]           = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    join_code:   Mapped[str]           = mapped_column(String, unique=True, nullable=False)
    creator_id:  Mapped[str]           = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at:  Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    creator     = relationship("User")
    enrollments = relationship("Enrollment", back_populates="class_")
    exams       = relationship("Exam",       back_populates="class_")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id:          Mapped[str]      = mapped_column(String, primary_key=True, default=gen_uuid)
    student_id:  Mapped[str]      = mapped_column(String, ForeignKey("users.id"),    nullable=False)
    class_id:    Mapped[str]      = mapped_column(String, ForeignKey("classes.id"),  nullable=False)
    approved:    Mapped[bool]     = mapped_column(Boolean, default=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student = relationship("User",  back_populates="enrollments")
    class_  = relationship("Class", back_populates="enrollments")


# ──────────────────────────────────────────────────────────────────
# Exams
# ──────────────────────────────────────────────────────────────────

class Exam(Base):
    __tablename__ = "exams"

    id:                          Mapped[str]            = mapped_column(String, primary_key=True, default=gen_uuid)
    class_id:                    Mapped[str]            = mapped_column(String, ForeignKey("classes.id"),  nullable=False)
    creator_id:                  Mapped[str]            = mapped_column(String, ForeignKey("users.id"),    nullable=False)
    title:                       Mapped[str]            = mapped_column(String, nullable=False)
    description:                 Mapped[Optional[str]]  = mapped_column(Text,   nullable=True)
    status:                      Mapped[ExamStatus]     = mapped_column(SAEnum(ExamStatus), default=ExamStatus.DRAFT)
    duration_minutes:            Mapped[int]            = mapped_column(Integer, nullable=False)
    scheduled_start:             Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_end:               Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Proctoring config
    max_window_switches:         Mapped[int]  = mapped_column(Integer, default=3)
    max_face_absent_seconds:     Mapped[int]  = mapped_column(Integer, default=10)
    allow_paste_in_essay:        Mapped[bool] = mapped_column(Boolean, default=False)
    require_liveness_check:      Mapped[bool] = mapped_column(Boolean, default=True)
    face_recheck_interval_minutes: Mapped[int] = mapped_column(Integer, default=5)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    class_    = relationship("Class", back_populates="exams")
    creator   = relationship("User",  back_populates="created_exams")
    questions = relationship("Question",    back_populates="exam", order_by="Question.order_index")
    sessions  = relationship("ExamSession", back_populates="exam")


class Question(Base):
    __tablename__ = "questions"

    id:            Mapped[str]           = mapped_column(String, primary_key=True, default=gen_uuid)
    exam_id:       Mapped[str]           = mapped_column(String, ForeignKey("exams.id"), nullable=False)
    order_index:   Mapped[int]           = mapped_column(Integer, nullable=False)
    question_type: Mapped[QuestionType]  = mapped_column(SAEnum(QuestionType), nullable=False)
    text:          Mapped[str]           = mapped_column(Text,    nullable=False)
    marks:         Mapped[float]         = mapped_column(Float,   default=1.0)

    # MCQ
    options:        Mapped[Optional[Any]] = mapped_column(JSON,   nullable=True)  # ["A", "B", "C", "D"]
    correct_option: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "A"

    # Essay
    max_words: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_words: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    exam = relationship("Exam", back_populates="questions")


# ──────────────────────────────────────────────────────────────────
# Exam Sessions
# ──────────────────────────────────────────────────────────────────

class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id:         Mapped[str]           = mapped_column(String, primary_key=True, default=gen_uuid)
    exam_id:    Mapped[str]           = mapped_column(String, ForeignKey("exams.id"),  nullable=False)
    student_id: Mapped[str]           = mapped_column(String, ForeignKey("users.id"),  nullable=False)
    status:     Mapped[SessionStatus] = mapped_column(SAEnum(SessionStatus), default=SessionStatus.PENDING)

    started_at:        Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_at:      Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    terminated_at:     Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    termination_reason: Mapped[Optional[str]]     = mapped_column(String,   nullable=True)

    # Clock reconciliation
    last_heartbeat_at:          Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_heartbeat_client_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Scores
    mcq_score:       Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    essay_score:     Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    integrity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    exam    = relationship("Exam", back_populates="sessions")
    student = relationship("User", back_populates="exam_sessions")
    answers = relationship("Answer",         back_populates="session")
    events  = relationship("ProctoringEvent", back_populates="session")


# ──────────────────────────────────────────────────────────────────
# Answers
# ──────────────────────────────────────────────────────────────────

class Answer(Base):
    __tablename__ = "answers"

    id:              Mapped[str]           = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id:      Mapped[str]           = mapped_column(String, ForeignKey("exam_sessions.id"), nullable=False)
    question_id:     Mapped[str]           = mapped_column(String, ForeignKey("questions.id"),     nullable=False)
    answer_text:     Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    selected_option: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_correct:      Mapped[Optional[bool]]  = mapped_column(Boolean, nullable=True)
    examiner_score:  Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    examiner_comment: Mapped[Optional[str]]  = mapped_column(Text,    nullable=True)
    last_updated_at: Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session  = relationship("ExamSession", back_populates="answers")
    question = relationship("Question")


# ──────────────────────────────────────────────────────────────────
# Proctoring Events
# ──────────────────────────────────────────────────────────────────

class ProctoringEvent(Base):
    __tablename__ = "proctoring_events"

    id:               Mapped[str]           = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id:       Mapped[str]           = mapped_column(String, ForeignKey("exam_sessions.id"), nullable=False)
    event_type:       Mapped[EventType]     = mapped_column(SAEnum(EventType),     nullable=False)
    severity:         Mapped[EventSeverity] = mapped_column(SAEnum(EventSeverity), nullable=False)
    timestamp:        Mapped[datetime]      = mapped_column(DateTime, nullable=False)
    server_received_at: Mapped[datetime]    = mapped_column(DateTime, default=datetime.utcnow)
    metadata_:        Mapped[Optional[Any]] = mapped_column("metadata", JSON, nullable=True)
    snapshot_path:    Mapped[Optional[str]] = mapped_column(String, nullable=True)
    examiner_note:    Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    dismissed:        Mapped[bool]          = mapped_column(Boolean, default=False)
    chain_hash:       Mapped[Optional[str]] = mapped_column(String, nullable=True)

    session = relationship("ExamSession", back_populates="events")
