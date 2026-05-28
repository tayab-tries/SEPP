import logging
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from client.reports.services.api_client import ReportsApiClient

logger = logging.getLogger(__name__)

class ReportsApiWorker(QObject):
    """
    QObject to handle async API calls for the Reports page.
    """
    performance_fetched = Signal(dict)
    history_fetched = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, api_client: ReportsApiClient) -> None:
        super().__init__()
        self._api = api_client

    def fetch_data(self) -> None:
        """Fetch both performance and history data."""
        try:
            perf_data = self._api.get_my_performance()
            self.performance_fetched.emit(perf_data)
            
            hist_data = self._api.get_my_history()
            self.history_fetched.emit(hist_data)
        except Exception as e:
            logger.exception("ReportsApiWorker fetch failed")
            self.error_occurred.emit(str(e))
