from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QPushButton, QFrame, QHBoxLayout, QVBoxLayout

from .styles import (
    TOPBAR_BG,
    TOPBAR_BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    PRIMARY_BUTTON,
)

class TopBarWidget(QFrame):
    """Top bar for review title, progress, and sidebar toggle."""

    toggle_sidebar_requested = Signal()
    close_requested = Signal()

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

        self.title_label = QLabel("Exam Review")
        self.title_label.setObjectName("examTitle")
        self.title_label.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {TEXT_PRIMARY};")
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        self.subtitle_label = QLabel("Question 1 of 1")
        self.subtitle_label.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")

        left.addWidget(self.title_label)
        left.addWidget(self.subtitle_label)
        root.addLayout(left, stretch=1)

        self.score_label = QLabel("")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {TEXT_PRIMARY}; padding: 0 16px;")
        root.addWidget(self.score_label)

        self.toggle_sidebar_button = QPushButton("☰ Comments")
        self.toggle_sidebar_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle_sidebar_button.setFixedHeight(38)
        self.toggle_sidebar_button.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {TEXT_PRIMARY};
                border: 1px solid {TOPBAR_BORDER};
                border-radius: 6px;
                padding: 0 16px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #F8FAFC;
            }}
        """)
        self.toggle_sidebar_button.clicked.connect(self.toggle_sidebar_requested.emit)
        root.addWidget(self.toggle_sidebar_button)

        self.close_button = QPushButton("Close")
        self.close_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_button.setFixedHeight(38)
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #dc2626;
            }}
        """)
        self.close_button.clicked.connect(self.close_requested.emit)
        root.addWidget(self.close_button)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title or "Exam Review")

    def update_progress(self, current: int, total: int) -> None:
        self.subtitle_label.setText(f"Question {current} of {total}")

    def set_score(self, score_text: str) -> None:
        if score_text:
            self.score_label.setText(score_text)
        else:
            self.score_label.setText("")
