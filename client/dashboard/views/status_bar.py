from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer

from client.dashboard.services.api_client import ApiClient

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


class _Dot(QLabel):
    """Colored ● indicator dot."""

    def __init__(self, active: bool = True) -> None:
        super().__init__("●")
        self.setStyleSheet("background: transparent;")
        self.set_active(active)

    def set_active(self, active: bool) -> None:
        color = ACCENT_GREEN if active else ACCENT_RED
        self.setStyleSheet(f"color:{color}; font-size:10px; background:transparent;")


class StatusBarWidget(QWidget):
    """
    Bottom status bar.
    Shows camera and network status.  Refreshes every 30 s via the API.
    Microphone is intentionally excluded per product spec.
    """

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._api = api
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            StatusBarWidget {{
                background: {CARD_BG};
                border-radius: {CARD_RADIUS}px;
                border: 1px solid {BORDER_COLOR};
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(8)

        # Camera
        self._cam_dot = _Dot(True)
        self._cam_lbl = QLabel("Camera: Active")
        self._cam_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;"
        )

        lay.addWidget(self._cam_dot)
        lay.addWidget(self._cam_lbl)
        lay.addSpacing(20)

        # Network
        self._net_dot = _Dot(True)
        self._net_lbl = QLabel("Network: Stable (24ms)")
        self._net_lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;"
        )

        lay.addWidget(self._net_dot)
        lay.addWidget(self._net_lbl)
        lay.addStretch()

        # Last scan (right-aligned)
        self._scan_lbl = QLabel("Last Hardware Scan: 2 minutes ago")
        self._scan_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:12px; background:transparent;"
        )
        lay.addWidget(self._scan_lbl)

        # Poll every 30 s
        self._poll = QTimer(self)
        self._poll.timeout.connect(self.refresh)
        self._poll.start(30_000)
        self.refresh()

    def refresh(self) -> None:
        """Pull fresh status from the API and update the UI."""
        status = self._api.get_system_status()

        cam = status.get("camera", {})
        self._cam_dot.set_active(cam.get("active", False))
        self._cam_lbl.setText(f"Camera: {cam.get('label', 'Unknown')}")

        net = status.get("network", {})
        self._net_dot.set_active(net.get("stable", False))
        ms  = net.get("latency_ms", 0)
        self._net_lbl.setText(f"Network: {net.get('label', 'Unknown')} ({ms}ms)")

        self._scan_lbl.setText(f"Last Hardware Scan: {status.get('last_scan', 'Unknown')}")
