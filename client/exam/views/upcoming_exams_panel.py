from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
)
from PySide6.QtCore import Qt, Signal

from client.exam.views.exam_card_widget import ExamCardWidget

# ─────────────────────────────────────────────────────────────────────────────
#  UpcomingExamsPanel
#  Wraps N ExamCardWidgets in a QScrollArea fixed to show 3 cards at a time.
#  Additional exams are reachable by scrolling vertically.
#
#  Public API
#  ----------
#  set_exams(exams: list[dict])   — clears and rebuilds all cards
#  set_loading()                  — shows a single loading placeholder
#  set_error(message: str)        — shows an inline error label
#
#  Signals re-emitted upward from child cards:
#  check_in_requested(exam_id)
#  view_details_requested(exam_id)
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED     = "#9ca3af"

# Approximate rendered height per card (px) — adjust if needed after first run.
_CARD_HEIGHT    = 118
_CARD_SPACING   = 10
CARD_RADIUS    = 10
_VISIBLE_CARDS  = 3
_SCROLL_HEIGHT  = _CARD_HEIGHT * _VISIBLE_CARDS + _CARD_SPACING * (_VISIBLE_CARDS - 1)


class UpcomingExamsPanel(QWidget):
    check_in_requested     = Signal(str)   # exam_id
    view_details_requested = Signal(str)   # exam_id

    def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            self.setStyleSheet(f"""
                UpcomingExamsPanel {{
                    background: {CARD_BG};
                    border: 1px solid {BORDER_COLOR};
                    border-radius: {CARD_RADIUS}px;
                }}
            """)
            self._cards: list[ExamCardWidget] = []
            self._setup_ui()
    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        # ── Section header ────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_lbl = QLabel("📅  Upcoming Exams")
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:16px; font-weight:700; background:transparent;"
        )

        self._count_badge = QLabel("0 TOTAL")
        self._count_badge.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background: #f3f4f6;
            border: 1px solid {BORDER_COLOR};
            border-radius: 10px;
            padding: 2px 10px;
            font-size: 11px;
            font-weight: 600;
        """)

        header_row.addWidget(title_lbl)
        header_row.addStretch()
        header_row.addWidget(self._count_badge)
        root.addLayout(header_row)

        # ── Scroll area ───────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setFixedHeight(_SCROLL_HEIGHT)
        self._scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 3px;
                min-height: 20px;
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

        # Inner container for cards
        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(0, 0, 6, 30)   # 6px right = scrollbar clearance and 16px bottom = spacing
        self._inner_lay.setSpacing(_CARD_SPACING)
        self._inner_lay.addStretch()

        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _clear_cards(self) -> None:
        for card in self._cards:
            self._inner_lay.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def _add_card(self, data: dict) -> None:
        card = ExamCardWidget()
        card.set_exam(data)
        card.check_in_requested.connect(self.check_in_requested)
        card.view_details_requested.connect(self.view_details_requested)
        # Insert before the trailing stretch
        self._inner_lay.insertWidget(self._inner_lay.count() - 1, card)
        self._cards.append(card)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_loading(self) -> None:
        self._clear_cards()
        placeholder = ExamCardWidget()
        placeholder.set_loading()
        self._inner_lay.insertWidget(0, placeholder)
        self._cards.append(placeholder)
        self._count_badge.setText("— TOTAL")

    def set_exams(self, exams: list[dict]) -> None:
        self._clear_cards()
        self._count_badge.setText(f"{len(exams)} TOTAL")
        for data in exams:
            self._add_card(data)

    def set_error(self, message: str) -> None:
        self._clear_cards()
        err_lbl = QLabel(f"Could not load exams: {message}")
        err_lbl.setStyleSheet(
            "color: #ef4444; font-size:13px; background:transparent; padding: 8px 0;"
        )
        err_lbl.setWordWrap(True)
        self._inner_lay.insertWidget(0, err_lbl)
        self._count_badge.setText("— TOTAL")
