from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QHBoxLayout, QVBoxLayout

from .styles import (
    TOPBAR_BG,
    TOPBAR_BORDER,
    TOPBAR_TIMER_BG,
    TOPBAR_TIMER_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    DANGER_BUTTON,
)

class TopBarWidget(QFrame):
    """Top bar for exam title, progress, countdown, and submit action."""

    submit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("examTopBar")
        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            QFrame#examTopBar {{
                background: {TOPBAR_BG};
                border-bottom: 1px solid {TOPBAR_BORDER};
            }}
            QLabel {{
                background: transparent;
                color: {TEXT_PRIMARY};
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 10, 24, 10)
        root.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(2)

        self.title_label = QLabel("Exam")
        self.title_label.setObjectName("examTitle")
        self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {TEXT_PRIMARY};")
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        self.subtitle_label = QLabel("Question 1 of 1")
        self.subtitle_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")

        left.addWidget(self.title_label)
        left.addWidget(self.subtitle_label)
        root.addLayout(left, stretch=1)

        self.timer_label = QLabel("Time remaining: --:--")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setMinimumWidth(190)
        self.timer_label.setFixedHeight(38)
        self.timer_label.setStyleSheet(f"""
            QLabel {{
                background: {TOPBAR_TIMER_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {TOPBAR_TIMER_BORDER};
                border-radius: 19px;
                font-size: 13px;
                font-weight: 800;
                padding: 0 14px;
            }}
        """)
        root.addWidget(self.timer_label)

        self.submit_button = QPushButton("Submit Exam")
        self.submit_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.submit_button.setFixedHeight(38)
        self.submit_button.setMinimumWidth(128)
        self.submit_button.setStyleSheet(DANGER_BUTTON)
        self.submit_button.clicked.connect(self.submit_requested.emit)
        root.addWidget(self.submit_button)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title or "Exam")

    def update_progress(self, current: int, total: int) -> None:
        self.subtitle_label.setText(f"Question {current} of {total}")

    def update_timer(self, text: str) -> None:
        self.timer_label.setText(text or "Time remaining: --:--")

    def set_timer_warning(self, enabled: bool) -> None:
        bg = WARNING if enabled else TOPBAR_TIMER_BG
        text_color = "white" if enabled else TEXT_PRIMARY
        self.timer_label.setStyleSheet(f"""
            QLabel {{
                background: {bg};
                color: {text_color};
                border: 1px solid {TOPBAR_TIMER_BORDER};
                border-radius: 19px;
                font-size: 13px;
                font-weight: 800;
                padding: 0 14px;
            }}
        """)

    def set_submit_enabled(self, enabled: bool) -> None:
        self.submit_button.setEnabled(enabled)
