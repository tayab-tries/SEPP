from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────────────────────────
#  JoinExamWidget
#  "Join an Exam" card. Student enters an access code and submits.
#
#  Signals
#  -------
#  access_code_submitted(code: str)
#      Emitted when the user clicks "Request Access" with a non-empty field.
#      The page layer calls the API; result is pushed back via set_error / reset.
#
#  Public API
#  ----------
#  set_error(message)   — red border on input + inline error message
#  clear_error()        — removes red border and hides error label
#  set_loading()        — disables button and changes label while request is in flight
#  reset()              — clears field, hides error, re-enables button (call on success)
# ─────────────────────────────────────────────────────────────────────────────

EXAM_CARD_BG    = "#1a2d4e"
INPUT_BG        = "#253d5e"
CARD_RADIUS     = 10
ACCENT_YELLOW   = "#f0a500"
ACCENT_YELLOW_H = "#d99400"
ACCENT_RED      = "#ef4444"

# Normal and error stylesheet templates for the QLineEdit
_INPUT_NORMAL = f"""
    QLineEdit {{
        background: {INPUT_BG};
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 6px;
        padding: 0 12px;
        font-size: 13px;
    }}
    QLineEdit:focus {{
        border: 1px solid rgba(255, 255, 255, 0.40);
    }}
"""

_INPUT_ERROR = f"""
    QLineEdit {{
        background: {INPUT_BG};
        color: white;
        border: 1px solid {ACCENT_RED};
        border-radius: 6px;
        padding: 0 12px;
        font-size: 13px;
    }}
"""


class JoinExamWidget(QWidget):
    access_code_submitted = Signal(str)   # code string

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            JoinExamWidget {{
                background: {EXAM_CARD_BG};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 22)
        root.setSpacing(10)

        # Title
        title = QLabel("Join an Exam")
        title.setStyleSheet(
            "color: white; font-size: 15px; font-weight: 700; background: transparent;"
        )

        # Subtitle
        subtitle = QLabel(
            "Enter the access code provided by your institution "
            "to register for a new assessment."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            "color: rgba(255,255,255,0.60); font-size: 12px; background: transparent;"
        )

        # Field label
        code_label = QLabel("Access Code")
        code_label.setStyleSheet(
            "color: rgba(255,255,255,0.80); font-size: 12px; "
            "font-weight: 600; background: transparent;"
        )

        # Input
        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("EX-XXXXX-XXXX")
        self._code_input.setFixedHeight(40)
        self._code_input.setStyleSheet(_INPUT_NORMAL)
        self._code_input.textChanged.connect(self.clear_error)

        # Error label (hidden by default)
        self._error_lbl = QLabel()
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setStyleSheet(
            f"color: {ACCENT_RED}; font-size: 12px; background: transparent;"
        )
        self._error_lbl.hide()

        # Submit button
        self._submit_btn = QPushButton("Request Access  →")
        self._submit_btn.setFixedHeight(40)
        self._submit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._submit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_YELLOW};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover   {{ background: {ACCENT_YELLOW_H}; }}
            QPushButton:disabled {{
                background: #6b5c30;
                color: rgba(255,255,255,0.45);
            }}
        """)
        self._submit_btn.clicked.connect(self._on_submit)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addSpacing(6)
        root.addWidget(code_label)
        root.addWidget(self._code_input)
        root.addWidget(self._error_lbl)
        root.addSpacing(2)
        root.addWidget(self._submit_btn)

    # ── Private ───────────────────────────────────────────────────────────────

    def _on_submit(self) -> None:
        code = self._code_input.text().strip()
        if not code:
            self.set_error("Please enter an access code.")
            return
        self.access_code_submitted.emit(code)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_error(self, message: str) -> None:
        """Show a red border on the input and display an error message."""
        self._code_input.setStyleSheet(_INPUT_ERROR)
        self._error_lbl.setText(message)
        self._error_lbl.show()
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Request Access  →")

    def clear_error(self) -> None:
        """Remove the red border and hide the error label."""
        self._code_input.setStyleSheet(_INPUT_NORMAL)
        self._error_lbl.hide()

    def set_loading(self) -> None:
        """Disable the button while the API request is in flight."""
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Submitting…")

    def reset(self) -> None:
        """Restore the widget to its initial empty state (call on success)."""
        self._code_input.clear()
        self.clear_error()
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Request Access  →")
