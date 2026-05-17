from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────
#  SEPP Dashboard — Design Tokens
#  Match these to the reference screenshot.
# ─────────────────────────────────────────────────────────

# Sidebar
SIDEBAR_BG       = "#0b1a2e"
SIDEBAR_HOVER    = "#152644"
SIDEBAR_ACTIVE   = "#1e3a62"
SIDEBAR_TEXT     = "#7a92ad"
SIDEBAR_TEXT_ACT = "#ffffff"

# Exam hero card
EXAM_CARD_BG     = "#1a2d4e"
TIMER_BOX_BG     = "#253d5e"
EXAM_TITLE_CLR   = "#7eb8f7"
EXAM_BODY_CLR    = "#b0c8e0"

# App chrome
TOP_BAR_BG       = "#ffffff"
MAIN_BG          = "#f0f2f5"
CARD_BG          = "#ffffff"

# Accents
ACCENT_YELLOW    = "#f0a500"
ACCENT_YELLOW_H  = "#d99400"
ACCENT_GREEN     = "#22c55e"
ACCENT_RED       = "#ef4444"

# Text
TEXT_PRIMARY     = "#0d1b2e"
TEXT_SECONDARY   = "#6b7280"
TEXT_MUTED       = "#9ca3af"

# Misc
BORDER_COLOR     = "#e5e7eb"
PROGRESS_BG      = "#e8eaed"
PROGRESS_FILL    = "#1a2d4e"

# Sizes
SIDEBAR_WIDTH    = 232
TOP_BAR_HEIGHT   = 56
CARD_RADIUS      = 10

_ACTIONS: list[tuple[str, str, str]] = [
    ("🔧", "Run System Diagnostic",  "Check hardware compatibility"),
    ("🔄", "Re-verify Identity",      "Update biometric baseline"),
    ("⏱",  "Access Sandbox",          "Practice with the interface"),
]


# ──────────────────────────────────────────────────────────────────────────────
class _ActionItem(QWidget):
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, subtitle: str) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._title = title
        self.setFixedHeight(64)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._normal_style = f"""
            _ActionItem {{
                background: #f7f8fa;
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
            }}
        """
        self._hover_style = f"""
            _ActionItem {{
                background: #eef0f4;
                border: 1px solid #d0d5dd;
                border-radius: 8px;
            }}
        """
        self.setStyleSheet(self._normal_style)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)

        # Icon bubble
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            background: {BORDER_COLOR};
            border-radius: 18px;
            font-size: 15px;
        """)

        # Text column
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:13px; font-weight:600; background:transparent;"
        )

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:11px; background:transparent;"
        )

        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)

        arrow = QLabel("›")
        arrow.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:20px; font-weight:300; background:transparent;"
        )

        lay.addWidget(icon_lbl)
        lay.addLayout(text_col, stretch=1)
        lay.addWidget(arrow)

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit(self._title)
        super().mousePressEvent(event)

    def enterEvent(self, event):  # noqa: N802
        self.setStyleSheet(self._hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self.setStyleSheet(self._normal_style)
        super().leaveEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
class QuickActions(QWidget):
    action_triggered = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QuickActions {{
                background: {CARD_BG};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        lightning = QLabel("⚡")
        lightning.setStyleSheet("font-size:15px; background:transparent;")
        title_lbl = QLabel("Quick Actions")
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:17px; font-weight:700; background:transparent;"
        )
        hdr.addWidget(lightning)
        hdr.addSpacing(4)
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        root.addLayout(hdr)
        root.addSpacing(2)

        # Action rows
        for icon, title, subtitle in _ACTIONS:
            item = _ActionItem(icon, title, subtitle)
            item.clicked.connect(self.action_triggered)
            root.addWidget(item)

        root.addStretch()
