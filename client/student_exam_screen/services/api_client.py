from __future__ import annotations

from typing import Any

import requests


class StudentExamApiClient:
    """
    REST API client for the student exam screen.

    Important:
    - This class only organizes HTTP calls.
    - It does NOT make calls off-thread by itself.
    - Use ApiWorker when calling these methods from ExamWindow.
    """

    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    @staticmethod
    def _extract_http_error(response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return f"Request failed with status {response.status_code}."

        detail = data.get("detail")

        if isinstance(detail, str) and detail.strip():
            return detail

        if isinstance(detail, list) and detail:
            first = detail[0]
            if isinstance(first, dict) and first.get("msg"):
                return str(first["msg"])

        return f"Request failed with status {response.status_code}."

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"

        extra_headers = kwargs.pop("headers", None) or {}
        headers = self._headers()
        headers.update(extra_headers)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=kwargs.pop("timeout", 15),
                **kwargs,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Network request failed: {exc}") from exc

        if response.status_code >= 400:
            raise RuntimeError(self._extract_http_error(response))

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

    # ─────────────────────────────────────────────
    # Exam launch
    # ─────────────────────────────────────────────

    def start_session(self, exam_id: str) -> dict:
        return self._request(
            "POST",
            "/sessions/start",
            json={"exam_id": exam_id},
        )

    def get_exam(self, exam_id: str) -> dict:
        return self._request(
            "GET",
            f"/exams/{exam_id}",
        )

    def get_questions(self, exam_id: str) -> list[dict]:
        return self._request(
            "GET",
            f"/exams/{exam_id}/questions",
        )

    def prepare_exam_launch(self, exam_id: str) -> dict:
        session = self.start_session(exam_id)
        exam = self.get_exam(exam_id)
        questions = self.get_questions(exam_id)

        return {
            "session": session,
            "exam": exam,
            "questions": questions,
        }

    # ─────────────────────────────────────────────
    # Active exam lifecycle
    # ─────────────────────────────────────────────

    def activate_session(self, session_id: str) -> dict:
        return self._request(
            "POST",
            f"/sessions/{session_id}/activate",
            timeout=10,
        )

    def verify_face(self, image_bytes: bytes) -> dict:
        return self._request(
            "POST",
            "/auth/verify-face",
            files={
                "image": (
                    "entry_verify.jpg",
                    image_bytes,
                    "image/jpeg",
                )
            },
            timeout=12,
        )

    def finalize_session(self, session_id: str, payload: dict) -> dict:
        return self._request(
            "POST",
            f"/sessions/{session_id}/finalize",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )