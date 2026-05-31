import os
import requests

from client.config import BASE_URL


class ReviewApiClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.token = ""

        env_token = os.environ.get("SEPP_AUTH_TOKEN", "").strip()
        if env_token:
            self.set_token(env_token)

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

    def fetch_review_data(self, session_id: str) -> dict:
        """
        Fetches session details, exam metadata, questions, and answers for the review view.
        """
        try:
            # 1. Fetch Session
            session_resp = self.session.get(f"{BASE_URL}/sessions/{session_id}", headers=self._auth(), timeout=10)
            session_resp.raise_for_status()
            session_data = session_resp.json()
            
            exam_id = session_data.get("exam_id")
            if not exam_id:
                raise ValueError("Session data missing exam_id")

            # 2. Fetch Exam
            exam_resp = self.session.get(f"{BASE_URL}/exams/{exam_id}", headers=self._auth(), timeout=10)
            exam_resp.raise_for_status()
            exam_data = exam_resp.json()

            # 3. Fetch Questions
            q_resp = self.session.get(f"{BASE_URL}/exams/{exam_id}/questions", headers=self._auth(), timeout=10)
            q_resp.raise_for_status()
            questions_data = q_resp.json()

            # 4. Fetch Answers
            ans_resp = self.session.get(f"{BASE_URL}/sessions/{session_id}/answers", headers=self._auth(), timeout=10)
            ans_resp.raise_for_status()
            answers_data = ans_resp.json()

            return {
                "session": session_data,
                "exam": exam_data,
                "questions": questions_data,
                "answers": answers_data,
            }

        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Review API unavailable: {exc}") from exc
