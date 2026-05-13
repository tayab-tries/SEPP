"""
client/modules/auth/signup_window.py

Signup controller — uses POST /auth/register-with-face atomic endpoint.
Single request: creates account + enrolls face together.
If face not detected server rejects — no orphaned accounts.
"""

import cv2
import logging
import requests
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QThread

from client.config import BASE_URL
from client.modules.auth.ui.signup_ui import SignupUI

logger = logging.getLogger(__name__)


def _frame_has_face(frame) -> bool:
    """Fast local check to avoid uploading photos with no visible face."""
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if cascade.empty():
            return True  # fail-open if detector is unavailable
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
        )
        return len(faces) > 0
    except Exception:
        return True  # fail-open; server-side check remains authoritative


class _RegisterWorker(QThread):
    """
    Single POST /auth/register-with-face call.
    Sends all registration data + face image as multipart form.
    Runs off main thread — spinner stays animated.
    """

    success = Signal(str, str)   # user_id, token
    error   = Signal(str)

    def __init__(self, fields: dict, frame, base_url: str):
        super().__init__()
        self._fields   = fields
        self._frame    = frame
        self._base_url = base_url

    def run(self):
        # Encode frame to JPEG
        success, buffer = cv2.imencode(".jpg", self._frame)
        if not success:
            self.error.emit("Failed to process photo.")
            return

        try:
            resp = requests.post(
                f"{self._base_url}/auth/register-with-face",
                data=self._fields,   # form fields
                files={"image": ("enroll.jpg", buffer.tobytes(), "image/jpeg")},
                timeout=20,
            )
        except requests.ConnectionError:
            self.error.emit("Cannot connect to server.")
            return
        except requests.Timeout:
            self.error.emit("Server not responding.")
            return
        except Exception as e:
            self.error.emit("Unexpected error.")
            logger.error("Register-with-face error: %s", e)
            return

        if resp.status_code == 201:
            data = resp.json()
            logger.info("Register+enroll OK — user_id: %s", data["user_id"])
            self.success.emit(data["user_id"], data["access_token"])
        elif resp.status_code == 409:
            self.error.emit("Email already registered. Try logging in.")
        elif resp.status_code == 422:
            detail = resp.json().get("detail", "Face not detected.")
            self.error.emit(detail)
        else:
            detail = resp.json().get("detail", "Registration failed.")
            self.error.emit(detail)


class SignupWindow(QObject):

    signup_complete = Signal()

    def __init__(self, ui: Optional[SignupUI] = None):
        super().__init__()
        self._step1_data: dict = {}
        self._step2_data: dict = {}
        self._worker: Optional[_RegisterWorker] = None

        if ui is not None:
            self._ui = ui
            self._ui.step1_completed.connect(self._on_step1_completed)
            self._ui.step2_completed.connect(self._on_step2_completed)
            self._ui.enroll_requested.connect(self._on_enroll_requested)

    def reset(self):
        """Reset all state — called when navigating to signup."""
        self._step1_data = {}
        self._step2_data = {}
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(1000)
        self._worker = None
        self._ui.reset()

    @Slot(dict)
    def _on_step1_completed(self, data: dict):
        self._step1_data = data
        self._ui.go_to_step2(data["role"])

    @Slot(dict)
    def _on_step2_completed(self, data: dict):
        self._step2_data = data
        self._ui.set_status("Almost there — take a photo to complete.", "")
        self._ui.go_to_step3()

    @Slot()
    def _on_enroll_requested(self):
        frame = self._ui.get_captured_frame()
        if frame is None:
            self._ui.set_status("Please capture a photo first.", "error")
            return
        if not _frame_has_face(frame):
            self._ui.set_status("No clear face detected. Please retake your photo.", "error")
            return

        self._ui.set_status("Creating your account...", "loading")
        self._ui.show_spinner()

        # All fields sent as multipart form data alongside the image
        fields = {
            "email":       self._step1_data["email"],
            "first_name":  self._step1_data["first_name"],
            "last_name":   self._step1_data["last_name"],
            "password":    self._step1_data["password"],
            "role":        self._step1_data["role"],
            "institution": self._step2_data.get("institution", ""),
            "department":  self._step2_data.get("department", ""),
            "subject":     self._step2_data.get("subject", ""),
        }

        self._worker = _RegisterWorker(fields, frame, BASE_URL)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @Slot(str, str)
    def _on_success(self, user_id: str, token: str):
        self._ui.hide_spinner()
        self._ui.set_status("✓ Registration complete! Redirecting to login...", "success")
        QTimer.singleShot(1800, self.signup_complete.emit)

    @Slot(str)
    def _on_error(self, message: str):
        self._ui.hide_spinner()
        self._ui.set_status(message, "error")