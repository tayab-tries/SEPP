"""
client/modules/exam_engine/essay_widget.py

Essay question widget — redesigned to match the new exam UI.

Security controls preserved:
  - Paste interception
  - Keystroke cadence reporting
  - Word limit enforcement
  - Drag-and-drop paste interception
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit, QVBoxLayout, QWidget


_BG_PAGE = "#F0F2F5"
_BG_WHITE = "#FFFFFF"
_BORDER = "#D1D5DB"
_BORDER_FOC = "#6B8CFF"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"
_RED_WARN = "#DC2626"
_AMBER_WARN = "#D97706"


class EssayWidget(QWidget):
    def __init__(
        self,
        question: dict,
        on_keystroke: Callable | None = None,
        on_paste: Callable[[int], None] | None = None,
        allow_paste: bool = False,
        mode: str = "attempt",
        readonly: bool | None = None,
    ) -> None:
        super().__init__()
        self.question = question
        self.on_keystroke = on_keystroke or (lambda: None)
        self.on_paste = on_paste or (lambda _length: None)
        self.allow_paste = allow_paste
        self.mode = mode
        self.readonly = (mode in {"preview", "review"}) if readonly is None else readonly
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

        info_parts = [f"{self.question.get('marks', 1)} mark(s)"]
        if self.question.get("min_words"):
            info_parts.append(f"Min: {self.question['min_words']} words")
        if self.question.get("max_words"):
            info_parts.append(f"Max: {self.question['max_words']} words")
        info_label = QLabel("  ·  ".join(info_parts))
        info_label.setStyleSheet(
            f"font-size: 13px; color: {_TXT_MUTED}; background: transparent;"
        )
        root.addWidget(info_label)
        root.addSpacing(28)

        response_label = QLabel("Your Response")
        response_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_TXT_MUTED};"
            "background: transparent; letter-spacing: 0.5px;"
        )
        root.addWidget(response_label)
        root.addSpacing(10)

        self.text_edit = _LockedTextEdit(
            on_keystroke=self.on_keystroke,
            on_paste=self.on_paste,
            allow_paste=self.allow_paste,
            max_words=self.question.get("max_words"),
            monitor_input=not self.readonly,
        )
        self.text_edit.setReadOnly(self.readonly)
        self.text_edit.setMinimumHeight(300)
        self.text_edit.setPlaceholderText("Type your comprehensive analysis here...")
        self.text_edit.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {_BG_WHITE};
                border: 1.5px solid {_BORDER};
                border-radius: 12px;
                padding: 16px;
                font-size: 15px;
                color: {_TXT};
            }}
            QTextEdit:focus {{
                border-color: {_BORDER_FOC};
            }}
            """
        )
        self.text_edit.textChanged.connect(self._update_word_count)
        root.addWidget(self.text_edit, 1)
        root.addSpacing(8)

        self.word_count_label = QLabel("Words: 0")
        self.word_count_label.setStyleSheet(
            f"font-size: 12px; color: {_TXT_MUTED}; background: transparent;"
        )
        root.addWidget(self.word_count_label)
        root.addStretch(1)

    def _update_word_count(self) -> None:
        text = self.text_edit.toPlainText().strip()
        count = len(text.split()) if text else 0
        max_words = self.question.get("max_words")

        if max_words and count > max_words:
            color = _RED_WARN
        elif max_words and count > max_words * 0.9:
            color = _AMBER_WARN
        else:
            color = _TXT_MUTED

        limit = f" / {max_words}" if max_words else ""
        self.word_count_label.setText(f"Words: {count}{limit}")
        self.word_count_label.setStyleSheet(
            f"font-size: 12px; color: {color}; background: transparent;"
        )

    def get_answer(self) -> str:
        return self.text_edit.toPlainText()

    def restore_answer(self, answer_text: str) -> None:
        self.text_edit.setPlainText(answer_text or "")

    def set_answer(self, answer_text: Optional[str]) -> None:
        self.restore_answer(str(answer_text or ""))


class _LockedTextEdit(QTextEdit):
    _NAVIGATION_KEYS = {
        Qt.Key.Key_Backspace,
        Qt.Key.Key_Delete,
        Qt.Key.Key_Left,
        Qt.Key.Key_Right,
        Qt.Key.Key_Up,
        Qt.Key.Key_Down,
        Qt.Key.Key_Home,
        Qt.Key.Key_End,
        Qt.Key.Key_PageUp,
        Qt.Key.Key_PageDown,
    }

    def __init__(
        self,
        on_keystroke: Callable,
        on_paste: Callable[[int], None],
        allow_paste: bool,
        max_words: Optional[int],
        monitor_input: bool = True,
    ) -> None:
        super().__init__()
        self.on_keystroke = on_keystroke
        self.on_paste = on_paste
        self.allow_paste = allow_paste
        self.max_words = max_words
        self.monitor_input = monitor_input

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.isReadOnly():
            super().keyPressEvent(event)
            return

        is_paste = (
            (
                event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_V
            )
            or (
                event.modifiers() == Qt.KeyboardModifier.ShiftModifier
                and event.key() == Qt.Key.Key_Insert
            )
        )

        if is_paste:
            clipboard_text = QApplication.clipboard().text()
            if self.monitor_input:
                self.on_paste(len(clipboard_text))
            if not self.allow_paste:
                return

        if self.max_words and event.key() not in self._NAVIGATION_KEYS:
            if event.text() and not event.modifiers():
                current_words = len(self.toPlainText().split())
                if current_words >= self.max_words:
                    if self.monitor_input:
                        self.on_keystroke()
                    return

        if self.monitor_input:
            self.on_keystroke()
        super().keyPressEvent(event)

    def insertFromMimeData(self, source) -> None:
        text = source.text() if source.hasText() else ""
        if self.monitor_input:
            self.on_paste(len(text))
        if self.allow_paste:
            super().insertFromMimeData(source)
