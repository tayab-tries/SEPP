"""
client/modules/exam_engine/essay_widget.py
Essay question widget.

Renders a long-form answer text box with:
  - Paste interception (block or log configurable)
  - Keystroke cadence reporting for paste-bypass detection
  - Live word count with colour warning at 90% and over limit
  - Word limit enforcement — blocks new characters when limit reached
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from typing import Callable, Optional


class EssayWidget(QWidget):
    """
    Essay question renderer with security controls.

    Args:
        question:     Question dict from server
        on_keystroke: Callback fired on every keypress — for cadence analysis
        on_paste:     Callback fired when paste is attempted, receives text length
        allow_paste:  If False, paste is blocked and only reported
    """

    def __init__(
        self,
        question:     dict,
        on_keystroke: Callable | None = None,
        on_paste:     Callable[[int], None] | None = None,
        allow_paste:  bool = False,
        mode:         str = "attempt",
        readonly:     bool | None = None,
    ):
        super().__init__()
        self.question     = question
        self.on_keystroke = on_keystroke or (lambda: None)
        self.on_paste     = on_paste or (lambda _length: None)
        self.allow_paste  = allow_paste
        self.mode         = mode
        self.readonly     = (mode in {"preview", "review"}) if readonly is None else readonly
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Question text
        q_label = QLabel(self.question["text"])
        q_label.setWordWrap(True)
        q_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(q_label)

        # Marks + word limits info bar
        info_parts = [f"{self.question['marks']} mark(s)"]
        if self.question.get("min_words"):
            info_parts.append(f"Min: {self.question['min_words']} words")
        if self.question.get("max_words"):
            info_parts.append(f"Max: {self.question['max_words']} words")
        info_label = QLabel("  ·  ".join(info_parts))
        info_label.setStyleSheet("color: grey; font-size: 12px;")
        layout.addWidget(info_label)

        # Locked text editor
        self.text_edit = _LockedTextEdit(
            on_keystroke=self.on_keystroke,
            on_paste=self.on_paste,
            allow_paste=self.allow_paste,
            max_words=self.question.get("max_words"),
            monitor_input=not self.readonly,
        )
        self.text_edit.setReadOnly(self.readonly)
        self.text_edit.setMinimumHeight(200)
        self.text_edit.setStyleSheet(
            "font-size: 14px; border: 1px solid #cccccc; "
            "border-radius: 4px; padding: 8px;"
        )
        self.text_edit.textChanged.connect(self._update_word_count)
        layout.addWidget(self.text_edit, stretch=1)

        # Live word count label
        self.word_count_label = QLabel("Words: 0")
        self.word_count_label.setStyleSheet("color: grey; font-size: 12px;")
        layout.addWidget(self.word_count_label)

    def _update_word_count(self):
        text      = self.text_edit.toPlainText().strip()
        count     = len(text.split()) if text else 0
        max_words = self.question.get("max_words")

        # Colour coding
        if max_words and count > max_words:
            color = "red"
        elif max_words and count > max_words * 0.9:
            color = "orange"
        else:
            color = "grey"

        limit_str = f" / {max_words}" if max_words else ""
        self.word_count_label.setText(f"Words: {count}{limit_str}")
        self.word_count_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def get_answer(self) -> str:
        """Return the full essay text."""
        return self.text_edit.toPlainText()

    def restore_answer(self, answer_text: str):
        """Restore a previously saved essay from local cache."""
        if answer_text:
            self.text_edit.setPlainText(answer_text)

    def set_answer(self, answer_text: Optional[str]):
        self.restore_answer(str(answer_text or ""))


class _LockedTextEdit(QTextEdit):
    """
    Hardened QTextEdit for exam essay input.

    Security controls:
      - Intercepts Ctrl+V and Shift+Insert paste shortcuts
      - Reports paste attempt via callback regardless of allow_paste setting
      - Blocks paste if allow_paste is False
      - Enforces max word count — new characters blocked at limit
      - Fires keystroke callback on every key for cadence analysis
    """

    # Keys allowed even when at word limit
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
        on_paste:     Callable[[int], None],
        allow_paste:  bool,
        max_words:    Optional[int],
        monitor_input: bool = True,
    ):
        super().__init__()
        self.on_keystroke = on_keystroke
        self.on_paste     = on_paste
        self.allow_paste  = allow_paste
        self.max_words    = max_words
        self.monitor_input = monitor_input

    def keyPressEvent(self, event: QKeyEvent):
        if self.isReadOnly():
            super().keyPressEvent(event)
            return

        # ── Paste interception ─────────────────────────────────────────────
        is_paste = (
            (
                event.modifiers() == Qt.KeyboardModifier.ControlModifier
                and event.key() == Qt.Key.Key_V
            ) or (
                event.modifiers() == Qt.KeyboardModifier.ShiftModifier
                and event.key() == Qt.Key.Key_Insert
            )
        )

        if is_paste:
            clipboard_text = QApplication.clipboard().text()
            if self.monitor_input:
                self.on_paste(len(clipboard_text))
            if not self.allow_paste:
                return  # Block paste — do not call super()

        # ── Word limit enforcement ─────────────────────────────────────────
        if self.max_words and event.key() not in self._NAVIGATION_KEYS:
            # Only block if this key would add new content (not control chars)
            if event.text() and not event.modifiers():
                current_words = len(self.toPlainText().split())
                if current_words >= self.max_words:
                    # At limit — block new character input
                    # Still fire keystroke callback for cadence tracking
                    if self.monitor_input:
                        self.on_keystroke()
                    return

        # ── Keystroke cadence reporting ────────────────────────────────────
        if self.monitor_input:
            self.on_keystroke()
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """
        Also intercept drag-and-drop paste (bypasses keyPressEvent).
        Report and optionally block.
        """
        text = source.text() if source.hasText() else ""
        if self.monitor_input:
            self.on_paste(len(text))
        if self.allow_paste:
            super().insertFromMimeData(source)
        # If not allow_paste — drop the paste silently
