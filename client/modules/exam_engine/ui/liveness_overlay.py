"""
client/modules/exam_engine/ui/liveness_overlay.py

Liveness check overlay — shown during Phase 1 entry verification.
Pure UI component — zero logic, zero API calls.

Receives state via slots connected to ExamWindow signals:
    status_changed(str)   → update status text
    state_updated(str)    → "waiting" | "checking" | "passed" | "failed"
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap


class LivenessOverlay(QFrame):
    """
    Full-screen overlay displayed during liveness verification.
    Instructs the student what to do and shows live status.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("liveness_overlay")
        self._build_ui()
        self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addStretch()

        # Title
        self._title = QLabel("🔍 Identity Verification")
        self._title.setObjectName("liveness_title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Instructions
        self._instruction = QLabel(
            "Please look directly at the camera and follow the steps below:\n\n"
            "  1.  Blink naturally — twice\n"
            "  2.  Slowly turn your head left, then right\n\n"
            "Keep your face clearly visible and well lit."
        )
        self._instruction.setObjectName("liveness_instruction")
        self._instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._instruction.setWordWrap(True)
        layout.addWidget(self._instruction)

        self._preview = QLabel("Camera preview will appear here")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFixedSize(320, 240)
        self._preview.setStyleSheet("background-color: #111827; border: 1px solid #334155;")
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)

        # Live status
        self._status = QLabel("Starting camera...")
        self._status.setObjectName("liveness_status")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        layout.addStretch()

    # ── Slots connected from ExamWindow ───────────────────────────────────

    @Slot(str)
    def set_status(self, text: str):
        """Update the status line below the instructions."""
        self._status.setText(text)

    @Slot(bytes)
    def set_preview_frame(self, image_bytes: bytes):
        pixmap = QPixmap()
        if pixmap.loadFromData(image_bytes):
            self._preview.setPixmap(
                pixmap.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    @Slot(str)
    def set_state(self, state: str):
        """
        Update visual state.
        state: "waiting" | "checking" | "passed" | "failed"
        Drives QSS property selector [state="..."]
        """
        self._status.setProperty("state", state)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)

        if state == "passed":
            self._title.setText("✓ Verification Complete")
            self._instruction.setText("Identity confirmed. Starting your exam...")

        elif state == "failed":
            self._title.setText("❌ Verification Failed")
            self._instruction.setText(
                "Liveness check could not be completed.\n\n"
                "Please contact your examiner to proceed."
            )
