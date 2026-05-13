"""
client/modules/exam_engine/ui/lockdown_overlay.py

Network lockdown overlay — shown when heartbeat connection is lost
or when exam is paused by the examiner.
Pure UI component — zero logic.

Receives state via slots connected to ExamWindow signals:
    lockdown_started()        → show overlay
    lockdown_ended()          → hide overlay
    lockdown_tick(int)        → update countdown
    lockdown_message(str)     → update message text (for pause vs disconnect)
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Slot


class LockdownOverlay(QFrame):
    """
    Full-screen overlay displayed during network lockdown or exam pause.
    Shows a countdown when in lockdown mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lockdown_overlay")
        self._build_ui()
        self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addStretch()

        # Title
        self._title = QLabel("⚠ Network Connection Lost")
        self._title.setObjectName("lockdown_title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Message
        self._message = QLabel(
            "Your answers are saved locally.\n"
            "Do NOT close this window.\n"
            "Attempting to reconnect..."
        )
        self._message.setObjectName("lockdown_message")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        # Countdown
        self._countdown = QLabel("")
        self._countdown.setObjectName("lockdown_countdown")
        self._countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._countdown)

        layout.addStretch()

    # ── Slots connected from ExamWindow ───────────────────────────────────

    @Slot()
    def show_lockdown(self):
        """Show overlay in network lockdown mode."""
        self._title.setText("⚠ Network Connection Lost")
        self._message.setText(
            "Your answers are saved locally.\n"
            "Do NOT close this window.\n"
            "Attempting to reconnect..."
        )
        self._countdown.setText("Session terminates in: 120s")
        self._countdown.setProperty("urgent", "false")
        self._refresh_style(self._countdown)
        self.show()
        self.raise_()

    @Slot()
    def show_paused(self):
        """Show overlay in exam-paused-by-examiner mode."""
        self._title.setText("⏸ Exam Paused")
        self._message.setText(
            "Your exam has been paused by the examiner.\n"
            "Please wait — do not close this window."
        )
        self._countdown.setText("")
        self.show()
        self.raise_()

    @Slot()
    def hide_overlay(self):
        self.hide()

    @Slot(int)
    def update_countdown(self, seconds_remaining: int):
        """Update the countdown label. Turns urgent red below 30s."""
        self._countdown.setText(f"Session terminates in: {seconds_remaining}s")

        urgent = "true" if seconds_remaining <= 30 else "false"
        self._countdown.setProperty("urgent", urgent)
        self._refresh_style(self._countdown)

    @Slot(str)
    def set_message(self, text: str):
        self._message.setText(text)

    # ── Helper ─────────────────────────────────────────────────────────────

    def _refresh_style(self, widget):
        """Force QSS property re-evaluation after property change."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)
