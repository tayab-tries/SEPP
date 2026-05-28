import logging
import requests

logger = logging.getLogger(__name__)

class ReportsApiClient:
    """Client for fetching data for the reports page."""

    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    def get_my_performance(self) -> dict:
        url = f"{self._base_url}/sessions/my-performance"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_my_history(self) -> list[dict]:
        url = f"{self._base_url}/sessions/my-history"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
