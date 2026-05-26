from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

# ─────────────────────────────────────────────────────────
#  SEPP Dashboard — Design Tokens
#  Match these to the reference screenshot.
# ─────────────────────────────────────────────────────────

# Sidebar
SIDEBAR_BG       = "#EAECF2"
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


_NAV_ITEMS: list[tuple[str, str]] = [
    ("⊞", "Dashboard"),
    ("☰", "Exams"),
    ("◎", "Monitoring"),
    ("▦", "Reports"),
    ("⚙", "Settings"),
]


# ──────────────────────────────────────────────────────────────────────────────
class _NavItem(QWidget):
    """Single sidebar navigation row."""

    clicked = Signal(str)

    def __init__(self, icon: str, label: str, active: bool = False) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._label  = label
        self._active = active
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(42)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._text_lbl = QLabel(label)

        lay.addWidget(self._icon_lbl)
        lay.addWidget(self._text_lbl)
        lay.addStretch()

        self._repaint()

    # ── styling ──────────────────────────────────────────────────────────

    def _repaint(self) -> None:
        bg  = SIDEBAR_ACTIVE   if self._active else "transparent"
        fg  = SIDEBAR_TEXT_ACT if self._active else SIDEBAR_TEXT
        fw  = "600"               if self._active else "400"
        self.setStyleSheet(f"QWidget {{ background: {bg}; border-radius: 8px; }}")
        self._icon_lbl.setStyleSheet(
            f"color:{fg}; background:transparent; font-size:14px;"
        )
        self._text_lbl.setStyleSheet(
            f"color:{fg}; background:transparent; font-size:13px; font-weight:{fw};"
        )

    def set_active(self, active: bool) -> None:
        self._active = active
        self._repaint()

    # ── events ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit(self._label)
        super().mousePressEvent(event)

    def enterEvent(self, event):  # noqa: N802
        if not self._active:
            self.setStyleSheet(
                f"QWidget {{ background:{SIDEBAR_HOVER}; border-radius:8px; }}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._repaint()
        super().leaveEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
class SidebarWidget(QWidget):
    nav_clicked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"background: {SIDEBAR_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 0, 10, 16)
        root.setSpacing(0)

        # ── Logo area ────────────────────────────────────────────────────
        logo_w = QWidget()
        logo_w.setFixedHeight(76)
        logo_w.setStyleSheet("background: transparent;")
        logo_lay = QHBoxLayout(logo_w)
        logo_lay.setContentsMargins(8, 0, 8, 0)
        logo_lay.setSpacing(10)

        shield = QLabel("🛡")
        shield.setFixedSize(38, 38)
        shield.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield.setStyleSheet(
            "background: #1e4d8c; border-radius: 9px; font-size: 18px; color: white;"
        )

        name_col = QVBoxLayout()
        name_col.setSpacing(0)
        name_lbl = QLabel("SEPP Secure")
        name_lbl.setStyleSheet(
            "color:white; font-size:13px; font-weight:700; background:transparent; margin-bottom:0px;"
        )
        ver_lbl = QLabel("v2.4.0 Active")
        ver_lbl.setStyleSheet(
            f"color:{SIDEBAR_TEXT}; font-size:11px; background:transparent; margin-bottom:0px;"
        )
        name_col.addWidget(name_lbl)
        name_col.addWidget(ver_lbl)

        logo_lay.addWidget(shield)
        logo_lay.addLayout(name_col)
        logo_lay.addStretch()
        root.addWidget(logo_w)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {SIDEBAR_HOVER};")
        root.addWidget(div)
        root.addSpacing(8)

        # ── Nav items ────────────────────────────────────────────────────
        self._nav_items: list[_NavItem] = []
        for icon, label in _NAV_ITEMS:
            item = _NavItem(icon, label, active=(label == "Dashboard"))
            item.clicked.connect(self._on_item_clicked)
            self._nav_items.append(item)
            root.addWidget(item)
            root.addSpacing(2)

        root.addStretch()

        # ── Live Support ─────────────────────────────────────────────────
        support_btn = QPushButton("  💬  Live Support")
        support_btn.setFixedHeight(42)
        support_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        support_btn.setStyleSheet("""
            QPushButton {
                background: #1e4d8c;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2563ab; }
        """)
        root.addWidget(support_btn)
        root.addSpacing(14)

        # ── Help / Sign Out ───────────────────────────────────────────────
        root.addWidget(self._bottom_btn("?   Help"))
        root.addSpacing(2)
        root.addWidget(self._bottom_btn("⎋   Sign Out", red=True))

    # ── helpers ──────────────────────────────────────────────────────────

    def _bottom_btn(self, text: str, red: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        fg  = "#ef4444" if red else SIDEBAR_TEXT
        fgh = "#f87171" if red else "#ffffff"
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {fg};
                border: none;
                text-align: left;
                padding-left: 14px;
                font-size: 13px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {SIDEBAR_HOVER};
                color: {fgh};
            }}
        """)
        return btn

    def _on_item_clicked(self, label: str) -> None:
        self.set_active_label(label)
        self.nav_clicked.emit(label)

    def set_active_label(self, label: str) -> None:
        for item in self._nav_items:
            item.set_active(item._label == label)
