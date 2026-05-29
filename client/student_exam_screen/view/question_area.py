from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from .question_widgets import (
    EssayQuestionWidget,
    MCQQuestionWidget,
    question_type_value,
)


class QuestionAreaWidget(QWidget):
    """Owns all question widgets and exposes old-style get/restore APIs."""

    answer_changed = Signal(str, object)
    paste_attempted = Signal(str, int)
    keystroke = Signal(str)

    def __init__(self, questions: list[dict], allow_paste_in_essay: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.questions = [dict(q or {}) for q in questions]
        self.question_widgets = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        for question in self.questions:
            q_type = question_type_value(question)
            if q_type == "mcq":
                widget = MCQQuestionWidget(question)
            else:
                widget = EssayQuestionWidget(question, allow_paste=allow_paste_in_essay)
                widget.paste_attempted.connect(self.paste_attempted.emit)
                widget.keystroke.connect(self.keystroke.emit)
            widget.answer_changed.connect(self.answer_changed.emit)
            self.stack.addWidget(widget)
            self.question_widgets.append(widget)

    def set_current_question(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def current_index(self) -> int:
        return self.stack.currentIndex()

    def current_widget(self):
        return self.stack.currentWidget()

    def get_current_answer(self):
        widget = self.current_widget()
        return widget.get_answer() if widget is not None else None

    def get_answer_by_index(self, index: int):
        if 0 <= index < len(self.question_widgets):
            return self.question_widgets[index].get_answer()
        return None

    def restore_answer(self, question_id: str, value) -> None:
        for widget in self.question_widgets:
            if getattr(widget, "question_id", None) == str(question_id):
                widget.restore_answer(value)
                return

    def set_questions_enabled(self, enabled: bool) -> None:
        for widget in self.question_widgets:
            widget.setEnabled(enabled)
