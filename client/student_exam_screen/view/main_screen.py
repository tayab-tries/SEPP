from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from .navigation_buttons import NavigationButtonsWidget
from .question_area import QuestionAreaWidget
from .styles import CARD_BG, CARD_BORDER


class MainScreenWidget(QFrame):
    """Center content card: scrollable question content + non-overlapping nav row."""

    prev_requested = Signal()
    next_requested = Signal()
    answer_changed = Signal(str, object)
    paste_attempted = Signal(str, int)
    keystroke = Signal(str)

    def __init__(self, questions: list[dict], allow_paste_in_essay: bool = False, parent=None) -> None:
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
            allow_paste_in_essay=allow_paste_in_essay,
        )
        self.question_area.answer_changed.connect(self.answer_changed.emit)
        self.question_area.paste_attempted.connect(self.paste_attempted.emit)
        self.question_area.keystroke.connect(self.keystroke.emit)

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

    def set_current_question(self, index: int) -> None:
        self.question_area.set_current_question(index)
        self.scroll.verticalScrollBar().setValue(0)

    def get_current_answer(self):
        return self.question_area.get_current_answer()

    def get_answer_by_index(self, index: int):
        return self.question_area.get_answer_by_index(index)

    def restore_answer(self, question_id: str, value) -> None:
        self.question_area.restore_answer(question_id, value)

    def set_navigation_enabled(self, prev_enabled: bool, next_enabled: bool) -> None:
        self.nav.set_enabled_state(prev_enabled, next_enabled)

    def set_questions_enabled(self, enabled: bool) -> None:
        self.question_area.set_questions_enabled(enabled)
