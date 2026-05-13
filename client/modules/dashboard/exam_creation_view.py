from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QCheckBox,
)

from client.modules.exam_engine.essay_widget import EssayWidget
from client.modules.exam_engine.mcq_widget import MCQWidget


class ExamCreationView(QWidget):
    back_requested = Signal()
    submit_requested = Signal(dict, list)

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._class_payload: dict = {}
        self._questions: list[dict] = []
        self._editing_index: int | None = None

        self._class_label = QLabel("Class: --")
        self._title_input = QLineEdit()
        self._desc_input = QTextEdit()
        self._duration_input = QSpinBox()
        self._scheduled_start_input = QLineEdit()
        self._scheduled_end_input = QLineEdit()

        self._hint = QLabel(
            "Exams are saved as draft and are not live until you schedule or start them from the class page."
        )
        self._hint.setWordWrap(True)

        self._require_liveness = QCheckBox(
            "Require entry liveness + face match at exam start (require_liveness_check; "
            "face enrollment is still required by the server to start any session)"
        )
        self._require_liveness.setChecked(True)
        self._allow_paste = QCheckBox("Allow paste in essay answers")
        self._allow_paste.setChecked(False)
        self._max_window_switches = QSpinBox()
        self._max_face_absent = QSpinBox()
        self._face_recheck_minutes = QSpinBox()

        self._q_type = QComboBox()
        self._q_text = QTextEdit()
        self._q_marks = QDoubleSpinBox()
        self._q_options = QLineEdit()
        self._q_correct_option = QLineEdit()
        self._q_min_words = QSpinBox()
        self._q_max_words = QSpinBox()
        self._questions_list = QListWidget()
        self._preview_host = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_host)
        self._preview_widget: QWidget | None = None
        self._status = QLabel("")
        self._build()
        self._wire()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("Back to Class")
        back.clicked.connect(self.back_requested.emit)
        submit = QPushButton("Create draft exam + questions")
        submit.clicked.connect(self._emit_submit)
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(submit)
        root.addLayout(top)

        self._class_label.setObjectName("sectionHeading")
        root.addWidget(self._class_label)

        meta_card = QWidget()
        self._apply_shadow(meta_card)
        meta = QVBoxLayout(meta_card)
        meta.addWidget(QLabel("Exam Title"))
        self._title_input.setPlaceholderText("Midterm - Operating Systems")
        meta.addWidget(self._title_input)
        meta.addWidget(QLabel("Description"))
        self._desc_input.setFixedHeight(80)
        meta.addWidget(self._desc_input)

        row = QHBoxLayout()
        self._duration_input.setRange(1, 600)
        self._duration_input.setValue(60)
        self._scheduled_start_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (optional)")
        self._scheduled_end_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (optional)")
        row.addWidget(QLabel("Duration (min)"))
        row.addWidget(self._duration_input)
        row.addWidget(QLabel("Start"))
        row.addWidget(self._scheduled_start_input, 1)
        row.addWidget(QLabel("End"))
        row.addWidget(self._scheduled_end_input, 1)
        meta.addLayout(row)

        meta.addWidget(self._hint)
        meta.addWidget(self._require_liveness)
        meta.addWidget(self._allow_paste)
        proc_row = QHBoxLayout()
        self._max_window_switches.setRange(0, 50)
        self._max_window_switches.setValue(3)
        self._max_face_absent.setRange(1, 600)
        self._max_face_absent.setValue(10)
        self._face_recheck_minutes.setRange(1, 240)
        self._face_recheck_minutes.setValue(5)
        proc_row.addWidget(QLabel("Max window switches"))
        proc_row.addWidget(self._max_window_switches)
        proc_row.addWidget(QLabel("Max face absent (sec)"))
        proc_row.addWidget(self._max_face_absent)
        proc_row.addWidget(QLabel("Face re-check (min)"))
        proc_row.addWidget(self._face_recheck_minutes)
        meta.addLayout(proc_row)
        root.addWidget(meta_card)

        q_card = QWidget()
        self._apply_shadow(q_card)
        q = QVBoxLayout(q_card)
        q.addWidget(QLabel("Add Question"))
        self._q_type.addItems(["mcq", "essay"])
        q.addWidget(self._q_type)
        self._q_text.setPlaceholderText("Question text")
        self._q_text.setFixedHeight(70)
        q.addWidget(self._q_text)
        mark_row = QHBoxLayout()
        self._q_marks.setRange(0.5, 100.0)
        self._q_marks.setSingleStep(0.5)
        self._q_marks.setValue(1.0)
        mark_row.addWidget(QLabel("Marks"))
        mark_row.addWidget(self._q_marks)
        q.addLayout(mark_row)

        self._q_options.setPlaceholderText("MCQ options, comma-separated (A,B,C,D)")
        self._q_correct_option.setPlaceholderText("Correct option value (e.g., A)")
        q.addWidget(self._q_options)
        q.addWidget(self._q_correct_option)

        words = QHBoxLayout()
        self._q_min_words.setRange(0, 20000)
        self._q_max_words.setRange(0, 20000)
        self._q_min_words.setValue(0)
        self._q_max_words.setValue(300)
        words.addWidget(QLabel("Essay min words"))
        words.addWidget(self._q_min_words)
        words.addWidget(QLabel("Essay max words"))
        words.addWidget(self._q_max_words)
        q.addLayout(words)

        q.addWidget(QLabel("Question Preview"))
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_layout.setSpacing(0)
        q.addWidget(self._preview_host, 1)

        add_q_btn = QPushButton("Add Question")
        add_q_btn.clicked.connect(self._add_question)
        edit_row = QHBoxLayout()
        update_btn = QPushButton("Update Selected")
        remove_btn = QPushButton("Remove Selected")
        move_up_btn = QPushButton("Move Up")
        move_down_btn = QPushButton("Move Down")
        update_btn.clicked.connect(self._update_selected_question)
        remove_btn.clicked.connect(self._remove_selected_question)
        move_up_btn.clicked.connect(self._move_selected_up)
        move_down_btn.clicked.connect(self._move_selected_down)
        edit_row.addWidget(update_btn)
        edit_row.addWidget(remove_btn)
        edit_row.addWidget(move_up_btn)
        edit_row.addWidget(move_down_btn)
        edit_row.addStretch(1)
        edit_row.addWidget(add_q_btn)
        q.addLayout(edit_row)
        root.addWidget(q_card)

        root.addWidget(QLabel("Questions to submit"))
        root.addWidget(self._questions_list, 1)
        root.addWidget(self._status)

    def _wire(self):
        self._q_type.currentTextChanged.connect(self._on_question_type_changed)
        self._q_type.currentTextChanged.connect(self._refresh_question_preview)
        self._q_text.textChanged.connect(self._refresh_question_preview)
        self._q_marks.valueChanged.connect(self._refresh_question_preview)
        self._q_options.textChanged.connect(self._refresh_question_preview)
        self._q_correct_option.textChanged.connect(self._refresh_question_preview)
        self._q_min_words.valueChanged.connect(self._refresh_question_preview)
        self._q_max_words.valueChanged.connect(self._refresh_question_preview)
        self._questions_list.itemClicked.connect(self._load_selected_question_for_edit)
        self._on_question_type_changed(self._q_type.currentText())
        self._refresh_question_preview()

    def set_class_payload(self, payload: dict):
        self._class_payload = dict(payload or {})
        self._class_label.setText(f"Class: {self._class_payload.get('name', 'Unknown')}")
        self._questions.clear()
        self._questions_list.clear()
        self._editing_index = None
        self._status.setText("")
        self._require_liveness.setChecked(True)
        self._allow_paste.setChecked(False)
        self._max_window_switches.setValue(3)
        self._max_face_absent.setValue(10)
        self._face_recheck_minutes.setValue(5)

    def _on_question_type_changed(self, q_type: str):
        is_mcq = q_type == "mcq"
        self._q_options.setEnabled(is_mcq)
        self._q_correct_option.setEnabled(is_mcq)
        self._q_min_words.setEnabled(not is_mcq)
        self._q_max_words.setEnabled(not is_mcq)

    def _add_question(self):
        question = self._build_question_from_form()
        if question is None:
            return

        self._questions.append(question)
        self._refresh_questions_list()
        self._clear_question_form()
        self._status.setText(f"Added question {len(self._questions)}.")

    def _update_selected_question(self):
        item = self._questions_list.currentItem()
        if item is None:
            self._status.setText("Select a question to update.")
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None or index < 0 or index >= len(self._questions):
            self._status.setText("Invalid question selection.")
            return
        question = self._build_question_from_form()
        if question is None:
            return
        self._questions[index] = question
        self._refresh_questions_list()
        self._questions_list.setCurrentRow(index)
        self._status.setText(f"Updated question {index + 1}.")

    def _remove_selected_question(self):
        item = self._questions_list.currentItem()
        if item is None:
            self._status.setText("Select a question to remove.")
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None or index < 0 or index >= len(self._questions):
            self._status.setText("Invalid question selection.")
            return
        self._questions.pop(index)
        self._refresh_questions_list()
        self._clear_question_form()
        self._status.setText("Removed selected question.")

    def _move_selected_up(self):
        item = self._questions_list.currentItem()
        if item is None:
            self._status.setText("Select a question to move.")
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None or index <= 0:
            self._status.setText("Question is already at the top.")
            return
        self._questions[index - 1], self._questions[index] = self._questions[index], self._questions[index - 1]
        self._refresh_questions_list()
        self._questions_list.setCurrentRow(index - 1)
        self._status.setText("Moved question up.")

    def _move_selected_down(self):
        item = self._questions_list.currentItem()
        if item is None:
            self._status.setText("Select a question to move.")
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None or index >= len(self._questions) - 1:
            self._status.setText("Question is already at the bottom.")
            return
        self._questions[index + 1], self._questions[index] = self._questions[index], self._questions[index + 1]
        self._refresh_questions_list()
        self._questions_list.setCurrentRow(index + 1)
        self._status.setText("Moved question down.")

    def _load_selected_question_for_edit(self, item: QListWidgetItem):
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None or index < 0 or index >= len(self._questions):
            return
        q = self._questions[index]
        self._editing_index = index
        self._q_type.setCurrentText(str(q.get("question_type", "mcq")))
        self._q_text.setPlainText(str(q.get("text", "")))
        self._q_marks.setValue(float(q.get("marks", 1.0)))
        self._q_options.setText(", ".join(q.get("options") or []))
        self._q_correct_option.setText(str(q.get("correct_option") or ""))
        self._q_min_words.setValue(int(q.get("min_words") or 0))
        self._q_max_words.setValue(int(q.get("max_words") or 0))
        self._refresh_question_preview()

    def _build_question_from_form(self) -> dict | None:
        q_type = self._q_type.currentText().strip()
        text = self._q_text.toPlainText().strip()
        if not text:
            self._status.setText("Question text is required.")
            return None

        question = {
            "question_type": q_type,
            "text": text,
            "marks": float(self._q_marks.value()),
        }
        if q_type == "mcq":
            options = [o.strip() for o in self._q_options.text().split(",") if o.strip()]
            correct = self._q_correct_option.text().strip()
            if len(options) < 2 or not correct:
                self._status.setText("MCQ requires at least 2 options and a correct option.")
                return None
            question["options"] = options
            question["correct_option"] = correct
            question["max_words"] = None
            question["min_words"] = None
        else:
            question["options"] = None
            question["correct_option"] = None
            question["min_words"] = int(self._q_min_words.value()) or None
            question["max_words"] = int(self._q_max_words.value()) or None
        return question

    def _refresh_questions_list(self):
        self._questions_list.clear()
        for idx, question in enumerate(self._questions, start=1):
            text = str(question.get("text", ""))
            q_type = str(question.get("question_type", "unknown"))
            item = QListWidgetItem(f"{idx}. [{q_type}] {text[:80]}")
            item.setData(Qt.ItemDataRole.UserRole, idx - 1)
            self._questions_list.addItem(item)

    def _clear_question_form(self):
        self._q_text.clear()
        self._q_options.clear()
        self._q_correct_option.clear()
        self._q_min_words.setValue(0)
        self._q_max_words.setValue(300)
        self._refresh_question_preview()

    def _refresh_question_preview(self, *_args):
        question = self._build_preview_question()
        if not question:
            self._set_preview_widget(QLabel("Enter question text to preview how students will see it."))
            return

        if question["question_type"] == "mcq":
            widget = MCQWidget(question, mode="preview")
            if question.get("correct_option"):
                widget.restore_answer(str(question.get("correct_option")))
        else:
            widget = EssayWidget(
                question,
                allow_paste=True,
                mode="preview",
                readonly=True,
            )
        self._set_preview_widget(widget)

    def _set_preview_widget(self, widget: QWidget):
        if self._preview_widget is not None:
            self._preview_layout.removeWidget(self._preview_widget)
            self._preview_widget.deleteLater()
        self._preview_widget = widget
        self._preview_layout.addWidget(widget)

    def _build_preview_question(self) -> dict | None:
        q_type = self._q_type.currentText().strip()
        text = self._q_text.toPlainText().strip()
        if not text:
            return None

        question = {
            "question_type": q_type,
            "text": text,
            "marks": float(self._q_marks.value()),
        }
        if q_type == "mcq":
            question["options"] = [o.strip() for o in self._q_options.text().split(",") if o.strip()]
            question["correct_option"] = self._q_correct_option.text().strip() or None
            question["min_words"] = None
            question["max_words"] = None
        else:
            question["options"] = None
            question["correct_option"] = None
            question["min_words"] = int(self._q_min_words.value()) or None
            question["max_words"] = int(self._q_max_words.value()) or None
        return question

    def _emit_submit(self):
        class_id = self._class_payload.get("class_id")
        title = self._title_input.text().strip()
        if not class_id or not title:
            self._status.setText("Class and exam title are required.")
            return
        if not self._questions:
            self._status.setText("Add at least one question.")
            return

        payload = {
            "class_id": class_id,
            "title": title,
            "description": self._desc_input.toPlainText().strip() or None,
            "duration_minutes": int(self._duration_input.value()),
            "scheduled_start": self._scheduled_start_input.text().strip() or None,
            "scheduled_end": self._scheduled_end_input.text().strip() or None,
            "max_window_switches": int(self._max_window_switches.value()),
            "max_face_absent_seconds": int(self._max_face_absent.value()),
            "allow_paste_in_essay": bool(self._allow_paste.isChecked()),
            "require_liveness_check": bool(self._require_liveness.isChecked()),
            "face_recheck_interval_minutes": int(self._face_recheck_minutes.value()),
        }
        self.submit_requested.emit(payload, list(self._questions))
