from __future__ import annotations

from typing import cast

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor

from client.exam.services.api_client import ApiClient
from client.exam.services.api_worker import ApiWorker
from client.exam.views.sidebar import SidebarWidget

from client.exam.views.upcoming_exams_panel    import UpcomingExamsPanel
from client.exam.views.pending_requests_panel  import PendingRequestsPanel
from client.exam.views.join_exam_widget        import JoinExamWidget
from client.dashboard.views.recent_results     import RecentResults
from client.Shared.view_details_dialog     import ViewDetailsDialog
from client.Shared.top_bar_icon            import TopBarIcon, get_initials

# ─────────────────────────────────────────────────────────────────────────────
#  Design tokens  (kept local — matches dashboard_page.py set)
# ─────────────────────────────────────────────────────────────────────────────

TOP_BAR_BG     = "#ffffff"
MAIN_BG        = "#f0f2f5"
CARD_BG        = "#ffffff"
BORDER_COLOR   = "#e5e7eb"
TEXT_PRIMARY   = "#0d1b2e"
TEXT_SECONDARY = "#6b7280"
TOP_BAR_HEIGHT = 56
SIDEBAR_WIDTH  = 232


# ─────────────────────────────────────────────────────────────────────────────
#  _TopBar  (reused verbatim from dashboard_page.py — visual only)
# ─────────────────────────────────────────────────────────────────────────────

class _TopBar(QWidget):
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
#  ExamsPage
# ─────────────────────────────────────────────────────────────────────────────

class ExamsPage(QWidget):
    """
    Top-level Exams page widget.

    Signals
    -------
    nav_requested(label: str)
        Bubbles sidebar nav clicks up to MainWindow for page switching.

    check_in_navigated(exam_id: str)
        Emitted when a student clicks "Check-In Now" on an exam card.
        MainWindow should catch this and push the check-in page.

    Wiring pattern
    --------------
    Identical to DashboardPage:
      child widget emits signal
        → ExamsPage slot catches it
          → _run_api_job dispatches ApiWorker off-thread
            → on_success callback pushes result back into widget via set_*
    """

    nav_requested      = Signal(str)   # label  → MainWindow
    check_in_navigated = Signal(str)   # exam_id → MainWindow
    review_requested   = Signal(str)   # session_id → MainWindow
    sign_out_requested = Signal()      # → MainWindow

    AUTO_REFRESH_MS = 10_000

    def __init__(
        self,
        api: ApiClient,
        full_name: str = "Student",
        auto_refresh_ms: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._full_name = full_name
        self._workers: list[ApiWorker] = []
        self._load_jobs_remaining = 0
        self._load_refresh_pending = False

        # Exam data cache keyed by exam_id — populated when upcoming exams load.
        # Used to serve ViewDetailsDialog without an extra round-trip.
        self._exam_cache: dict[str, dict] = {}
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(auto_refresh_ms or self.AUTO_REFRESH_MS)
        self._auto_refresh_timer.timeout.connect(self._on_auto_refresh_tick)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {MAIN_BG};")

        self._build_ui()
        self._wire_signals()
        self._load_page_data(show_loading=True)
        self._auto_refresh_timer.start()

    # ── UI assembly ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        root.addWidget(_TopBar(self._full_name))

        # Body: sidebar + content
        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        body_lay = QHBoxLayout(body_w)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Sidebar
        self._sidebar = SidebarWidget()
        self._sidebar.nav_clicked.connect(self._on_nav)
        self._sidebar.sign_out_requested.connect(self.sign_out_requested.emit)
        body_lay.addWidget(self._sidebar)

        # Content area
        content_w = QWidget()
        content_w.setStyleSheet(f"background: {MAIN_BG};")
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(28, 20, 28, 20)
        content_lay.setSpacing(16)

        # Page header
        content_lay.addWidget(self._build_page_header())

        # Two-column panel row
        panels = QHBoxLayout()
        panels.setSpacing(20)

        # Left column (~60 %)
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        self._upcoming_panel  = UpcomingExamsPanel()
        self._pending_panel   = PendingRequestsPanel()

        left_col.addWidget(self._upcoming_panel)
        left_col.addWidget(self._pending_panel)
        left_col.addStretch()

        # Right column (~40 %)
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        self._join_widget      = JoinExamWidget()
        self._recent_results   = RecentResults(api=self._api)
        self._recent_results.result_clicked.connect(self._on_recent_result_clicked)

        right_col.addWidget(self._join_widget)
        right_col.addWidget(self._recent_results)
        right_col.addStretch()

        panels.addLayout(left_col, stretch=60)
        panels.addLayout(right_col, stretch=40)

        content_lay.addLayout(panels, stretch=1)
        body_lay.addWidget(content_w, stretch=1)
        root.addWidget(body_w, stretch=1)

    def _build_page_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        title = QLabel("My Exams")
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:26px; font-weight:800; background:transparent;"
        )

        subtitle = QLabel("Manage your scheduled assessments and security credentials.")
        subtitle.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;"
        )

        lay.addWidget(title)
        lay.addWidget(subtitle)
        return w

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        # Upcoming exams panel
        self._upcoming_panel.check_in_requested.connect(self._on_check_in)
        self._upcoming_panel.view_details_requested.connect(self._on_view_details)

        # Pending requests panel
        self._pending_panel.cancel_requested.connect(self._on_cancel_request)

        # Join exam widget
        self._join_widget.access_code_submitted.connect(self._on_join_exam)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_nav(self, label: str) -> None:
        self.nav_requested.emit(label)

    def _on_check_in(self, exam_id: str) -> None:
        """Navigate to the check-in page via MainWindow."""
        self.check_in_navigated.emit(exam_id)

    def _on_view_details(self, exam_id: str) -> None:
        """
        Show ViewDetailsDialog using cached exam data.
        Data is populated when upcoming exams are loaded — no extra API call.
        """
        data = self._exam_cache.get(exam_id)
        if data is None:
            # Edge case: cache miss (shouldn't happen in normal flow).
            return
        dlg = ViewDetailsDialog(exam_data=data, parent=self)
        dlg.exec_()

    def _on_cancel_request(self, request_id: str) -> None:
        """
        User confirmed cancellation in the dialog.
        Dispatch to api_worker; on success remove the row.
        """
        self._run_api_job(
            self._api.cancel_request,
            lambda _result: self._pending_panel.remove_request(request_id),
            lambda msg: self._api_error_dialog("Cancel Request", msg),
            request_id,
        )

    def _on_join_exam(self, code: str) -> None:
        """
        Student submitted an access code.
        Disable the button while the request is in flight.
        On success: add the new pending card silently and reset the input.
        On error: show red border + message in the widget.
        """
        self._join_widget.set_loading()
        self._run_api_job(
            self._api.submit_access_code,
            self._on_join_success,
            self._on_join_error,
            code,
        )

    def _on_join_success(self, new_request: dict) -> None:
        self._pending_panel.add_request(new_request)
        self._join_widget.reset()

    def _on_join_error(self, message: str) -> None:
        self._join_widget.set_error(message or "Could not submit access request.")

    def _on_recent_result_clicked(self, data: dict) -> None:
        session_id = data.get("session_id")
        if session_id:
            self.review_requested.emit(session_id)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_page_data(self, *, show_loading: bool) -> None:
        if self._load_jobs_remaining > 0:
            self._load_refresh_pending = True
            return

        self._load_refresh_pending = False
        self._load_jobs_remaining = 3

        if show_loading:
            self._upcoming_panel.set_loading()
            self._pending_panel.set_loading()
            self._recent_results.set_loading()

        self._run_api_job(
            self._api.get_upcoming_exams,
            lambda exams: (
                self._on_exams_loaded(exams),
                self._finish_load_job(),
            ),
            lambda msg: (self._upcoming_panel.set_error(msg), self._finish_load_job()),
        )

        self._run_api_job(
            self._api.get_pending_requests,
            lambda requests: (
                self._pending_panel.set_requests(requests),
                self._finish_load_job(),
            ),
            lambda msg: (self._pending_panel.set_error(msg), self._finish_load_job()),
        )

        self._run_api_job(
            self._api.get_recent_results,
            lambda results: (
                self._recent_results.set_results(results),
                self._finish_load_job(),
            ),
            lambda msg, replace_view=show_loading: (
                self._recent_results.set_error(msg) if replace_view else None,
                self._finish_load_job(),
            ),
        )

    def _on_exams_loaded(self, exams: list[dict]) -> None:
        """Populate the upcoming panel and build the exam cache."""
        self._exam_cache = {e["exam_id"]: e for e in exams if "exam_id" in e}
        self._upcoming_panel.set_exams(exams)

    # ── Public refresh API (callable by MainWindow) ───────────────────────────

    def refresh_data(self) -> None:
        """Re-fetch all page data. Call when the page becomes visible."""
        self._load_page_data(show_loading=False)

    def shutdown(self) -> None:
        """Stop background refresh and wait for worker threads before teardown."""
        self._auto_refresh_timer.stop()
        self._load_refresh_pending = False
        for worker in list(self._workers):
            try:
                if worker.isRunning() and not worker.wait(2000):
                    worker.terminate()
                    worker.wait(2000)
            except Exception:
                pass
            try:
                worker.deleteLater()
            except Exception:
                pass
        self._workers.clear()

    def _finish_load_job(self) -> None:
        if self._load_jobs_remaining > 0:
            self._load_jobs_remaining -= 1
        if self._load_jobs_remaining == 0 and self._load_refresh_pending:
            QTimer.singleShot(0, self.refresh_data)

    def _on_auto_refresh_tick(self) -> None:
        if not self.isVisible():
            return
        self.refresh_data()

    # ── ApiWorker helpers (identical to DashboardPage pattern) ────────────────

    def _run_api_job(self, fn, on_success, on_error=None, *args, **kwargs) -> None:
        worker = ApiWorker(fn, *args, **kwargs)
        worker.finished.connect(on_success)

        if on_error is not None:
            worker.errored.connect(on_error)
        else:
            worker.errored.connect(
                lambda msg: self._api_error_dialog("API Error", msg)
            )

        worker.finished.connect(lambda _r, w=worker: self._cleanup_worker(w))
        worker.errored.connect(lambda _m, w=worker: self._cleanup_worker(w))

        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker: ApiWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def _api_error_dialog(self, title: str, message: str) -> None:
        from client.Shared.info_dialog import InfoDialog
        dlg = InfoDialog(title=title, body=message, parent=self)
        dlg.exec_()
