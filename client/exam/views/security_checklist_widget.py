from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from client.Shared.info_dialog import InfoDialog

# ─────────────────────────────────────────────────────────────────────────────
#  SecurityChecklistWidget
#  Purely visual card. All content is hardcoded / static.
#  No signals. No public set_* API.
#
#  "Run System Diagnostics" button opens an InfoDialog that states
#  the feature is not yet available.
#
#  Checklist items
#  ---------------
#  ✅  Identity Verified    — green
#  ✅  Environment Clear    — green
#  ⚠️  Update Browser       — warning / red subtitle
# ─────────────────────────────────────────────────────────────────────────────

CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
CARD_RADIUS    = 10
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED     = "#9ca3af"
ACCENT_GREEN   = "#22c55e"
ACCENT_RED     = "#ef4444"
ACCENT_YELLOW  = "#f0a500"

_ITEMS = [
    {
        "icon":     "✅",
        "title":    "Identity Verified",
        "subtitle": "Your biometric data is active and ready for proctoring.",
        "ok":       True,
    },
    {
        "icon":     "✅",
        "title":    "Environment Clear",
        "subtitle": "360° scan performed within the last 24 hours.",
        "ok":       True,
    },
    {
        "icon":     "⚠️",
        "title":    "Update Browser",
        "subtitle": "SE-Browser update v4.2 required for upcoming exams.",
        "ok":       False,
    },
]


class SecurityChecklistWidget(QWidget):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            SecurityChecklistWidget {{
                background: {CARD_BG};
                border: 1px solid {BORDER_COLOR};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)
        hdr_row.setContentsMargins(0, 0, 0, 12)

        shield_lbl = QLabel("🛡")
        shield_lbl.setStyleSheet("font-size:14px; background:transparent;")

        hdr_lbl = QLabel("SECURITY CHECKLIST")
        hdr_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:11px; font-weight:700; "
            f"letter-spacing:1px; background:transparent;"
        )

        hdr_row.addWidget(shield_lbl)
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        root.addLayout(hdr_row)

        # ── Checklist items ───────────────────────────────────────────────────
        for i, item in enumerate(_ITEMS):
            root.addWidget(self._build_item(item))

            if i < len(_ITEMS) - 1:
                div = QFrame()
                div.setFixedHeight(1)
                div.setStyleSheet(f"background:{BORDER_COLOR};")
                root.addWidget(div)

        root.addSpacing(14)

        # ── Run System Diagnostics button ─────────────────────────────────────
        diag_btn = QPushButton("Run System Diagnostics")
        diag_btn.setFixedHeight(36)
        diag_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        diag_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: #f9fafb; }}
        """)
        diag_btn.clicked.connect(self._on_diagnostics)
        root.addWidget(diag_btn)

    def _build_item(self, item: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        w.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout(w)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        icon = QLabel(item["icon"])
        icon.setFixedWidth(22)
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        icon.setStyleSheet("font-size:16px; background:transparent;")

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_lbl = QLabel(item["title"])
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:13px; font-weight:600; background:transparent;"
        )

        subtitle_color = ACCENT_RED if not item["ok"] else TEXT_SECONDARY
        sub_lbl = QLabel(item["subtitle"])
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(
            f"color:{subtitle_color}; font-size:12px; background:transparent;"
        )

        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)

        row.addWidget(icon)
        row.addLayout(text_col)
        return w

    # ── Slot ──────────────────────────────────────────────────────────────────

    def _on_diagnostics(self) -> None:
        dlg = InfoDialog(
            title="System Diagnostics",
            body=(
                "System Diagnostics is not yet available.\n\n"
                "This feature will be enabled in a future release of SecureExam. "
                "Please check back after your next application update."
            ),
            parent=self,
        )
        dlg.exec_()
