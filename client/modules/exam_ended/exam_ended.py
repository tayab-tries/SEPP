"""
client/modules/exam_ended/exam_ended.py

Static post-exam result screen for submitted or terminated outcomes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


_BG_PAGE = "#F0F2F5"
_BG_WHITE = "#FFFFFF"
_BORDER = "#E5E7EB"
_NAVY = "#0F2454"
_NAVY_HOVER = "#1A3A7A"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"

_GREEN_BG = "#DCFCE7"
_GREEN_ICON = "#22C55E"

_RED_BG = "#FEE2E2"
_RED_FG = "#991B1B"
_RED_ICON = "#DC2626"


class _StatCard(QFrame):
    def __init__(
        self,
        label: str,
        value: str,
        sub: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background-color: {_BG_WHITE};"
            f"border: 1px solid {_BORDER}; border-radius: 16px; }}"
        )
        self.setMinimumWidth(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label_widget = QLabel(label)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {_TXT_MUTED};"
            "letter-spacing: 1px; background: transparent;"
        )

        value_widget = QLabel(value)
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_widget.setWordWrap(True)
        value_widget.setStyleSheet(
            f"font-size: 32px; font-weight: 900; color: {_NAVY}; background: transparent;"
        )

        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        if sub:
            sub_widget = QLabel(sub)
            sub_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub_widget.setWordWrap(True)
            sub_widget.setStyleSheet(
                f"font-size: 12px; color: {_TXT_MUTED}; background: transparent;"
            )
            layout.addWidget(sub_widget)


class ExamEndedScreen(QWidget):
    done = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {_BG_PAGE};")
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        topbar = QWidget()
        topbar.setFixedHeight(56)
        topbar.setStyleSheet(
            f"background-color: {_BG_WHITE}; border-bottom: 1px solid {_BORDER};"
        )
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(24, 0, 24, 0)
        brand = QLabel("SEPP")
        brand.setStyleSheet(
            f"font-size: 18px; font-weight: 900; color: {_NAVY}; background: transparent;"
        )
        topbar_layout.addWidget(brand)
        topbar_layout.addStretch(1)
        outer.addWidget(topbar)

        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setContentsMargins(40, 60, 40, 60)
        center_layout.setSpacing(32)

        self._icon_circle = QLabel()
        self._icon_circle.setFixedSize(100, 100)
        self._icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._headline = QLabel()
        self._headline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtext = QLabel()
        self._subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtext.setWordWrap(True)
        self._subtext.setStyleSheet(
            f"font-size: 15px; color: {_TXT_MUTED}; background: transparent;"
        )

        center_layout.addWidget(self._icon_circle, 0, Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self._headline)
        center_layout.addWidget(self._subtext)

        self._stats_row = QWidget()
        self._stats_row.setStyleSheet("background: transparent;")
        self._stats_layout = QHBoxLayout(self._stats_row)
        self._stats_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stats_layout.setSpacing(16)
        self._stats_row.hide()
        center_layout.addWidget(self._stats_row)

        self._notice_card = self._build_notice_card()
        center_layout.addWidget(self._notice_card)

        self._return_btn = QPushButton("Return to Dashboard")
        self._return_btn.setFixedHeight(50)
        self._return_btn.setFixedWidth(260)
        self._return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._return_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {_NAVY};
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 15px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: {_NAVY_HOVER};
            }}
            """
        )
        self._return_btn.clicked.connect(self.done)
        center_layout.addWidget(self._return_btn, 0, Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(center, 1)
        self.set_result("submitted")

    def _build_notice_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {_BG_WHITE};"
            f"border: 1px solid {_BORDER}; border-radius: 16px; }}"
        )
        card.setMaximumWidth(520)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)

        for text in (
            "Submission data has been saved locally.",
            "Session recording is queued for review.",
            "Results will be published after grading.",
        ):
            label = QLabel(text)
            label.setStyleSheet(
                f"font-size: 13px; color: {_TXT_MUTED}; background: transparent;"
            )
            layout.addWidget(label)

        return card

    def set_result(
        self,
        outcome: str,
        *,
        mcq_score: int | None = None,
        total_marks: int | None = None,
        exam_name: str = "",
        duration_taken: str = "",
    ) -> None:
        is_submitted = outcome == "submitted"

        self._set_icon(outcome)
        self._headline.setStyleSheet(
            f"font-size: 30px; font-weight: 900; color: {(_TXT if is_submitted else _RED_FG)}; background: transparent;"
        )
        self._notice_card.setVisible(is_submitted)

        if is_submitted:
            self._headline.setText("Exam Submitted Successfully")
            self._subtext.setText(
                "Your answers have been securely submitted.\n"
                "Results will be available once grading is complete."
            )
        else:
            self._headline.setText("Session Terminated")
            self._subtext.setText(
                "Your session was terminated by the proctor or system.\n"
                "Please contact your examiner for further information."
            )

        self._clear_stats()
        if mcq_score is not None and total_marks is not None:
            self._stats_layout.addWidget(
                _StatCard("MCQ SCORE", f"{mcq_score}", f"out of {total_marks}")
            )
        if duration_taken:
            self._stats_layout.addWidget(_StatCard("TIME TAKEN", duration_taken))
        if exam_name:
            self._stats_layout.addWidget(_StatCard("EXAM", exam_name))

        self._stats_row.setVisible(self._stats_layout.count() > 0)

    def _set_icon(self, outcome: str) -> None:
        if outcome == "submitted":
            self._icon_circle.setText("✓")
            self._icon_circle.setStyleSheet(
                f"background-color: {_GREEN_BG}; color: {_GREEN_ICON};"
                "border-radius: 50px; font-size: 42px; font-weight: 900;"
            )
            return
        self._icon_circle.setText("✕")
        self._icon_circle.setStyleSheet(
            f"background-color: {_RED_BG}; color: {_RED_ICON};"
            "border-radius: 50px; font-size: 42px; font-weight: 900;"
        )

    def _clear_stats(self) -> None:
        while self._stats_layout.count():
            item = self._stats_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
