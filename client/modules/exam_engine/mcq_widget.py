"""
client/modules/exam_engine/mcq_widget.py

MCQ question widget — redesigned to match the new exam UI.

Public API unchanged:
    get_answer()            -> str | None
    restore_answer(str)
    set_answer(str | None)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


_BG_PAGE = "#F0F2F5"
_BG_OPTION = "#FFFFFF"
_BG_SELECTED = "#EEF3FF"
_BORDER = "#E5E7EB"
_BORDER_SEL = "#6B8CFF"
_NAVY = "#0F2454"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"
_PILL_DEFAULT = "#EEF3FF"
_PILL_SEL_BG = _NAVY
_PILL_SEL_FG = "#FFFFFF"
_PILL_DEF_FG = _NAVY


class _OptionRow(QFrame):
    clicked = Signal(int)

    LABELS = ["A", "B", "C", "D", "E", "F"]

    def __init__(
        self,
        index: int,
        text: str,
        readonly: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.index = index
        self.readonly = readonly
        self.label_char = self.LABELS[index] if index < len(self.LABELS) else str(index)

        self.setFixedHeight(56)
        self.setCursor(
            Qt.CursorShape.ArrowCursor if readonly else Qt.CursorShape.PointingHandCursor
        )
        self._apply_style(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 20, 0)
        layout.setSpacing(16)

        self._pill = QLabel(self.label_char)
        self._pill.setFixedSize(32, 32)
        self._pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_pill_style(False)

        self._text_label = QLabel(text)
        self._text_label.setWordWrap(True)
        self._text_label.setStyleSheet(
            f"font-size: 14px; color: {_TXT}; background: transparent;"
        )

        layout.addWidget(self._pill)
        layout.addWidget(self._text_label, 1)

    def set_selected(self, selected: bool) -> None:
        self._apply_style(selected)
        self._apply_pill_style(selected)

    def _apply_style(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                f"QFrame {{ background-color: {_BG_SELECTED};"
                f"border: 1.5px solid {_BORDER_SEL};"
                f"border-radius: 12px; }}"
            )
            return
        hover_rule = "QFrame:hover { border-color: #B0BFFF; }" if not self.readonly else ""
        self.setStyleSheet(
            f"QFrame {{ background-color: {_BG_OPTION};"
            f"border: 1.5px solid {_BORDER};"
            f"border-radius: 12px; }}"
            f"{hover_rule}"
        )

    def _apply_pill_style(self, selected: bool) -> None:
        if selected:
            self._pill.setStyleSheet(
                f"background-color: {_PILL_SEL_BG}; color: {_PILL_SEL_FG};"
                "border-radius: 16px; font-size: 13px; font-weight: 900;"
            )
            return
        self._pill.setStyleSheet(
            f"background-color: {_PILL_DEFAULT}; color: {_PILL_DEF_FG};"
            "border-radius: 16px; font-size: 13px; font-weight: 900;"
        )

    def mousePressEvent(self, event) -> None:
        if not self.readonly:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)


class MCQWidget(QWidget):
    OPTION_LABELS = _OptionRow.LABELS

    def __init__(
        self,
        question: dict,
        mode: str = "attempt",
        readonly: bool | None = None,
    ) -> None:
        super().__init__()
        self.question = question
        self.mode = mode
        self.readonly = (mode in {"preview", "review"}) if readonly is None else readonly
        self._selected_index: int | None = None
        self._option_rows: list[_OptionRow] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(f"background-color: {_BG_PAGE};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 8, 40, 24)
        root.setSpacing(0)

        question_label = QLabel(self.question.get("text", ""))
        question_label.setWordWrap(True)
        question_label.setStyleSheet(
            f"font-size: 22px; font-weight: 900; color: {_TXT}; background: transparent;"
        )
        root.addWidget(question_label)
        root.addSpacing(6)

        marks = self.question.get("marks", 1)
        marks_label = QLabel(f"{marks} mark{'s' if marks != 1 else ''}")
        marks_label.setStyleSheet(
            f"font-size: 13px; color: {_TXT_MUTED}; background: transparent;"
        )
        root.addWidget(marks_label)
        root.addSpacing(28)

        response_label = QLabel("Your Response")
        response_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TXT_MUTED};"
            "background: transparent; letter-spacing: 0.5px;"
        )
        root.addWidget(response_label)
        root.addSpacing(12)

        options_widget = QWidget()
        options_widget.setStyleSheet("background: transparent;")
        options_layout = QVBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(10)

        for index, option_text in enumerate(self.question.get("options", [])):
            row = _OptionRow(index, str(option_text), readonly=self.readonly)
            row.clicked.connect(self._on_option_clicked)
            options_layout.addWidget(row)
            self._option_rows.append(row)

        root.addWidget(options_widget)
        root.addStretch(1)

    def _select_index(self, index: int) -> None:
        if index < 0 or index >= len(self._option_rows):
            return
        if self._selected_index is not None and self._selected_index < len(self._option_rows):
            self._option_rows[self._selected_index].set_selected(False)
        self._selected_index = index
        self._option_rows[index].set_selected(True)

    def _on_option_clicked(self, index: int) -> None:
        if self.readonly:
            return
        self._select_index(index)

    def get_answer(self) -> Optional[str]:
        if self._selected_index is None:
            return None
        labels = self.OPTION_LABELS
        return (
            labels[self._selected_index]
            if self._selected_index < len(labels)
            else str(self._selected_index)
        )

    def restore_answer(self, selected_option: str) -> None:
        labels = self.OPTION_LABELS
        if selected_option in labels:
            self._select_index(labels.index(selected_option))
            return
        for index, option_text in enumerate(self.question.get("options", [])):
            if str(option_text).strip() == str(selected_option).strip():
                self._select_index(index)
                return

    def set_answer(self, selected_option: Optional[str]) -> None:
        self.restore_answer(str(selected_option or ""))
