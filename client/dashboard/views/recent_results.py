from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

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


# ──────────────────────────────────────────────────────────────────────────────
class _ResultItem(QWidget):
    """Single result entry: date, title, score, progress bar, divider."""

    def __init__(self, data: dict) -> None:
        super().__init__()
        self.setMinimumHeight(72)
        self.setMaximumHeight(72)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 4)
        root.setSpacing(4)

        # Date
        date_lbl = QLabel(data.get("date", ""))
        date_lbl.setStyleSheet(
            f"color:{TEXT_MUTED}; font-size:9px; font-weight:500; background:transparent;"
        )

        # Title + score column
        row = QHBoxLayout()
        row.setSpacing(8)

        title_lbl = QLabel(data.get("title", ""))
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:12px; font-weight:700; background:transparent;"
        )
        
        title_lbl.setWordWrap(False)
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        score = int(data.get("score", 0) or 0)
        status = data.get("status_label") or data.get("status", "")

        score_lbl = QLabel(f"{score}%")
        score_lbl.setFixedSize(52, 18)
        score_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        score_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:14px; font-weight:800; background:transparent;"
        )

        status_lbl = QLabel(status.upper())
        status_lbl.setFixedSize(52, 12)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_lbl.setStyleSheet(
            f"color:{ACCENT_GREEN}; font-size:9px; font-weight:800; background:transparent;"
        )

        score_col = QVBoxLayout()
        score_col.setSpacing(2)
        score_col.setContentsMargins(0, 0, 0, 0)
        score_col.addWidget(score_lbl)
        score_col.addWidget(status_lbl)
        score_col.addStretch()

        row.addWidget(title_lbl, stretch=1)
        row.addSpacing(10)
        row.addLayout(score_col)

        # Progress bar
        bar = QProgressBar()
        bar.setFixedHeight(6)
        bar.setMaximum(100)
        bar.setValue(max(0, min(100, score)))
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {PROGRESS_BG};
                border-radius: 3px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {PROGRESS_FILL};
                border-radius: 3px;
            }}
        """)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"color: {BORDER_COLOR};")

        root.addWidget(date_lbl)
        root.addLayout(row)
        root.addWidget(bar)
        root.addWidget(div)


# ──────────────────────────────────────────────────────────────────────────────
class RecentResults(QWidget):

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        # self.setMinimumHeight(285)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._api = api
        self.setStyleSheet(f"""
            RecentResults {{
                background: {CARD_BG};
                border-radius: {CARD_RADIUS}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 10)
        root.setSpacing(0)

        title_lbl = QLabel("Recent Results")
        title_lbl.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:700; background:transparent;"
        )
        root.addWidget(title_lbl)

        self._scroll = QScrollArea()
        self._scroll.setFixedHeight(170)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }

            QScrollBar::handle:vertical {
                background: #D1D5DB;
                border-radius: 3px;
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

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")

        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 6, 10, 0)
        self._list_lay.setSpacing(0)

        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll, stretch=1)

        root.addSpacing(10)
        # Download button
        dl_btn = QPushButton("Download Full Transcripts")
        dl_btn.setFixedHeight(32)
        dl_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        dl_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_PRIMARY};
                border: none;
                border-top: 1px solid {BORDER_COLOR};
                border-radius: 0px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: #f9fafb;
            }}
        """)
        root.addWidget(dl_btn)

        self.set_loading()

    def _clear(self) -> None:
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_loading(self) -> None:
        self._clear()
        lbl = QLabel("Loading recent results…")
        lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )
        self._list_lay.addWidget(lbl)
        self._list_lay.addStretch()


    def set_results(self, results: list[dict]) -> None:
        self._clear()

        results = results[:5]

        if not results:
            self.set_empty()
            return

        for r in results:
            self._list_lay.addWidget(_ResultItem(r))

        self._list_lay.addStretch()


    def set_empty(self) -> None:
        self._clear()
        lbl = QLabel("No recent results yet.")
        lbl.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:12px; background:transparent;"
        )
        self._list_lay.addWidget(lbl)
        self._list_lay.addStretch()


    def set_error(self, message: str = "Could not load recent results.") -> None:
        self._clear()
        lbl = QLabel(message)
        lbl.setStyleSheet(
            f"color:{ACCENT_RED}; font-size:12px; background:transparent;"
        )
        self._list_lay.addWidget(lbl)
        self._list_lay.addStretch()