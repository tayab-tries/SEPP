from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from .navigation_buttons import NavigationButtonsWidget
from .question_area import QuestionAreaWidget
from .styles import CARD_BG, CARD_BORDER


class MainScreenWidget(QFrame):
    """Center content card: scrollable question content + non-overlapping nav row for review mode."""

    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, questions: list[dict], answers: list[dict] | None = None, session_id: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("mainQuestionCard")
        self.setStyleSheet(f"""
            QFrame#mainQuestionCard {{
                background: #FFFFFF;
                border: 1px solid #DDe5ef;
                border-radius: 8px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(0)

        self.question_area = QuestionAreaWidget(
            questions=questions,
            answers=answers,
            session_id=session_id
        )

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.question_area)
        root.addWidget(self.scroll, stretch=1)

        self.nav = NavigationButtonsWidget()
        self.nav.prev_requested.connect(self.prev_requested.emit)
        self.nav.next_requested.connect(self.next_requested.emit)
        root.addWidget(self.nav)

    @property
    def question_widgets(self):
        return self.question_area.question_widgets
        
    @property
    def answers_map(self):
        return self.question_area.answers_map

    def set_current_question(self, index: int) -> None:
        self.question_area.set_current_question(index)
        self.scroll.verticalScrollBar().setValue(0)

    def set_navigation_enabled(self, prev_enabled: bool, next_enabled: bool) -> None:
        self.nav.set_enabled_state(prev_enabled, next_enabled)
