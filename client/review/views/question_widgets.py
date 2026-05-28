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
    QHBoxLayout,
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
    def __init__(self, question: dict, answer: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.question = dict(question or {})
        self.answer = dict(answer or {})
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

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)

        q_type = question_type_value(self.question).upper() or "QUESTION"
        meta_left = QLabel(q_type)
        meta_left.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:12px; font-weight:700;")
        meta_layout.addWidget(meta_left)
        
        meta_layout.addStretch()

        marks = self.question.get("marks", 1.0)
        score = self.answer.get("examiner_score")
        
        if score is not None:
            score_text = f"Grade: {score} / {marks}"
        else:
            if q_type == "MCQ":
                is_correct = self.answer.get("is_correct")
                if is_correct is True:
                    score_text = f"Grade: {marks} / {marks}"
                elif is_correct is False:
                    score_text = f"Grade: 0 / {marks}"
                else:
                    score_text = f"Grade: Not graded / {marks}"
            else:
                score_text = f"Grade: Not graded / {marks}"
        
        meta_right = QLabel(score_text)
        meta_right.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:14px; font-weight:800;")
        meta_layout.addWidget(meta_right)

        self.root.addLayout(meta_layout)

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

    def get_answer(self):
        return None

    def restore_answer(self, value):
        pass


class MCQOptionButton(QRadioButton):
    def __init__(self, key: str, text: str, parent=None) -> None:
        super().__init__(f"{key}. {text}", parent)
        self.option_key = key
        self.setMinimumHeight(48)
        self.setWordWrap(True) if hasattr(self, "setWordWrap") else None
        # Base styling for review mode (read only)
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
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)


class MCQQuestionWidget(BaseQuestionWidget):
    """Single-answer MCQ widget for review mode."""

    def __init__(self, question: dict, answer: dict | None = None, parent=None) -> None:
        super().__init__(question, answer, parent)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons: dict[str, MCQOptionButton] = {}

        options = self.question.get("options") or []
        correct_option = self.question.get("correct_option")
        selected_option = self.answer.get("selected_option")

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
            
            # Disable interaction
            btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            if selected_option == key:
                btn.setChecked(True)

            # Apply highlights
            if key == correct_option:
                btn.setStyleSheet(f"""
                    QRadioButton {{
                        background: #dcfce7; /* Light green */
                        border: 1px solid #22c55e;
                        border-radius: 10px;
                        padding: 13px 14px;
                        color: #166534;
                        font-size: 14px;
                        font-weight: 700;
                        spacing: 10px;
                    }}
                    QRadioButton::indicator {{ width: 16px; height: 16px; }}
                """)
            elif key == selected_option and key != correct_option:
                btn.setStyleSheet(f"""
                    QRadioButton {{
                        background: #fee2e2; /* Light red */
                        border: 1px solid #ef4444;
                        border-radius: 10px;
                        padding: 13px 14px;
                        color: #991b1b;
                        font-size: 14px;
                        font-weight: 700;
                        spacing: 10px;
                    }}
                    QRadioButton::indicator {{ width: 16px; height: 16px; }}
                """)

            self.group.addButton(btn)
            self._buttons[key] = btn
            options_lay.addWidget(btn)

        if not options:
            empty = QLabel("No options were provided for this MCQ.")
            empty.setStyleSheet(f"color:{TEXT_MUTED}; font-size:13px;")
            options_lay.addWidget(empty)

        self.root.addWidget(options_container)
        self.root.addStretch(1)

    def restore_answer(self, value: str | None) -> None:
        pass


class AutoResizeTextEdit(QTextEdit):
    def __init__(self, min_height: int = 180, max_height: int = 420, parent=None) -> None:
        super().__init__(parent)
        self.min_height = min_height
        self.max_height = max_height
        self.setAcceptRichText(False)
        self.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.setMinimumHeight(min_height)
        self.setFixedHeight(min_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: #f8fafc;
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
                padding: 12px;
                color: {TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.45;
            }}
        """)
        self.document().contentsChanged.connect(self._schedule_resize)

    def _schedule_resize(self) -> None:
        QTimer.singleShot(0, self._resize_to_document)

    def _resize_to_document(self) -> None:
        doc_height = int(self.document().size().height()) + 34
        new_height = max(self.min_height, min(doc_height, self.max_height))
        if new_height != self.height():
            self.setFixedHeight(new_height)


class EssayQuestionWidget(BaseQuestionWidget):
    def __init__(self, question: dict, answer: dict | None = None, parent=None) -> None:
        super().__init__(question, answer, parent)

        self.word_limits_label = QLabel(self._limits_text(word_count(self.answer.get("answer_text", ""))))
        self.word_limits_label.setWordWrap(True)
        self.word_limits_label.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size:12px; font-weight:700;")
        self.root.addWidget(self.word_limits_label)

        self.editor = AutoResizeTextEdit()
        self.editor.setPlainText(self.answer.get("answer_text", ""))
        self.root.addWidget(self.editor)
        self.root.addStretch(1)
        
        QTimer.singleShot(50, self.editor._resize_to_document)

    def _limits_text(self, count: int) -> str:
        min_words = self.question.get("min_words")
        max_words = self.question.get("max_words")
        parts = [f"Words: {count}"]
        if min_words is not None:
            parts.append(f"Minimum: {min_words}")
        if max_words is not None:
            parts.append(f"Maximum: {max_words}")
        return "  •  ".join(parts)

    def restore_answer(self, value: str | None) -> None:
        pass
