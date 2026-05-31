from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from .question_widgets import (
    EssayQuestionWidget,
    MCQQuestionWidget,
    question_type_value,
)


class QuestionAreaWidget(QWidget):
    """Owns all question widgets for review mode."""

    def __init__(self, questions: list[dict], answers: list[dict] | None = None, session_id: str = "", parent=None) -> None:
        super().__init__(parent)
        self.session_id = session_id
        self.questions = [dict(q or {}) for q in questions]
        answers_list = answers or []
        
        # Create a mapping of question_id -> answer dict for easy lookup
        self.answers_map = {}
        for ans in answers_list:
            qid = str(ans.get("question_id", ""))
            if qid:
                self.answers_map[qid] = ans

        self.question_widgets = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        for question in self.questions:
            q_type = question_type_value(question)
            qid = str(question.get("id") or question.get("question_id") or "")
            answer = self.answers_map.get(qid, {})

            if q_type == "mcq":
                widget = MCQQuestionWidget(question, answer=answer, session_id=self.session_id)
            else:
                widget = EssayQuestionWidget(question, answer=answer, session_id=self.session_id)
            
            self.stack.addWidget(widget)
            self.question_widgets.append(widget)

    def set_current_question(self, index: int) -> None:
        if 0 <= index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def current_index(self) -> int:
        return self.stack.currentIndex()

    def current_widget(self):
        return self.stack.currentWidget()
