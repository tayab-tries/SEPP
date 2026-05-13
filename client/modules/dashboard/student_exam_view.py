from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QFrame,
)

from client.modules.exam_engine.essay_widget import EssayWidget
from client.modules.exam_engine.mcq_widget import MCQWidget


def _noop_keystroke():
    return None


def _noop_paste(_length: int):
    return None


class StudentExamView(QWidget):
    back_requested = Signal()
    submit_requested = Signal(dict, list)  # session payload, answers payload list

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._session: dict = {}
        self._exam: dict = {}
        self._questions: list[dict] = []
        self._answers_by_question: dict[str, dict] = {}
        self._readonly = False
        self._graded = False

        self._title = QLabel("Exam")
        self._status = QLabel("")
        self._question_list = QListWidget()
        self._question_stack = QStackedWidget()
        self._submit_btn = QPushButton("Submit Exam")
        self._feedback = QLabel("")
        self._question_widgets: list[QWidget] = []
        self._build()
        self._wire()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("Back")
        back.clicked.connect(self.back_requested.emit)
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(self._submit_btn)
        root.addLayout(top)

        self._title.setObjectName("sectionHeading")
        root.addWidget(self._title)
        root.addWidget(self._status)

        body = QHBoxLayout()
        body.setSpacing(12)

        left = QFrame()
        left.setObjectName("mainCard")
        self._apply_shadow(left)
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(14, 14, 14, 14)
        left_col.addWidget(QLabel("Questions"))
        left_col.addWidget(self._question_list, 1)
        body.addWidget(left, 1)

        right = QFrame()
        right.setObjectName("mainCard")
        self._apply_shadow(right)
        right_col = QVBoxLayout(right)
        right_col.setContentsMargins(14, 14, 14, 14)
        right_col.addWidget(self._question_stack, 1)
        self._feedback.setWordWrap(True)
        right_col.addWidget(self._feedback)
        body.addWidget(right, 2)

        root.addLayout(body, 1)

    def _wire(self):
        self._submit_btn.clicked.connect(self._emit_submit)
        self._question_list.currentRowChanged.connect(self._question_stack.setCurrentIndex)
        self._question_list.currentRowChanged.connect(self._render_feedback)

    def configure(
        self,
        session: dict,
        exam: dict,
        questions: list[dict],
        answers: list[dict] | None,
        readonly: bool,
        graded: bool,
    ):
        self._session = dict(session or {})
        self._exam = dict(exam or {})
        self._questions = list(questions or [])
        self._answers_by_question = {
            str(a.get("question_id")): dict(a) for a in (answers or []) if a.get("question_id")
        }
        self._readonly = bool(readonly)
        self._graded = bool(graded)
        self._title.setText(self._exam.get("title", "Exam"))
        self._submit_btn.setVisible(not self._readonly)
        self._submit_btn.setEnabled(not self._readonly)
        self._status.setText(
            "Review mode: answers are read-only." if self._readonly else "Attempt mode: answer all questions then submit."
        )
        self._rebuild_questions()

    def _rebuild_questions(self):
        self._question_list.clear()
        while self._question_stack.count():
            w = self._question_stack.widget(0)
            self._question_stack.removeWidget(w)
            w.deleteLater()
        self._question_widgets.clear()

        if not self._questions:
            self._feedback.setText("No questions available.")
            return

        for idx, q in enumerate(self._questions, start=1):
            qid = str(q.get("question_id") or q.get("id") or "")
            q_type = str(q.get("question_type", "unknown"))
            prompt = str(q.get("text", "Question"))[:60]
            list_item = QListWidgetItem(f"{idx}. [{q_type}] {prompt}")
            self._question_list.addItem(list_item)

            if q_type == "mcq":
                answer_widget = MCQWidget(
                    q,
                    mode="review" if self._readonly else "attempt",
                    readonly=self._readonly,
                )
                answer_widget.restore_answer(
                    (self._answers_by_question.get(qid) or {}).get("selected_option")
                )
            else:
                answer_widget = EssayWidget(
                    q,
                    on_keystroke=_noop_keystroke,
                    on_paste=_noop_paste,
                    allow_paste=bool(self._exam.get("allow_paste_in_essay", False)),
                    mode="review" if self._readonly else "attempt",
                    readonly=self._readonly,
                )
                answer_widget.restore_answer(
                    (self._answers_by_question.get(qid) or {}).get("answer_text")
                )

            self._question_stack.addWidget(answer_widget)
            self._question_widgets.append(answer_widget)

        self._question_list.setCurrentRow(0)
        self._render_feedback(0)

    def _render_feedback(self, row: int):
        if row < 0 or row >= len(self._questions):
            self._feedback.setText("")
            return
        q = self._questions[row]
        qid = str(q.get("question_id") or q.get("id") or "")
        answer_row = self._answers_by_question.get(qid) or {}

        if not self._readonly:
            self._feedback.setText("Feedback appears here after grading.")
            return

        score = answer_row.get("examiner_score")
        is_correct = answer_row.get("is_correct")
        selected = answer_row.get("selected_option")
        lines = [f"Selected option: {selected}" if selected else "Essay answer submitted."]
        if self._graded:
            lines.append(f"Result: {'Correct' if is_correct else 'Incorrect'}" if is_correct is not None else "Result: Pending")
            lines.append(f"Score: {score}" if score is not None else "Score: Pending")
            if str(q.get("question_type")) == "mcq":
                if is_correct is True and selected:
                    lines.append(f"Right answer: {selected}")
                elif is_correct is False:
                    lines.append("Right answer: Not exposed by current backend contract.")
            lines.append("Examiner comment: Not exposed by current backend contract.")
        else:
            lines.append("Grading is not complete yet.")
        self._feedback.setText("\n".join(lines))

    def _emit_submit(self):
        answers_payload: list[dict] = []
        for idx, q in enumerate(self._questions):
            widget = self._question_widgets[idx]
            qid = str(q.get("question_id") or q.get("id") or "")
            q_type = str(q.get("question_type", ""))
            if q_type == "mcq":
                selected = widget.get_answer() if hasattr(widget, "get_answer") else None
                answers_payload.append({"question_id": qid, "selected_option": selected, "answer_text": None})
            else:
                text = widget.get_answer() if hasattr(widget, "get_answer") else ""
                answers_payload.append({"question_id": qid, "selected_option": None, "answer_text": text})
        self.submit_requested.emit(dict(self._session), answers_payload)
