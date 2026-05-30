from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, Signal

from client.reports.views.sidebar import SidebarWidget
from client.reports.views.stats_panel import StatsPanel
from client.reports.views.all_results_list import AllResultsList
from client.reports.services.api_client import ReportsApiClient
from client.reports.services.api_worker import ReportsApiWorker
from client.Shared.top_bar_icon import TopBarIcon, get_initials

# ─────────────────────────────────────────────────────────────────────────────
#  Design tokens
# ─────────────────────────────────────────────────────────────────────────────

TOP_BAR_BG     = "#ffffff"
MAIN_BG        = "#f0f2f5"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TOP_BAR_HEIGHT = 56

# ─────────────────────────────────────────────────────────────────────────────
#  _TopBar
# ─────────────────────────────────────────────────────────────────────────────

class _TopBar(QWidget):
    """Thin horizontal bar at the very top: logo + icon row + avatar."""

    def __init__(self, full_name: str = "Student") -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(TOP_BAR_HEIGHT)
        self.setStyleSheet(f"""
            _TopBar {{
                background: {TOP_BAR_BG};
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(16)

        logo = QLabel()
        logo.setTextFormat(Qt.TextFormat.RichText)
        logo.setText(
            f'<span style="color:{TEXT_PRIMARY}; font-size:17px; font-weight:900;">SEPP</span>'
            f'<span style="color:#4a90d9; font-size:17px; font-weight:700;"> SECURE</span>'
        )
        logo.setStyleSheet("background:transparent;")
        lay.addWidget(logo)
        lay.addStretch()

        # Icon row (camera, signal, bell)
        for icon_kind in ["camera", "signal", "bell"]:
            icon_btn = TopBarIcon(icon_kind)
            lay.addWidget(icon_btn)

        # Avatar circle showing initials
        avatar = QLabel(get_initials(full_name))
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("""
            background: #4a90d9;
            color: white;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 800;
        """)
        lay.addWidget(avatar)


# ─────────────────────────────────────────────────────────────────────────────
#  ReportsPage
# ─────────────────────────────────────────────────────────────────────────────

class ReportsPage(QWidget):
    """
    Main entry point for the Reports view.
    Currently just scaffolding with Sidebar and Topbar.
    """
    nav_requested      = Signal(str)
    sign_out_requested = Signal()
    review_requested   = Signal(str, str)  # session_id, exam_id -> MainWindow

    def __init__(
        self,
        api: ReportsApiClient,
        full_name: str = "Student",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._full_name = full_name
        
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {MAIN_BG};")

        self._build_workers()
        self._build_ui()
        self._wire_signals()

    def _build_workers(self) -> None:
        self._worker = ReportsApiWorker(self._api)
        self._worker.performance_fetched.connect(self._on_performance_fetched)
        self._worker.history_fetched.connect(self._on_history_fetched)
        self._worker.error_occurred.connect(self._on_error)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        root.addWidget(_TopBar(self._full_name))

        # Body (Sidebar + Content)
        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        body_lay = QHBoxLayout(body_w)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Sidebar
        self._sidebar = SidebarWidget()
        body_lay.addWidget(self._sidebar)

        # Main Content Area
        content_w = QWidget()
        content_w.setStyleSheet("background: transparent;")
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(40, 32, 40, 32)
        content_lay.setSpacing(24)

        # Header
        content_lay.addWidget(self._build_page_header())
        # Stats Panel
        self._stats_panel = StatsPanel()
        content_lay.addWidget(self._stats_panel)

        # All Results List
        self._results_list = AllResultsList()
        content_lay.addWidget(self._results_list, stretch=1)

        body_lay.addWidget(content_w, stretch=1)
        root.addWidget(body_w, stretch=1)

    def _build_page_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        title = QLabel("My Reports")
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:26px; font-weight:800; background:transparent;"
        )

        subtitle = QLabel("View and analyze your exam results and feedback.")
        subtitle.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;"
        )

        lay.addWidget(title)
        lay.addWidget(subtitle)
        return w

    def _wire_signals(self) -> None:
        self._sidebar.nav_clicked.connect(self.nav_requested.emit)
        self._sidebar.sign_out_requested.connect(self.sign_out_requested.emit)
        self._results_list.review_requested.connect(self.review_requested.emit)

    def refresh_data(self) -> None:
        """Called when navigating to this page to reload data."""
        self._worker.fetch_data()

    def _on_performance_fetched(self, data: dict) -> None:
        self._stats_panel.update_stats(data)

    def _on_history_fetched(self, history: list[dict]) -> None:
        self._results_list.update_history(history)

    def _on_error(self, err: str) -> None:
        # Simplistic error logging for now
        print(f"Reports API Error: {err}")
