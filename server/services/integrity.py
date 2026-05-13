from __future__ import annotations

from sqlalchemy.orm import Session

from server.models.models import Answer, ExamSession, ProctoringEvent, Question
from shared.constants import EventSeverity, QuestionType


SEVERITY_PENALTIES = {
    EventSeverity.INFO: 0,
    EventSeverity.LOW: 2,
    EventSeverity.MEDIUM: 5,
    EventSeverity.HIGH: 15,
    EventSeverity.CRITICAL: 30,
}


def calculate_integrity_score(session_id: str, db: Session) -> float:
    events = db.query(ProctoringEvent).filter(ProctoringEvent.session_id == session_id).all()
    penalty = 0
    for event in events:
        penalty += SEVERITY_PENALTIES.get(event.severity, 0)
    return float(max(0, 100 - penalty))


def integrity_recommendation(score: float | None) -> str:
    if score is None:
        return "not_calculated"
    if score >= 85:
        return "clear"
    if score >= 60:
        return "review_recommended"
    return "high_risk_review_required"


def refresh_integrity_score(session_id: str, db: Session) -> float:
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        return 0.0
    score = calculate_integrity_score(session_id, db)
    session.integrity_score = score
    return score


def proctoring_event_counts(session_id: str, db: Session) -> dict[str, int]:
    events = db.query(ProctoringEvent).filter(ProctoringEvent.session_id == session_id).all()
    counts: dict[str, int] = {}
    for event in events:
        key = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        counts[key] = counts.get(key, 0) + 1
    return counts


def refresh_essay_score(session_id: str, db: Session) -> float:
    rows = (
        db.query(Answer, Question)
        .join(Question, Question.id == Answer.question_id)
        .filter(
            Answer.session_id == session_id,
            Question.question_type == QuestionType.ESSAY,
        )
        .all()
    )
    score = round(
        sum(float(answer.examiner_score or 0) for answer, _question in rows),
        2,
    )
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session:
        session.essay_score = score
    return score
