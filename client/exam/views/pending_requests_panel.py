from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal

from client.exam.views.pending_request_card import PendingRequestCard

# ─────────────────────────────────────────────────────────────────────────────
#  PendingRequestsPanel
#  Wraps a table header row and N PendingRequestCard rows.
#
#  Public API
#  ----------
#  set_requests(requests: list[dict])   — clears and rebuilds all rows
#  add_request(data: dict)              — appends one new row (after join success)
#  remove_request(request_id: str)      — removes a row (after cancel confirmed)
#  set_loading()                        — shows loading state
#
#  Signals re-emitted upward:
#  cancel_requested(request_id: str)
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
CARD_RADIUS    = 10
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED     = "#9ca3af"


class PendingRequestsPanel(QWidget):
    cancel_requested = Signal(str)   # request_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # request_id → PendingRequestCard
        self._cards: dict[str, PendingRequestCard] = {}
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            PendingRequestsPanel {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(2, 16, 2, 0)
        root.setSpacing(0)

        # ── Section header ────────────────────────────────────────────────────
        section_hdr = QHBoxLayout()
        section_hdr.setContentsMargins(16, 0, 16, 10)
        section_hdr.setSpacing(8)

        icon_lbl = QLabel("⏳")
        icon_lbl.setStyleSheet("font-size:14px; background:transparent;")

        title_lbl = QLabel("Pending Access Requests")
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:16px; font-weight:700; background:transparent;"
        )

        section_hdr.addWidget(icon_lbl)
        section_hdr.addWidget(title_lbl)
        section_hdr.addStretch()
        root.addLayout(section_hdr)

        # ── Table header row ──────────────────────────────────────────────────
        table_hdr = QWidget()
        table_hdr.setStyleSheet("background: transparent; border: none;")
        
        hdr_lay = QHBoxLayout(table_hdr)
        hdr_lay.setContentsMargins(16, 8, 16, 8)
        hdr_lay.setSpacing(0)

        col_specs = [("Exam Name", 220), ("Request Date", 120)]
        for col_text, width in col_specs:
            lbl = QLabel(col_text)
            lbl.setFixedWidth(width)
            lbl.setStyleSheet(
                f"color:{TEXT_MUTED}; font-size:12px; font-weight:600; background:transparent;"
            )
            hdr_lay.addWidget(lbl)

        hdr_lay.addStretch()

        status_hdr = QLabel("Status")
        status_hdr.setFixedWidth(160)
        status_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_hdr.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:12px; font-weight:600; background:transparent;"
        )
        hdr_lay.addWidget(status_hdr)
        hdr_lay.addSpacing(76)   # aligns with Cancel button + its left spacing
        root.addWidget(table_hdr)

        # ── Cards container ───────────────────────────────────────────────────
        self._cards_w = QWidget()
        self._cards_w.setStyleSheet("background: transparent;")
        self._cards_lay = QVBoxLayout(self._cards_w)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        self._cards_lay.setSpacing(0)
        root.addWidget(self._cards_w)

        # ── Empty / loading state label ───────────────────────────────────────
        self._state_lbl = QLabel("No pending access requests.")
        self._state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:13px; background:transparent; padding: 20px 0;"
        )
        root.addWidget(self._state_lbl)
        self._state_lbl.hide()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _clear_all(self) -> None:
        for card in list(self._cards.values()):
            self._cards_lay.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

    def _add_card(self, data: dict) -> None:
        card = PendingRequestCard()
        card.set_request(data)
        card.cancel_requested.connect(self.cancel_requested)
        request_id = data.get("request_id", "")
        self._cards[request_id] = card
        self._cards_lay.addWidget(card)

    def _refresh_state_label(self) -> None:
        """Show empty state label only when there are no cards."""
        self._state_lbl.setText("No pending access requests.")
        self._state_lbl.setVisible(len(self._cards) == 0)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_loading(self) -> None:
        self._clear_all()
        self._state_lbl.setText("Loading…")
        self._state_lbl.show()

    def set_error(self, message: str) -> None:
        self._clear_all()
        self._state_lbl.setText(f"Could not load requests: {message}")
        self._state_lbl.show()

    def set_requests(self, requests: list[dict]) -> None:
        self._clear_all()
        for data in requests:
            self._add_card(data)
        self._refresh_state_label()

    def add_request(self, data: dict) -> None:
        """Append a newly approved pending request (called after join-exam success)."""
        self._add_card(data)
        self._refresh_state_label()

    def remove_request(self, request_id: str) -> None:
        """Remove a row after a cancel has been confirmed and processed."""
        card = self._cards.pop(request_id, None)
        if card:
            self._cards_lay.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._refresh_state_label()
