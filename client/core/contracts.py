"""
Contract adapters for backend payload normalization.
"""

from __future__ import annotations

from typing import Iterable


def resolve_id(payload: dict, *keys: str) -> str:
    """
    Resolve canonical id from a payload using preferred keys first.
    Always falls back to `id`.
    """
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    value = payload.get("id")
    if value:
        return str(value)
    joined = ", ".join(keys) if keys else "id"
    raise ValueError(f"Missing id in payload (expected one of: {joined}, id)")


def resolve_optional_id(payload: dict, *keys: str) -> str | None:
    try:
        return resolve_id(payload, *keys)
    except ValueError:
        return None


def normalize_exam_payload(raw: dict) -> dict:
    exam = dict(raw or {})
    exam["exam_id"] = resolve_id(exam, "exam_id")
    exam.setdefault("id", exam["exam_id"])
    return exam


def normalize_class_payload(raw: dict) -> dict:
    klass = dict(raw or {})
    class_id = resolve_optional_id(klass, "class_id")
    if class_id:
        klass["class_id"] = class_id
        klass.setdefault("id", class_id)
    return klass


def normalize_session_payload(raw: dict) -> dict:
    session = dict(raw or {})
    session["session_id"] = resolve_id(session, "session_id")
    session.setdefault("id", session["session_id"])
    exam_id = resolve_optional_id(session, "exam_id")
    if exam_id:
        session["exam_id"] = exam_id
    return session


def normalize_question_payload(raw: dict) -> dict:
    question = dict(raw or {})
    question["id"] = resolve_id(question, "question_id")
    question.setdefault("question_id", question["id"])
    return question


def normalize_question_list(items: Iterable[dict]) -> list[dict]:
    return [normalize_question_payload(item) for item in items or []]


def resolve_student_name(payload: dict) -> str:
    """
    Modular resolver for student name/display from a session, event, or enrollment payload.
    """
    name = payload.get("student_name") or payload.get("full_name") or payload.get("name")
    if name:
        return str(name)
    student_id = payload.get("student_id")
    if student_id:
        student_id_str = str(student_id)
        return student_id_str[:12] + "..." if len(student_id_str) > 12 else student_id_str
    return "Student"
