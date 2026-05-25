from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    tone: str
    chip_text: str
    chip_is_live: bool
    value: str
    title: str
    icon: str


@dataclass(frozen=True)
class ExamRowSpec:
    exam_id: str
    exam_name: str
    join_code: str
    status: str
    duration: str
    students: str
    avatar_count: int = 0


@dataclass(frozen=True)
class AlertSpec:
    severity: str
    title: str
    body: str
    age: str
    action_primary: str
    action_secondary: str = ""
