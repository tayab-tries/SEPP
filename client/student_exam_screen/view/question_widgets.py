from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QCursor, QTextOption
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    ACCENT,
    CARD_BG,
    CARD_BORDER,
    DANGER,
    OPTION_BG,
    OPTION_SELECTED_BG,
    OPTION_SELECTED_BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def question_type_value(question: dict) -> str:
    raw = question.get("question_type")
    return getattr(raw, "value", raw) or ""


def option_key(index: int) -> str:
    """Return A, B, ..., Z, AA, AB... for any option count."""
    letters = ""
    n = index
    while True:
        letters = chr(ord("A") + (n % 26)) + letters
        n = n // 26 - 1
        if n < 0:
            return letters


def word_count(text: str) -> int:
    return len(re.findall(r"\b\S+\b", text or ""))


class BaseQuestionWidget(QFrame):
    answer_changed = Signal(str, object)

    def __init__(self, question: dict, parent=None) -> None:
        super().__init__(parent)
        self.question = dict(question or {})
        self.question_id = str(self.question.get("id") or self.question.get("question_id") or "")
        self.setObjectName("questionWidget")
        self.setStyleSheet(f"""
            QFrame#questionWidget {{
                background: {CARD_BG};
                border: none;
            }}
            QLabel {{ background: transparent; }}
        """)

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(18)

        meta = QLabel(self._meta_text())
        meta.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:12px; font-weight:700;")
        self.root.addWidget(meta)

        self.question_label = QLabel(str(self.question.get("text") or ""))
        self.question_label.setWordWrap(True)
        self.question_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.question_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: 18px;
                font-weight: 800;
                line-height: 1.35;
            }}
        """)
        self.root.addWidget(self.question_label)

    def _meta_text(self) -> str:
        marks = self.question.get("marks")
        q_type = question_type_value(self.question).upper() or "QUESTION"
        if marks is None:
            return q_type
        return f"{q_type} • {marks} mark{'s' if float(marks or 0) != 1 else ''}"

    def get_answer(self):
        raise NotImplementedError

    def restore_answer(self, value):
        raise NotImplementedError


class MCQOptionButton(QRadioButton):
    def __init__(self, key: str, text: str, parent=None) -> None:
        super().__init__(f"{key}. {text}", parent)
        self.option_key = key
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(48)
        self.setWordWrap(True) if hasattr(self, "setWordWrap") else None
        self.setStyleSheet(f"""
            QRadioButton {{
                background: {OPTION_BG};
                border: 1px solid #e3e9f2;
                border-radius: 10px;
                padding: 13px 14px;
                color: {TEXT_PRIMARY};
                font-size: 14px;
                font-weight: 600;
                spacing: 10px;
            }}
            QRadioButton:hover {{
                border: 1px solid {OPTION_SELECTED_BORDER};
                background: #f0f9fd;
            }}
            QRadioButton:checked {{
                border: 1px solid {OPTION_SELECTED_BORDER};
                background: {OPTION_SELECTED_BG};
                color: {TEXT_PRIMARY};
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)


class MCQQuestionWidget(BaseQuestionWidget):
    """Single-answer MCQ widget. Returns backend option key: A/B/C..."""

    def __init__(self, question: dict, parent=None) -> None:
        super().__init__(question, parent)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons: dict[str, MCQOptionButton] = {}

        options = self.question.get("options") or []
        options_container = QWidget()
        options_lay = QVBoxLayout(options_container)
        options_lay.setContentsMargins(0, 4, 0, 0)
        options_lay.setSpacing(10)

        for i, item in enumerate(options):
            key = option_key(i)
            text = str(item)
            if isinstance(item, dict):
                key = str(item.get("key") or item.get("id") or key)
                text = str(item.get("text") or item.get("label") or item.get("value") or "")
            btn = MCQOptionButton(key, text)
            self.group.addButton(btn)
            self._buttons[key] = btn
            options_lay.addWidget(btn)
            btn.toggled.connect(lambda checked, k=key: self._on_toggled(k, checked))

        if not options:
            empty = QLabel("No options were provided for this MCQ.")
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
            options_lay.addWidget(empty)

        self.root.addWidget(options_container)
        self.root.addStretch(1)

    def _on_toggled(self, key: str, checked: bool) -> None:
        if checked:
            self.answer_changed.emit(self.question_id, key)

    def get_answer(self) -> str | None:
        checked = self.group.checkedButton()
        if checked is None:
            return None
        return getattr(checked, "option_key", None)

    def restore_answer(self, value: str | None) -> None:
        if not value:
            self.group.setExclusive(False)
            for btn in self._buttons.values():
                btn.setChecked(False)
            self.group.setExclusive(True)
            return
        btn = self._buttons.get(str(value))
        if btn:
            btn.setChecked(True)


class AutoResizeTextEdit(QTextEdit):
    paste_blocked = Signal(int)

    def __init__(self, allow_paste: bool, min_height: int = 180, max_height: int = 420, parent=None) -> None:
        super().__init__(parent)
        self.allow_paste = allow_paste
        self.min_height = min_height
        self.max_height = max_height
        self.setAcceptRichText(False)
        self.setPlaceholderText("Type your answer here...")
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.setMinimumHeight(min_height)
        self.setFixedHeight(min_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: #fbfdff;
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
                padding: 12px;
                color: {TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.45;
                selection-background-color: {ACCENT};
            }}
            QTextEdit:focus {{
                border: 1px solid {ACCENT};
                background: white;
            }}
        """)
        self.document().contentsChanged.connect(self._schedule_resize)

    def insertFromMimeData(self, source) -> None:  # noqa: N802 - Qt override
        text = source.text() if source and source.hasText() else ""
        if not self.allow_paste:
            self.paste_blocked.emit(len(text))
            return
        super().insertFromMimeData(source)

    def _schedule_resize(self) -> None:
        QTimer.singleShot(0, self._resize_to_document)

    def _resize_to_document(self) -> None:
        doc_height = int(self.document().size().height()) + 34
        new_height = max(self.min_height, min(doc_height, self.max_height))
        if new_height != self.height():
            self.setFixedHeight(new_height)


class EssayQuestionWidget(BaseQuestionWidget):
    paste_attempted = Signal(str, int)
    keystroke = Signal(str)

    def __init__(self, question: dict, allow_paste: bool = False, parent=None) -> None:
        super().__init__(question, parent)
        self.allow_paste = allow_paste

        self.word_limits_label = QLabel(self._limits_text(0))
        self.word_limits_label.setWordWrap(True)
        self.word_limits_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:12px; font-weight:700;")
        self.root.addWidget(self.word_limits_label)

        self.editor = AutoResizeTextEdit(allow_paste=allow_paste)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.paste_blocked.connect(self._on_paste_blocked)
        self.root.addWidget(self.editor)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        self.warning_label.setStyleSheet(f"color:{DANGER}; font-size:12px; font-weight:700;")
        self.root.addWidget(self.warning_label)
        self.root.addStretch(1)

    def _limits_text(self, count: int) -> str:
        min_words = self.question.get("min_words")
        max_words = self.question.get("max_words")
        parts = [f"Words: {count}"]
        if min_words is not None:
            parts.append(f"Minimum: {min_words}")
        if max_words is not None:
            parts.append(f"Maximum: {max_words}")
        return "  •  ".join(parts)

    def _on_text_changed(self) -> None:
        text = self.editor.toPlainText()
        self.word_limits_label.setText(self._limits_text(word_count(text)))
        self.answer_changed.emit(self.question_id, text)
        self.keystroke.emit(self.question_id)

    def _on_paste_blocked(self, length: int) -> None:
        self.warning_label.setText("Paste is disabled for this exam.")
        self.warning_label.show()
        QTimer.singleShot(2500, self.warning_label.hide)
        self.paste_attempted.emit(self.question_id, length)

    def get_answer(self) -> str:
        return self.editor.toPlainText()

    def restore_answer(self, value: str | None) -> None:
        self.editor.blockSignals(True)
        self.editor.setPlainText(value or "")
        self.editor.blockSignals(False)
        self.word_limits_label.setText(self._limits_text(word_count(value or "")))
        self.editor._schedule_resize()
