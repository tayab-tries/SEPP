"""
client/exam/services/api_client.py

Synchronous API client for the Exams page.

Important:
- This class does NOT use QThread directly.
- ExamsPage runs these blocking methods through ApiWorker.
- ApiClient only handles:
    1. HTTP requests
    2. Auth headers
    3. Error parsing
    4. Mapping backend JSON into widget-friendly dicts
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import requests


class ApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        access_token: Optional[str] = None,
        timeout: int = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout

    # ─────────────────────────────────────────────────────────────
    # Auth
    # ─────────────────────────────────────────────────────────────

    def set_access_token(self, access_token: str) -> None:
        """
        Set or replace the JWT token after login/register.
        """
        self.access_token = access_token

    def clear_access_token(self) -> None:
        self.access_token = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
        }

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    # ─────────────────────────────────────────────────────────────
    # Low-level request helper
    # ─────────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not connect to server: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(self._extract_error_message(response))

        if response.status_code == 204:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("Server returned an invalid JSON response.") from exc

    def _extract_error_message(self, response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return f"Request failed with status {response.status_code}."

        detail = data.get("detail")

        if isinstance(detail, str):
            return detail

        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict):
                msg = first.get("msg")
                if msg:
                    return str(msg)

        return f"Request failed with status {response.status_code}."

    # ─────────────────────────────────────────────────────────────
    # Exams page methods expected by ExamsPage
    # ─────────────────────────────────────────────────────────────

    def get_upcoming_exams(self) -> list[dict]:
        """
        Called by ExamsPage._load_page_data().

        Backend route:
            GET /exams/upcoming

        Returns widget-ready data for UpcomingExamsPanel / ExamCardWidget.
        """
        rows = self._request("GET", "/exams/upcoming")

        if not isinstance(rows, list):
            raise RuntimeError("Unexpected upcoming exams response.")

        return [self._map_exam(row) for row in rows]

    def get_pending_requests(self) -> list[dict]:
        """
        Called by ExamsPage._load_page_data().

        Backend route:
            GET /exams/access-requests/me

        Returns widget-ready data for PendingRequestsPanel.
        """
        rows = self._request("GET", "/exams/access-requests/me")

        if not isinstance(rows, list):
            raise RuntimeError("Unexpected pending requests response.")

        return [self._map_access_request(row) for row in rows]

    def get_recent_results(self, limit: int = 5) -> list[dict]:
        """
        Called by ExamsPage._load_page_data() for the RecentResults widget.

        Backend route:
            GET /results/recent
        """
        rows = self._request("GET", "/results/recent", params={"limit": limit}) or []

        if not isinstance(rows, list):
            raise RuntimeError("Unexpected recent attempts response.")

        return [self._map_recent_result(row) for row in rows]

    def submit_access_code(self, code: str) -> dict:
        """
        Called when student submits exam join code.

        Backend route:
            POST /exams/join-by-code/{code}

        Returns one widget-ready pending request dict.
        """
        clean_code = code.strip().upper()

        if not clean_code:
            raise RuntimeError("Please enter an access code.")

        encoded_code = quote(clean_code, safe="")
        row = self._request("POST", f"/exams/join-by-code/{encoded_code}")

        if not isinstance(row, dict):
            raise RuntimeError("Unexpected join exam response.")

        return self._map_access_request(row)

    def cancel_request(self, request_id: str) -> dict:
        """
        Called when student cancels their own pending exam access request.

        Backend route:
            DELETE /exams/access-requests/{request_id}
        """
        clean_id = request_id.strip()

        if not clean_id:
            raise RuntimeError("Missing request id.")

        encoded_id = quote(clean_id, safe="")
        row = self._request("DELETE", f"/exams/access-requests/{encoded_id}")

        if isinstance(row, dict):
            return row

        return {"request_id": request_id, "message": "Request cancelled."}

    # ─────────────────────────────────────────────────────────────
    # Optional useful methods for later
    # ─────────────────────────────────────────────────────────────

    def get_exam_details(self, exam_id: str) -> dict:
        """
        Optional helper for later pages/dialogs.

        Backend route:
            GET /exams/{exam_id}
        """
        encoded_id = quote(exam_id.strip(), safe="")
        row = self._request("GET", f"/exams/{encoded_id}")

        if not isinstance(row, dict):
            raise RuntimeError("Unexpected exam details response.")

        return row

    def start_session(self, exam_id: str) -> dict:
        """
        Optional helper for check-in/start exam flow.

        Backend route:
            POST /sessions/start
        """
        return self._request(
            "POST",
            "/sessions/start",
            json={"exam_id": exam_id},
        )

    # ─────────────────────────────────────────────────────────────
    # Mapping helpers: backend JSON → widget dicts
    # ─────────────────────────────────────────────────────────────

    def _map_exam(self, row: dict[str, Any]) -> dict:
        """
        ExamCardWidget expects:
            exam_id
            title
            date
            duration_mins
            face_id_required
            check_in_open

        ViewDetailsDialog also benefits from:
            start_time
            examiner_name
            duration_mins
        """
        exam_id = str(row.get("exam_id") or row.get("id") or "")
        title = str(row.get("title") or "Untitled Exam")

        start_raw = (
            row.get("start_time")
            or row.get("scheduled_start")
            or row.get("scheduledStart")
        )

        end_raw = (
            row.get("end_time")
            or row.get("scheduled_end")
            or row.get("scheduledEnd")
        )

        duration = (
            row.get("duration_mins")
            or row.get("duration_minutes")
            or row.get("duration")
            or 0
        )

        status = str(row.get("status") or "").upper()

        face_required = bool(
            row.get("face_id_required")
            if "face_id_required" in row
            else row.get("require_liveness_check", True)
        )

        check_in_open = bool(
            row.get("check_in_open")
            if "check_in_open" in row
            else status == "LIVE"
        )

        return {
            # Required by ExamCardWidget
            "exam_id": exam_id,
            "title": title,
            "date": self._format_short_datetime(start_raw),
            "duration_mins": int(duration or 0),
            "face_id_required": face_required,
            "check_in_open": check_in_open,

            # Used by ViewDetailsDialog cache
            "start_time": self._format_long_datetime(start_raw),
            "end_time": self._format_long_datetime(end_raw),
            "examiner_name": str(row.get("examiner_name") or row.get("creator_name") or "—"),

            # Keep useful raw/backend fields too
            "class_id": row.get("class_id"),
            "description": row.get("description"),
            "status": row.get("status"),
            "exam_type": row.get("exam_type"),
            "raw": row,
        }

    def _map_access_request(self, row: dict[str, Any]) -> dict:
        """
        PendingRequestCard expects:
            request_id
            exam_name
            exam_id
            request_date
            status
        """
        request_id = str(
            row.get("request_id")
            or row.get("id")
            or row.get("access_request_id")
            or ""
        )

        exam_id = str(row.get("exam_id") or "")

        exam_name = str(
            row.get("exam_name")
            or row.get("exam_title")
            or row.get("title")
            or "Unknown Exam"
        )

        requested_raw = (
            row.get("request_date")
            or row.get("requested_at")
            or row.get("created_at")
        )

        approved = bool(row.get("approved", False))

        status = str(
            row.get("status")
            or ("Approved" if approved else "Awaiting Approval")
        )

        return {
            "request_id": request_id,
            "exam_name": exam_name,
            "exam_id": exam_id,
            "request_date": self._format_date(requested_raw),
            "status": status,

            # Keep useful raw/backend fields too
            "approved": approved,
            "requested_at": requested_raw,
            "raw": row,
        }

    def _map_recent_result(self, row: dict[str, Any]) -> dict:
        submitted_raw = (
            row.get("submitted_at")
            or row.get("created_at")
        )
        
        status = str(row.get("status") or "UNKNOWN")
        if "." in status:
            status = status.split(".")[-1]
        status = status.replace("_", " ").upper()
        
        score_val = row.get("total_score")
        if score_val is None:
            score = 0
        else:
            try:
                score = int(round(float(score_val)))
            except (TypeError, ValueError):
                score = 0

        return {
            "title": str(row.get("title") or row.get("exam_name") or "Unknown Exam"),
            "date": self._format_date(submitted_raw).upper() if submitted_raw else "TBA",
            "score": score,
            "status": status,
            "status_label": status,
            "is_graded": row.get("is_graded", True),
            "raw": row,
        }

    # ─────────────────────────────────────────────────────────────
    # Date formatting helpers
    # ─────────────────────────────────────────────────────────────

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            return None

        text = value.strip()

        if not text:
            return None

        # FastAPI often returns ISO strings. Handle trailing Z too.
        text = text.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _format_short_datetime(self, value: Any) -> str:
        dt = self._parse_datetime(value)

        if dt is None:
            return "Not scheduled"

        return dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")

    def _format_long_datetime(self, value: Any) -> str:
        dt = self._parse_datetime(value)

        if dt is None:
            return "Not scheduled"

        return dt.strftime("%b %d, %Y at %I:%M %p").replace(" 0", " ")

    def _format_date(self, value: Any) -> str:
        dt = self._parse_datetime(value)

        if dt is None:
            return "—"

        return dt.strftime("%b %d, %Y").replace(" 0", " ")