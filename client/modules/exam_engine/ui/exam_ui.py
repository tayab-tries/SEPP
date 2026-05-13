"""
client/modules/exam_engine/ui/exam_ui.py

Main exam area UI component — question display, navigation, timer.
Pure UI — no logic, no API calls, no proctoring.

Emits signals for user actions:
    prev_requested()      → student clicked Previous
    next_requested()      → student clicked Next
    submit_requested()    → student clicked Submit

Receives state via slots from ExamWindow:
    update_timer(str)         → update timer label text
    set_timer_warning(bool)   → turn timer red
    update_progress(int, int) → update "Question X of Y"
    set_navigation_enabled(bool, bool, bool) → prev, next, submit
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Optional


class ExamUI(QWidget):
    """
    Exam question area with top bar, question stack, and navigation.

    All user-initiated actions are emitted as signals — ExamWindow
    connects to them and handles the logic.
    """

    # ── Signals emitted to ExamWindow ──────────────────────────────────────
    prev_requested   = Signal()
    next_requested   = Signal()
    submit_requested = Signal()

    def __init__(self, questions: list, parent=None):
        super().__init__(parent)
        self.questions = questions
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ── Top bar ────────────────────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.timer_label = QLabel("Time remaining: --:--")
        self.timer_label.setObjectName("timer_label")
        self.timer_label.setProperty("warning", "false")

        self.progress_label = QLabel(f"Question 1 of {len(self.questions)}")
        self.progress_label.setObjectName("progress_label")

        top_bar.addWidget(self.timer_label)
        top_bar.addStretch()
        top_bar.addWidget(self.progress_label)
        layout.addLayout(top_bar)

        # Separator line
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #0f3460;")
        layout.addWidget(separator)

        # ── Question stack ─────────────────────────────────────────────────
        self.question_stack = QStackedWidget()
        layout.addWidget(self.question_stack, stretch=1)

        # ── Navigation bar ─────────────────────────────────────────────────
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(8)

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setObjectName("prev_btn")
        self.prev_btn.setEnabled(False)

        self.submit_btn = QPushButton("Submit Exam")
        self.submit_btn.setObjectName("submit_btn")
        self.submit_btn.setEnabled(False)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setObjectName("next_btn")
        self.next_btn.setEnabled(False)

        self.prev_btn.clicked.connect(self.prev_requested)
        self.next_btn.clicked.connect(self.next_requested)
        self.submit_btn.clicked.connect(self.submit_requested)

        nav_bar.addWidget(self.prev_btn)
        nav_bar.addStretch()
        nav_bar.addWidget(self.submit_btn)
        nav_bar.addWidget(self.next_btn)
        layout.addLayout(nav_bar)

    # ── Slots connected from ExamWindow ───────────────────────────────────

    @Slot(str)
    def update_timer(self, text: str):
        self.timer_label.setText(text)

    @Slot(bool)
    def set_timer_warning(self, warning: bool):
        """Turn timer red when ≤5 minutes remaining."""
        self.timer_label.setProperty("warning", "true" if warning else "false")
        self.timer_label.style().unpolish(self.timer_label)
        self.timer_label.style().polish(self.timer_label)

    @Slot(int, int)
    def update_progress(self, current: int, total: int):
        self.progress_label.setText(f"Question {current} of {total}")

    @Slot(bool, bool, bool)
    def set_navigation_enabled(
        self,
        prev:   bool,
        next_:  bool,
        submit: bool,
    ):
        self.prev_btn.setEnabled(prev)
        self.next_btn.setEnabled(next_)
        self.submit_btn.setEnabled(submit)
