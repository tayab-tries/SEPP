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
    QFrame,
    QScrollArea,
)

from client.modules.exam_engine.essay_widget import EssayWidget
from client.modules.exam_engine.mcq_widget import MCQWidget
from client.modules.dashboard.dashboard_shell import (
    SHELL_ACTION,
    SHELL_ACTION_HOVER,
    SHELL_BORDER,
    SHELL_CARD,
    SHELL_TEXT,
    SHELL_TEXT_MUTED,
)


class ExamCreationView(QWidget):
    back_requested = Signal()
    submit_requested = Signal(dict, list)

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._class_payload: dict = {}
        self._questions: list[dict] = []
        self._editing_index: int | None = None
        self._submit_busy = False

        self.setObjectName("examCreationView")

        self._context_label = QLabel("Create a joinable exam")
        self._title_input = QLineEdit()
        self._desc_input = QTextEdit()
        self._duration_input = QSpinBox()
        self._scheduled_start_input = QLineEdit()
        self._scheduled_end_input = QLineEdit()

        self._hint = QLabel(
            "Exams are saved as draft first. After creation, you can schedule them or move them live from the examiner dashboard."
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
        self._back_btn: QPushButton | None = None
        self._submit_btn: QPushButton | None = None
        self._build()
        self._wire()

    def _build(self):
        self.setStyleSheet(
            f"""
            QWidget#examCreationView {{
                background: transparent;
                color: {SHELL_TEXT};
            }}
            QFrame#mainCard {{
                background-color: {SHELL_CARD};
                border: 1px solid {SHELL_BORDER};
                border-radius: 18px;
            }}
            QLabel#fieldLabel {{
                color: {SHELL_TEXT};
                font-size: 13px;
                font-weight: 700;
                background: transparent;
            }}
            QLabel#supportText {{
                color: {SHELL_TEXT_MUTED};
                font-size: 13px;
                background: transparent;
            }}
            QLabel#statusMessage {{
                color: #9A3412;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
            }}
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {{
                background-color: #F7FAFD;
                border: 1px solid {SHELL_BORDER};
                border-radius: 12px;
                color: #1F2937;
                padding: 10px 12px;
                selection-background-color: #D9E7FF;
            }}
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid {SHELL_ACTION};
            }}
            QListWidget {{
                padding: 8px;
            }}
            QListWidget::item {{
                border-radius: 10px;
                padding: 8px 10px;
                margin: 2px 0;
                color: #1F2937;
            }}
            QListWidget::item:selected {{
                background-color: #DCE9FF;
                color: #0F2454;
                border: 1px solid #AFC6F8;
            }}
            QListWidget::item:hover {{
                background-color: #EDF4FF;
            }}
            QCheckBox {{
                color: #243043;
                spacing: 8px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QCheckBox::indicator:unchecked {{
                border: 1px solid {SHELL_BORDER};
                border-radius: 5px;
                background: white;
            }}
            QCheckBox::indicator:checked {{
                border: 1px solid {SHELL_ACTION};
                border-radius: 5px;
                background: {SHELL_ACTION};
            }}
            QPushButton {{
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 700;
            }}
            QPushButton#primaryButton {{
                background-color: {SHELL_ACTION};
                color: white;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {SHELL_ACTION_HOVER};
            }}
            QPushButton#secondaryButton {{
                background-color: #EAF0F7;
                color: {SHELL_TEXT};
                border: 1px solid {SHELL_BORDER};
            }}
            QPushButton#secondaryButton:hover {{
                background-color: #DDE7F2;
            }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        scroll.setWidget(body)

        root = QVBoxLayout(body)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("Back to Dashboard")
        back.setObjectName("secondaryButton")
        back.clicked.connect(self.back_requested.emit)
        submit = QPushButton("Create draft exam + questions")
        submit.setObjectName("primaryButton")
        submit.clicked.connect(self._emit_submit)
        self._back_btn = back
        self._submit_btn = submit
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(submit)
        root.addLayout(top)

        self._context_label.setObjectName("sectionHeading")
        root.addWidget(self._context_label)

        meta_card = QFrame()
        meta_card.setObjectName("mainCard")
        self._apply_shadow(meta_card)
        meta = QVBoxLayout(meta_card)
        meta.setContentsMargins(22, 22, 22, 22)
        meta.setSpacing(12)
        meta_title = QLabel("Exam Setup")
        meta_title.setObjectName("sectionHeading")
        meta_subtitle = QLabel("Define the exam details, scheduling window, and integrity rules.")
        meta_subtitle.setObjectName("supportText")
        meta_subtitle.setWordWrap(True)
        meta.addWidget(meta_title)
        meta.addWidget(meta_subtitle)
        meta.addWidget(self._make_field_label("Exam Title"))
        self._title_input.setPlaceholderText("Midterm - Operating Systems")
        meta.addWidget(self._title_input)
        meta.addWidget(self._make_field_label("Description"))
        self._desc_input.setFixedHeight(80)
        meta.addWidget(self._desc_input)

        row = QHBoxLayout()
        self._duration_input.setRange(1, 600)
        self._duration_input.setValue(60)
        self._scheduled_start_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (optional)")
        self._scheduled_end_input.setPlaceholderText("YYYY-MM-DDTHH:MM:SS (optional)")
        row.addWidget(self._make_field_label("Duration (min)"))
        row.addWidget(self._duration_input)
        row.addWidget(self._make_field_label("Start"))
        row.addWidget(self._scheduled_start_input, 1)
        row.addWidget(self._make_field_label("End"))
        row.addWidget(self._scheduled_end_input, 1)
        meta.addLayout(row)

        self._hint.setObjectName("supportText")
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
        proc_row.addWidget(self._make_field_label("Max window switches"))
        proc_row.addWidget(self._max_window_switches)
        proc_row.addWidget(self._make_field_label("Max face absent (sec)"))
        proc_row.addWidget(self._max_face_absent)
        proc_row.addWidget(self._make_field_label("Face re-check (min)"))
        proc_row.addWidget(self._face_recheck_minutes)
        meta.addLayout(proc_row)
        root.addWidget(meta_card)

        q_card = QFrame()
        q_card.setObjectName("mainCard")
        self._apply_shadow(q_card)
        q = QVBoxLayout(q_card)
        q.setContentsMargins(22, 22, 22, 22)
        q.setSpacing(12)
        q_title = QLabel("Question Builder")
        q_title.setObjectName("sectionHeading")
        q_subtitle = QLabel("Compose MCQ or essay questions and preview them before adding them to the exam.")
        q_subtitle.setObjectName("supportText")
        q_subtitle.setWordWrap(True)
        q.addWidget(q_title)
        q.addWidget(q_subtitle)
        q.addWidget(self._make_field_label("Question Type"))
        self._q_type.addItems(["mcq", "essay"])
        q.addWidget(self._q_type)
        self._q_text.setPlaceholderText("Question text")
        self._q_text.setFixedHeight(70)
        q.addWidget(self._q_text)
        mark_row = QHBoxLayout()
        self._q_marks.setRange(0.5, 100.0)
        self._q_marks.setSingleStep(0.5)
        self._q_marks.setValue(1.0)
        mark_row.addWidget(self._make_field_label("Marks"))
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
        words.addWidget(self._make_field_label("Essay min words"))
        words.addWidget(self._q_min_words)
        words.addWidget(self._make_field_label("Essay max words"))
        words.addWidget(self._q_max_words)
        q.addLayout(words)

        q.addWidget(self._make_field_label("Question Preview"))
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_layout.setSpacing(0)
        q.addWidget(self._preview_host, 1)

        add_q_btn = QPushButton("Add Question")
        add_q_btn.setObjectName("primaryButton")
        add_q_btn.clicked.connect(self._add_question)
        edit_row = QHBoxLayout()
        update_btn = QPushButton("Update Selected")
        remove_btn = QPushButton("Remove Selected")
        move_up_btn = QPushButton("Move Up")
        move_down_btn = QPushButton("Move Down")
        for button in (update_btn, remove_btn, move_up_btn, move_down_btn):
            button.setObjectName("secondaryButton")
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

        queue_card = QFrame()
        queue_card.setObjectName("mainCard")
        self._apply_shadow(queue_card)
        queue = QVBoxLayout(queue_card)
        queue.setContentsMargins(22, 22, 22, 22)
        queue.setSpacing(12)
        queue_title = QLabel("Questions to Submit")
        queue_title.setObjectName("sectionHeading")
        queue_subtitle = QLabel("This is the final order that will be saved with the draft exam.")
        queue_subtitle.setObjectName("supportText")
        queue_subtitle.setWordWrap(True)
        queue.addWidget(queue_title)
        queue.addWidget(queue_subtitle)
        queue.addWidget(self._questions_list, 1)
        root.addWidget(queue_card, 1)

        self._status.setObjectName("statusMessage")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

    def _make_field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

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
        self._questions_list.currentItemChanged.connect(self._on_question_selection_changed)
        self._on_question_type_changed(self._q_type.currentText())
        self._refresh_question_preview()

    def set_class_payload(self, payload: dict):
        self._class_payload = dict(payload or {})
        if self._class_payload.get("name"):
            self._context_label.setText(f"Create exam for {self._class_payload.get('name')}")
        else:
            self._context_label.setText("Create a joinable exam")
        self._questions.clear()
        self._questions_list.clear()
        self._editing_index = None
        self._status.setText("")
        self.set_submit_busy(False)
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
        self._select_question_index(len(self._questions) - 1)
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
        self._select_question_index(index)
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
        if self._questions:
            self._select_question_index(min(index, len(self._questions) - 1))
        else:
            self._editing_index = None
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
        self._select_question_index(index - 1)
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
        self._select_question_index(index + 1)
        self._status.setText("Moved question down.")

    def _load_selected_question_for_edit(self, item: QListWidgetItem):
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None or index < 0 or index >= len(self._questions):
            return
        self._load_question_at_index(int(index))

    def _on_question_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._editing_index = None
            return
        index = current.data(Qt.ItemDataRole.UserRole)
        if index is None:
            self._editing_index = None
            return
        self._load_question_at_index(int(index))

    def _load_question_at_index(self, index: int) -> None:
        if index < 0 or index >= len(self._questions):
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

    def _selected_question_index(self) -> int | None:
        item = self._questions_list.currentItem()
        if item is None:
            return None
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None:
            return None
        index = int(index)
        if 0 <= index < len(self._questions):
            return index
        return None

    def _select_question_index(self, index: int) -> None:
        if index < 0 or index >= self._questions_list.count():
            return
        self._questions_list.setCurrentRow(index)

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
        self._editing_index = None
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
        if self._submit_busy:
            return
        title = self._title_input.text().strip()
        if not title:
            self._status.setText("Exam title is required.")
            return
        if not self._questions:
            self._status.setText("Add at least one question.")
            return

        self.set_submit_busy(True)
        payload = {
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

    def set_exam_context(self, label: str = "Create a joinable exam"):
        self._class_payload = {}
        self._context_label.setText(label)
        self._questions.clear()
        self._questions_list.clear()
        self._editing_index = None
        self._status.setText("")
        self.set_submit_busy(False)
        self._title_input.clear()
        self._desc_input.clear()
        self._scheduled_start_input.clear()
        self._scheduled_end_input.clear()
        self._duration_input.setValue(60)
        self._require_liveness.setChecked(True)
        self._allow_paste.setChecked(False)
        self._max_window_switches.setValue(3)
        self._max_face_absent.setValue(10)
        self._face_recheck_minutes.setValue(5)
        self._clear_question_form()
        self._refresh_questions_list()
        self._q_type.setCurrentText("mcq")
        self._q_marks.setValue(1.0)

    def set_status_message(self, message: str) -> None:
        self._status.setText(message)

    def set_submit_busy(self, busy: bool) -> None:
        self._submit_busy = busy
        if self._submit_btn is not None:
            self._submit_btn.setEnabled(not busy)
            self._submit_btn.setText("Creating draft…" if busy else "Create draft exam + questions")
        if self._back_btn is not None:
            self._back_btn.setEnabled(not busy)
