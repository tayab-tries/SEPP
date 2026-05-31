from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout,
)
from PySide6.QtCore import Qt, Signal

from client.modules.assessments.assessment_exam_card import AssessmentExamCardWidget

# ─────────────────────────────────────────────────────────────────────────────
#  ExaminerAssessmentsPanel
#  Shows all exams created by the examiner in a grid or list.
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
CARD_RADIUS    = 10

class ExaminerAssessmentsPanel(QWidget):
    assessment_exam_selected = Signal(str)  # exam_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ExaminerAssessmentsPanel {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {CARD_RADIUS}px;
            }}
        """)
        self._cards: list[AssessmentExamCardWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # ── Header ────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        
        title_lbl = QLabel("📚  Your Exams")
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:18px; font-weight:700; background:transparent;"
        )

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

        header_row.addWidget(title_lbl)
        header_row.addStretch()
        header_row.addWidget(self._count_badge)
        root.addLayout(header_row)

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
        
        # We will use a grid layout for cards
        self._inner_lay = QGridLayout(self._inner)
        self._inner_lay.setContentsMargins(0, 0, 8, 20)
        self._inner_lay.setSpacing(16)
        
        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll)

    def _clear_cards(self) -> None:
        for card in self._cards:
            self._inner_lay.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        
        # Clear any remaining items in grid
        while self._inner_lay.count():
            item = self._inner_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_loading(self) -> None:
        self._clear_cards()
        self._count_badge.setText("— TOTAL")
        placeholder = AssessmentExamCardWidget()
        placeholder.set_loading()
        self._inner_lay.addWidget(placeholder, 0, 0)
        self._cards.append(placeholder)

    def set_exams(self, exams: list[dict]) -> None:
        self._clear_cards()
        self._count_badge.setText(f"{len(exams)} TOTAL")
        
        if not exams:
            empty_lbl = QLabel("No exams found.")
            empty_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._inner_lay.addWidget(empty_lbl, 0, 0)
            return

        # 2 columns grid
        row = 0
        col = 0
        for data in exams:
            card = AssessmentExamCardWidget()
            card.set_exam(data)
            card.view_assessments_requested.connect(self.assessment_exam_selected)
            self._inner_lay.addWidget(card, row, col)
            self._cards.append(card)
            
            col += 1
            if col > 1:
                col = 0
                row += 1
        
        # Add stretch row at the bottom
        self._inner_lay.setRowStretch(row + 1, 1)

    def set_error(self, message: str) -> None:
        self._clear_cards()
        self._count_badge.setText("— TOTAL")
        err_lbl = QLabel(f"Could not load exams: {message}")
        err_lbl.setStyleSheet("color: #ef4444; font-size:14px;")
        err_lbl.setWordWrap(True)
        self._inner_lay.addWidget(err_lbl, 0, 0)
