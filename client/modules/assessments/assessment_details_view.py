from typing import Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from client.dashboard.views.sidebar import MAIN_BG
from client.modules.assessments.assessment_attempt_card import AssessmentAttemptCardWidget

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"

class AssessmentDetailsView(QWidget):
    back_requested = Signal()
    view_logs_requested = Signal(str)    # session_id
    grade_attempt_requested = Signal(str) # session_id

    def __init__(self, apply_shadow: Callable[[QWidget], None], parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {MAIN_BG};")
        self._cards: list[AssessmentAttemptCardWidget] = []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)
        
        # Simple header with back button
        header_row = QVBoxLayout()
        header_row.setSpacing(12)
        self._back_btn = QPushButton("← Back to Assessments")
        self._back_btn.setFixedWidth(180)
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #3b82f6;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #eff6ff; }
        """)
        self._back_btn.clicked.connect(self.back_requested)
        header_row.addWidget(self._back_btn)
        
        title_row = QHBoxLayout()
        self._title_lbl = QLabel("Assessment Details")
        self._title_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #0d1b2e;")
        
        self._count_badge = QLabel("0 TOTAL")
        self._count_badge.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background: #f3f4f6;
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 600;
        """)

        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._count_badge)
        header_row.addLayout(title_row)
        layout.addLayout(header_row)

        # ── Scroll area ───────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        
        # Layout for cards
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(0, 0, 8, 20)
        self._inner_lay.setSpacing(16)
        self._inner_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self._scroll.setWidget(self._inner)
        layout.addWidget(self._scroll, stretch=1)

    def _clear_cards(self) -> None:
        for card in self._cards:
            self._inner_lay.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        
        while self._inner_lay.count():
            item = self._inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_loading(self) -> None:
        self._clear_cards()
        self._count_badge.setText("— TOTAL")
        placeholder = AssessmentAttemptCardWidget()
        placeholder.set_loading()
        self._inner_lay.addWidget(placeholder)
        self._cards.append(placeholder)

    def set_sessions(self, sessions: list[dict]) -> None:
        self._clear_cards()
        self._count_badge.setText(f"{len(sessions)} TOTAL")
        
        if not sessions:
            empty_lbl = QLabel("No students have attempted this exam yet.")
            empty_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._inner_lay.addWidget(empty_lbl)
            return

        for data in sessions:
            card = AssessmentAttemptCardWidget()
            card.set_attempt(data)
            card.view_logs_requested.connect(self.view_logs_requested)
            card.grade_attempt_requested.connect(self.grade_attempt_requested)
            self._inner_lay.addWidget(card)
            self._cards.append(card)

    def set_error(self, message: str) -> None:
        self._clear_cards()
        self._count_badge.setText("— TOTAL")
        err_lbl = QLabel(f"Could not load student attempts: {message}")
        err_lbl.setStyleSheet("color: #ef4444; font-size:14px;")
        err_lbl.setWordWrap(True)
        self._inner_lay.addWidget(err_lbl)

    def set_exam_context(self, exam_id: str):
        self._exam_id = exam_id
        self._title_lbl.setText(f"Assessment Details for Exam ID: {exam_id}")
