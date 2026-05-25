from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from client.Shared.info_dialog import InfoDialog

# ─────────────────────────────────────────────────────────────────────────────
#  PendingRequestCard
#  One table row per pending exam access request.
#  Starts blank; populate via set_request(data).
#
#  Signals
#  -------
#  cancel_requested(request_id: str)
#      Emitted only after the user confirms the cancellation dialog.
#
#  Status badge values
#  -------------------
#  "Awaiting Approval"  → grey badge
#  "Approved"           → green badge
#
#  Expected data dict (passed to set_request)
#  -------------------------------------------
#  {
#      "request_id":   str,
#      "exam_name":    str,
#      "exam_id":      str,
#      "request_date": str,   e.g. "Oct 20, 2023"
#      "status":       str,   "Awaiting Approval" | "Approved"
#  }
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED     = "#9ca3af"
ACCENT_GREEN   = "#22c55e"
ACCENT_RED     = "#ef4444"

_ROW_HEIGHT = 58


class PendingRequestCard(QWidget):
    cancel_requested = Signal(str)   # request_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._request_id: str = ""
        self._exam_name:  str = ""
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setFixedHeight(_ROW_HEIGHT)
        self.setStyleSheet(f"""
            PendingRequestCard {{
                background: transparent;
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)

        # ── Exam name + ID column ─────────────────────────────────────────────
        name_col = QVBoxLayout()
        name_col.setSpacing(2)

        self._name_lbl = QLabel()
        self._name_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:13px; font-weight:600; background:transparent;"
        )

        self._exam_id_lbl = QLabel()
        self._exam_id_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:11px; background:transparent;"
        )

        name_col.addWidget(self._name_lbl)
        name_col.addWidget(self._exam_id_lbl)

        name_w = QWidget()
        name_w.setStyleSheet("background: transparent;")
        name_w.setFixedWidth(220)
        name_w.setLayout(name_col)

        # ── Request date column ───────────────────────────────────────────────
        self._date_lbl = QLabel()
        self._date_lbl.setFixedWidth(120)
        self._date_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;"
        )

        # ── Status badge ──────────────────────────────────────────────────────
        self._status_badge = QLabel()
        self._status_badge.setFixedWidth(160)
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_badge.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        # ── Cancel button ─────────────────────────────────────────────────────
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedSize(64, 30)
        self._cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {ACCENT_RED};
                border: none;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

        lay.addWidget(name_w)
        lay.addWidget(self._date_lbl)
        lay.addStretch()
        lay.addWidget(self._status_badge)
        lay.addSpacing(12)
        lay.addWidget(self._cancel_btn)

    # ── Status badge styling ──────────────────────────────────────────────────

    def _apply_status_style(self, status: str) -> None:
        if status == "Approved":
            fg     = ACCENT_GREEN
            bg     = "#f0fdf4"
            border = "#bbf7d0"
        else:                          # "Awaiting Approval" or unknown
            fg     = TEXT_SECONDARY
            bg     = "#f9fafb"
            border = BORDER_COLOR

        self._status_badge.setStyleSheet(f"""
            color: {fg};
            background: {bg};
            border: 1px solid {border};
            border-radius: 12px;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 500;
        """)
        self._status_badge.setText(f"● {status}")

    # ── Cancel flow ───────────────────────────────────────────────────────────

    def _on_cancel_clicked(self) -> None:
        dlg = InfoDialog(
            title="Cancel Request",
            body=(
                f'Are you sure you want to cancel your access request for\n'
                f'"{self._exam_name}"?\n\n'
                "It will be moved back to scheduled exams."
            ),
            parent=self,
            confirm_label="Yes, Cancel",
            cancel_label="Keep",
        )
        dlg.confirmed.connect(lambda: self.cancel_requested.emit(self._request_id))
        dlg.exec_()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_request(self, data: dict) -> None:
        """Populate the row with data pushed from the page layer."""
        self._request_id = data.get("request_id", "")
        self._exam_name  = data.get("exam_name",  "Unknown Exam")
        approved = bool(data.get("approved"))

        self._name_lbl.setText(self._exam_name)
        self._exam_id_lbl.setText(f"ID: {data.get('exam_id', '—')}")
        self._date_lbl.setText(data.get("request_date", "—"))
        self._apply_status_style(data.get("status", "Awaiting Approval"))
        self._cancel_btn.setVisible(not approved)
