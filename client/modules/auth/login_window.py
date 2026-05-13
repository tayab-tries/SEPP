"""
client/modules/auth/login_window.py
Login controller — pure logic, no UI ownership.
"""

import logging
import requests

from PySide6.QtCore import QObject, Signal, Slot, QThread

from client.config import BASE_URL
from client.modules.auth.ui.login_ui import LoginUI

from typing import Optional

logger = logging.getLogger(__name__)


class _LoginWorker(QThread):
    """Single POST /auth/login call, off the GUI thread."""

    success    = Signal(dict)
    http_error = Signal(int)   # non-200 status code
    net_error  = Signal(str)   # "connection" | "timeout" | raw exc string

    def __init__(self, email: str, password: str):
        super().__init__()
        self._email    = email
        self._password = password

    def run(self):
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/login",
                data={"username": self._email, "password": self._password},
                timeout=10,
            )
            if resp.status_code == 200:
                self.success.emit(resp.json())
            else:
                self.http_error.emit(resp.status_code)
        except requests.ConnectionError:
            self.net_error.emit("connection")
        except requests.Timeout:
            self.net_error.emit("timeout")
        except Exception as exc:  # noqa: BLE001
            self.net_error.emit(str(exc))


class LoginWindow(QObject):

    login_successful = Signal(str, str, str, str, bool)

    def __init__(self, ui: Optional[LoginUI] = None):
        super().__init__()
        self._worker: Optional[_LoginWorker] = None
        if ui is not None:
            self._ui = ui
            self._ui.login_requested.connect(self._on_login_requested)

    @Slot(str, str)
    def _on_login_requested(self, email: str, password: str):
        if self._worker and self._worker.isRunning():
            return  # ignore double-submit while in flight
        self._ui.set_status("Signing in...", "loading")
        self._ui.set_loading(True)

        self._worker = _LoginWorker(email, password)
        self._worker.success.connect(self._on_success)
        self._worker.http_error.connect(self._on_http_error)
        self._worker.net_error.connect(self._on_net_error)
        self._worker.start()

    @Slot(dict)
    def _on_success(self, data: dict):
        logger.info("Login OK — role: %s", data.get("role"))
        self._ui.set_loading(False)
        self._ui.set_status("✓ Login successful", "success")
        self.login_successful.emit(
            data["access_token"],
            data["role"],
            data["user_id"],
            data["full_name"],
            data["face_enrolled"],
        )

    @Slot(int)
    def _on_http_error(self, status_code: int):
        self._ui.set_loading(False)
        if status_code == 401:
            self._ui.set_status("Invalid email or password.", "error")
        else:
            self._ui.set_status(f"Server error ({status_code}). Try again.", "error")

    @Slot(str)
    def _on_net_error(self, kind: str):
        self._ui.set_loading(False)
        if kind == "connection":
            self._ui.set_status("Cannot connect to server.", "error")
        elif kind == "timeout":
            self._ui.set_status("Server not responding. Try again.", "error")
        else:
            logger.error("Login error: %s", kind)
            self._ui.set_status("Unexpected error.", "error")
