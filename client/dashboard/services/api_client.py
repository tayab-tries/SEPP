"""
SEPP API Client
===============
All methods return stubbed data that mirrors the exact JSON shape
your FastAPI backend should return.  To wire up real endpoints:

  1. pip install requests
  2. Replace each stub body with the commented-out HTTP call.
  3. Set the SEPP_API_URL environment variable (default: http://localhost:8000).
  4. Set SEPP_AUTH_TOKEN for Bearer-token auth.
"""

from __future__ import annotations

import os
import requests

from client.dashboard.dashboard_utils import (
    format_exam_payload,
    format_result_payload,
)

from client.config import BASE_URL


class ApiClient:
    """Thin HTTP client for the SEPP FastAPI backend."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.token = ""

        env_token = os.environ.get("SEPP_AUTH_TOKEN", "").strip()
        if env_token:
            self.set_token(env_token)

# ── Helpers ───────────────────────────────────────────────────────────
    def _get(self, path: str, params: dict | None = None):
        url = f"{BASE_URL}{path}"

        try:
            response = self.session.get(
                url,
                headers=self._auth(),
                params=params,
                timeout=15,
            )
            response.raise_for_status()

            if not response.content:
                return None

            return response.json()

        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"API unavailable: {exc}") from exc
    
    # ── Exams ─────────────────────────────────────────────────────────────

    def get_next_exam(self) -> dict | None:
        """
        GET /exams/next
        Returns the next scheduled exam for the authenticated student,
        or None if no exam is imminent.

        Expected response shape:
            {
                "id":               str,
                "course_code":      str,
                "title":            str,
                "description":      str,
                "start_time":       str,   # ISO-8601
                "duration_minutes": int,
                "exam_type":        str    # "Proctored" | "Open Book" | …
            }
        """
        data = self._get("/exams/next")
        
        if not data:
            return None

        return format_exam_payload(data)

    def get_upcoming_assessments(self, limit: int = 5) -> list[dict]:
        """
        GET /exams/upcoming

        Returns upcoming assessments for the authenticated student,
        sorted by start time ascending.

        Backend should return:
            [
                {
                    "id": str,
                    "course_code": str,      # mapped from Class.join_code
                    "title": str,
                    "description": str | None,
                    "start_time": str | None,  # ISO-8601
                    "end_time": str | None,    # ISO-8601
                    "duration_minutes": int,
                    "exam_type": str           # "Proctored" or "Open Book"
                }
            ]

        The PySide6 client will format month/day/time from start_time.
        """
        data = self._get("/exams/upcoming", params={"limit": limit}) or []

        return [format_exam_payload(item) for item in data]
    
    # ── Results ───────────────────────────────────────────────────────────

    def get_recent_results(self, limit: int = 5) -> list[dict]:
        """
        GET /results/recent

        Returns the authenticated student's most recent submitted results.

        Backend should return:
            [
                {
                    "session_id": str,
                    "exam_id": str,
                    "course_code": str,       # mapped from Class.join_code
                    "title": str,
                    "submitted_at": str | None,  # ISO-8601
                    "mcq_score": float | None,
                    "essay_score": float | None,
                    "total_score": float,
                    "integrity_score": float | None,
                    "status": str
                }
            ]

        The current dashboard can display only title/name and date,
        but we keep the full score fields available for future UI use.
        """
        data = self._get("/results/recent", params={"limit": limit}) or []
        return [format_result_payload(item) for item in data]

    # ── System status ─────────────────────────────────────────────────────

    def get_system_status(self) -> dict:
        """
        Stubbed for now.
        No backend /system/status route required yet.
        """
        return {
            "camera": {
                "active": True,
                "label": "Active",
            },
            "network": {
                "stable": True,
                "latency_ms": 24,
                "label": "Stable",
            },
            "last_scan": "2 minutes ago",
        }
    # ── Student ───────────────────────────────────────────────────────────

    def get_student_info(self) -> dict:
        try:
            data = self._get("/auth/me")
        except Exception:
            return {
                "name": "Student",
                "system_safe": True,
                "identity_verified": True,
            }

        if not data:
            return {
                "name": "Student",
                "system_safe": True,
                "identity_verified": True,
            }

        return {
            "name": data.get("full_name") or data.get("name") or "Student",
            "system_safe": True,
            "identity_verified": bool(data.get("face_enrolled", False)),
        }

    # ── Helpers ───────────────────────────────────────────────────────────

    def _auth(self) -> dict:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def set_token(self, token: str) -> None:
        token = (token or "").replace("Bearer ", "").strip()
        self.token = token

        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
        else:
            self.session.headers.pop("Authorization", None)
            
    def clear_token(self) -> None:
        self.set_token("")
