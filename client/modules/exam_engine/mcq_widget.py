"""
client/modules/exam_engine/mcq_widget.py
MCQ question widget.

Renders a multiple choice question with radio button options.
Labels options A, B, C, D automatically.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QRadioButton, QButtonGroup,
)
from typing import Optional


class MCQWidget(QWidget):
    """
    Renders an MCQ question with radio button options.
    Options labeled A, B, C, D, E automatically.
    """

    OPTION_LABELS = ["A", "B", "C", "D", "E"]

    def __init__(self, question: dict, mode: str = "attempt", readonly: bool | None = None):
        super().__init__()
        self.question = question
        self.mode = mode
        self.readonly = (mode in {"preview", "review"}) if readonly is None else readonly
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Question text
        q_label = QLabel(self.question["text"])
        q_label.setWordWrap(True)
        q_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(q_label)

        # Marks
        marks_label = QLabel(f"[{self.question['marks']} mark(s)]")
        marks_label.setStyleSheet("color: grey; font-size: 12px;")
        layout.addWidget(marks_label)

        # Radio button options
        self.button_group = QButtonGroup(self)

        for i, option_text in enumerate(self.question.get("options", [])):
            label = self.OPTION_LABELS[i] if i < len(self.OPTION_LABELS) else str(i)
            radio = QRadioButton(f"  {label}.  {option_text}")
            radio.setStyleSheet("font-size: 14px; padding: 6px;")
            radio.setEnabled(not self.readonly)
            self.button_group.addButton(radio, i)
            layout.addWidget(radio)

        layout.addStretch()

    def get_answer(self) -> Optional[str]:
        """Return selected option label (A, B, C...) or None if nothing selected."""
        checked_id = self.button_group.checkedId()
        if checked_id == -1:
            return None
        return (
            self.OPTION_LABELS[checked_id]
            if checked_id < len(self.OPTION_LABELS)
            else str(checked_id)
        )

    def restore_answer(self, selected_option: str):
        """Re-check the correct radio button from saved answer."""
        if selected_option in self.OPTION_LABELS:
            idx    = self.OPTION_LABELS.index(selected_option)
            button = self.button_group.button(idx)
            if button:
                button.setChecked(True)
            return

        # Historical dashboard attempts stored option text instead of A/B/C.
        for idx, option_text in enumerate(self.question.get("options", [])):
            if str(option_text).strip() == str(selected_option or "").strip():
                button = self.button_group.button(idx)
                if button:
                    button.setChecked(True)
                return

    def set_answer(self, selected_option: Optional[str]):
        self.restore_answer(str(selected_option or ""))
