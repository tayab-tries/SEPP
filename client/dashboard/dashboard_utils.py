from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)

        # If backend sent timezone-aware datetime, convert to local naive
        # so it can be compared safely with datetime.now().
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)

        return dt
    except (TypeError, ValueError):
        return None


def format_month(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    return dt.strftime("%b").upper() if dt else "--"


def format_day(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    return dt.strftime("%d") if dt else "--"


def format_time(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    return dt.strftime("%I:%M %p").lstrip("0") if dt else "TBA"


def format_date(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    return dt.strftime("%b %d, %Y").upper() if dt else "TBA"


def format_datetime_label(value: str | None) -> str:
    dt = parse_iso_datetime(value)
    return dt.strftime("%b %d, %Y • %I:%M %p").replace(" 0", " ").upper() if dt else "TBA"


def format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "Duration TBA"

    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return "Duration TBA"

    if minutes <= 0:
        return "Duration TBA"

    if minutes < 60:
        return f"{minutes} min"

    hours = minutes // 60
    mins = minutes % 60

    if mins == 0:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"

    return f"{hours} hr {mins} min"


def normalize_status(value: Any) -> str:
    if value is None:
        return "UNKNOWN"

    text = str(value)

    if "." in text:
        text = text.split(".")[-1]

    return text.replace("_", " ").upper()


def format_score(value: Any) -> int:
    if value is None:
        return 0

    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def format_exam_payload(exam: dict) -> dict:
    start_time = exam.get("start_time") or exam.get("scheduled_start")

    return {
        **exam,

        # Old/current UI compatibility
        "month": format_month(start_time),
        "day": format_day(start_time),
        "time": format_time(start_time),

        # Better labels for new UI
        "date": format_date(start_time),
        "datetime_label": format_datetime_label(start_time),
        "duration_label": format_duration(exam.get("duration_minutes")),
        "status": normalize_status(exam.get("status")),
        "status_label": normalize_status(exam.get("status")),
    }


def format_result_payload(result: dict) -> dict:
    submitted_at = result.get("submitted_at")
    total_score = result.get("total_score")

    return {
        **result,

        # Current RecentResults expects these
        "date": format_date(submitted_at),
        "score": format_score(total_score),
        "status": normalize_status(result.get("status")),

        # Extra labels for future UI
        "datetime_label": format_datetime_label(submitted_at),
        "score_label": str(format_score(total_score)),
        "status_label": normalize_status(result.get("status")),
    }