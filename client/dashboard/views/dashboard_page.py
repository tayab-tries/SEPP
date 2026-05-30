from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from typing import cast

from client.dashboard.services.api_client import ApiClient
from client.dashboard.views.sidebar import SidebarWidget
from client.dashboard.views.next_exam_card import NextExamCard
from client.dashboard.views.upcoming_assessments import UpcomingAssessments
from client.dashboard.views.recent_results import RecentResults
from client.dashboard.views.quick_actions import QuickActions
from client.dashboard.views.status_bar import StatusBarWidget
from client.dashboard.services.api_worker import ApiWorker


from client.Shared.top_bar_icon import TopBarIcon, get_initials


# ─────────────────────────────────────────────────────────
#  SEPP Dashboard — Design Tokens
#  Match these to the reference screenshot.
# ─────────────────────────────────────────────────────────

CARD        = "#FFFFFF"
BORDER      = "#DDE0E8"
T_PRIMARY   = "#111827"
T_SECONDARY = "#6B7280"

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
        self.avatar = QLabel(get_initials(full_name))
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar.setStyleSheet("""
            background: #4a90d9;
            color: white;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 800;
        """)
        lay.addWidget(self.avatar)

    def update_user_info(self, name: str) -> None:
        self.avatar.setText(get_initials(name))



# ──────────────────────────────────────────────────────────────────────────────
class _PageHeader(QWidget):
    """'Student Dashboard' title + subtitle + system-status badges."""

    def __init__(
        self,
        student_name: str,
        system_safe: bool,
        identity_verified: bool,
    ) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        self.setFixedHeight(70)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # Title column
        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        title = QLabel("Student Dashboard")
        title.setStyleSheet(
            f"color:{TEXT_PRIMARY}; font-size:26px; font-weight:800; background:transparent;"
        )

        subtitle = QLabel(
            f"Welcome back, {student_name}. "
            "Your system is secure and ready for examination."
        )
        subtitle.setStyleSheet(
            f"color:{TEXT_SECONDARY}; font-size:13px; background:transparent;"
        )

        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        # Badge row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badge_row.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        if system_safe:
            badge_row.addWidget(_PageHeader._badge("● System: Safe", ACCENT_GREEN))
        if identity_verified:
            badge_row.addWidget(_PageHeader._badge("● Identity Verified", ACCENT_GREEN))

        lay.addLayout(title_col, stretch=1)
        lay.addLayout(badge_row)

    @staticmethod
    def _badge(text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        lbl.setStyleSheet(f"""
            color: {color};
            background: white;
            border: 1px solid {BORDER_COLOR};
            border-radius: 14px;
            padding: 4px 14px;
            font-size: 12px;
            font-weight: 500;
        """)
        return lbl

class InfoDialog(QDialog):
    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(400)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Single card container — everything lives inside this
        card = QWidget()
        card.setObjectName("dialogCard")
        card.setStyleSheet(f"""
            QWidget#dialogCard {{
                background: {CARD};
                border-radius: 10px;
                border: 1px solid {BORDER};
            }}
        """)

        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # ── Title bar ────────────────────────────────────────────────
        tb = QWidget()
        tb.setStyleSheet("background: transparent;")

        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(20, 8, 16, 6)
        tb_lay.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{T_PRIMARY}; background:transparent;"
        )

        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {T_SECONDARY};
                border: none;
                font-size: 13px;
                font-weight: 600;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: #F3F4F6;
                color: {T_PRIMARY};
            }}
        """)
        close_btn.clicked.connect(self.accept)

        tb_lay.addWidget(close_btn)
        card_lay.addWidget(tb)

        # ── Divider ──────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER};")
        card_lay.addWidget(divider)

        # ── Body ─────────────────────────────────────────────────────
        lbl = QLabel(body)
        lbl.setWordWrap(True)
        lbl.setContentsMargins(24, 16, 24, 20)
        lbl.setStyleSheet(
            f"font-size:13px; color:{T_PRIMARY}; background:transparent;"
        )
        card_lay.addWidget(lbl)

        outer.addWidget(card)

# ──────────────────────────────────────────────────────────────────────────────
class DashboardPage(QWidget):
    nav_requested = Signal(str)
    review_requested = Signal(str)
    check_in_requested = Signal(str)   # exam_id → MainWindow
    sign_out_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._api = ApiClient()
        self._token: str = ""
        self._user_id: str = ""
        self._full_name: str = "Student"
        self._workers: list[ApiWorker] = []
        student = {
            "name": "Student",
            "system_safe": True,
            "identity_verified": False,
        }

        self.setMinimumSize(1100, 720)
        self.setWindowTitle("SEPP — Student Dashboard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {MAIN_BG};")

        # ── Root ─────────────────────────────────────────────────────────
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Top bar
        self._top_bar = _TopBar()
        root_lay.addWidget(self._top_bar)

        # ── Body: sidebar + content ───────────────────────────────────────
        body_w = QWidget()
        body_w.setStyleSheet("background: transparent;")
        body_lay = QHBoxLayout(body_w)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._sidebar = SidebarWidget()
        self._sidebar.nav_clicked.connect(self._on_nav)
        self._sidebar.sign_out_clicked.connect(self.sign_out_requested.emit)
        body_lay.addWidget(self._sidebar)

        # ── Content area ─────────────────────────────────────────────────
        content_w = QWidget()
        content_w.setStyleSheet(f"background: {MAIN_BG};")
        content_lay = QVBoxLayout(content_w)
        content_lay.setContentsMargins(28, 20, 28, 20)
        content_lay.setSpacing(16)

        # Page header
        self._page_header = _PageHeader(
            student.get("name", "Student"),
            student.get("system_safe", False),
            student.get("identity_verified", False),
        )
        content_lay.addWidget(self._page_header)

        # ── Main two-column panel row ─────────────────────────────────────
        panels_lay = QHBoxLayout()
        panels_lay.setSpacing(20)

        # Left column
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        self._exam_card = NextExamCard(self._api)
        self._exam_card.check_in_clicked.connect(self.check_in_requested.emit)
        self._exam_card.instructions_clicked.connect(
            lambda: self._dialog(
                "Exam Instructions",
                "• Read all questions carefully before answering.\n"
                "• You have 120 minutes to complete this exam.\n"
                "• Do not leave the exam window — this will be flagged.\n"
                "• Ensure your face is visible in the camera at all times.\n\n"
                "Good luck!",
            )
        )

        self._assessments = UpcomingAssessments(self._api)
        self._assessments.view_schedule_clicked.connect(
            lambda: self._on_nav("Exams")
        )

        left_col.addWidget(self._exam_card)
        left_col.addWidget(self._assessments)

        # Right column
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        self._quick_actions = QuickActions()
        self._quick_actions.action_triggered.connect(self._on_action)

        self._results = RecentResults(self._api)
        self._results.result_clicked.connect(self._on_recent_result_clicked)

        right_col.addWidget(self._quick_actions)
        right_col.addWidget(self._results, stretch=1)

        panels_lay.addLayout(left_col, stretch=58)
        panels_lay.addLayout(right_col, stretch=42)

        content_lay.addLayout(panels_lay, stretch=1)

        # Status bar (bottom)
        self._status_bar = StatusBarWidget(self._api)
        content_lay.addWidget(self._status_bar)

        body_lay.addWidget(content_w, stretch=1)
        root_lay.addWidget(body_w, stretch=1)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_nav(self, label: str) -> None:
        self.nav_requested.emit(label)

    def _on_recent_result_clicked(self, data: dict) -> None:
        session_id = data.get("session_id")
        if not session_id:
            return
            
        title = data.get("title", "Exam Attempt")
        raw = data.get("raw", {})
        
        # Read the backend is_graded flag (defaults to True if somehow missing)
        is_graded = data.get("is_graded", True)
        
        from client.Shared.attempt_review_dialog import AttemptReviewDialog
        dialog = AttemptReviewDialog(title, is_graded, self)
        
        def on_review():
            self.review_requested.emit(session_id)
            
        def on_report():
            self._dialog("Check Report", "The detailed report feature will be implemented soon.")
            
        dialog.review_requested.connect(on_review)
        dialog.report_requested.connect(on_report)
        dialog.exec()
        
    def show_nav_dialog(self, label: str) -> None:
        self._dialog(
            label,
            f"The '{label}' page has not been implemented yet.\n\n"
            "This click is now routed through MainWindow."
        )

    def _on_action(self, action: str) -> None:
        messages = {
            "Run System Diagnostic": (
                "Running system diagnostic…\n\n"
                "✓ Camera detected and active\n"
                "✓ Network latency: 24 ms\n"
                "✓ Disk space: sufficient\n"
                "✓ CPU load: normal\n\n"
                "All systems operational."
            ),
            "Re-verify Identity": (
                "Launching biometric verification…\n\n"
                "Please look directly at your camera.\n"
                "Keep your face centred and well-lit.\n\n"
                "(Biometric capture would run here in production.)"
            ),
            "Access Sandbox": (
                "Opening sandbox environment…\n\n"
                "This is a practice session.\n"
                "No responses will be recorded or graded.\n\n"
                "Use this to familiarise yourself with the exam interface."
            ),
        }
        self._dialog(action, messages.get(action, "Feature coming soon."))

    def _dialog(self, title: str, message: str) -> None:
        dlg = InfoDialog(title, message, self)
        dlg.exec_()
        
    def _run_api_job(self, fn, on_success, on_error=None, *args, **kwargs) -> None:
        worker = ApiWorker(fn, *args, **kwargs)

        worker.finished.connect(on_success)

        if on_error is not None:
            worker.errored.connect(on_error)
        else:
            worker.errored.connect(lambda msg: self._dialog("API Error", msg))

        worker.finished.connect(lambda _result, w=worker: self._cleanup_worker(w))
        worker.errored.connect(lambda _msg, w=worker: self._cleanup_worker(w))

        self._workers.append(worker)
        worker.start()


    def _cleanup_worker(self, worker: ApiWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def shutdown(self) -> None:
        """Stop worker threads before the widget is destroyed."""
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

    def _load_dashboard_data(self) -> None:
        self._exam_card.set_loading()
        self._assessments.set_loading()
        self._results.set_loading()

        self._refresh_next_exam()

        self._run_api_job(
            self._api.get_upcoming_assessments,
            self._assessments.set_assessments,
            lambda msg: self._assessments.set_error(msg),
            5,
        )

        self._run_api_job(
            self._api.get_recent_results,
            self._results.set_results,
            lambda msg: self._results.set_error(msg),
            5,
        )
        
    def _refresh_next_exam(self) -> None:
        self._exam_card.set_loading()

        self._run_api_job(
            self._api.get_next_exam,
            self._exam_card.set_exam,
            lambda msg: self._exam_card.set_error(msg),
        )
        
    def _refresh_student_info(self) -> None:
        self._run_api_job(
            self._api.get_student_info,
            self._apply_student_info,
            lambda _msg: None,  # keep default header if /auth/me fails
        )


    def _apply_student_info(self, student: dict) -> None:
        old_header = self._page_header
        parent = old_header.parentWidget()

        if parent is None:
            return

        layout = parent.layout()

        if layout is None:
            return

        parent_layout = cast(QVBoxLayout, layout)
        index = parent_layout.indexOf(old_header)

        self._page_header = _PageHeader(
            student.get("name", "Student"),
            student.get("system_safe", True),
            student.get("identity_verified", False),
        )

        self._top_bar.update_user_info(student.get("name", "Student"))

        parent_layout.insertWidget(index, self._page_header)
        old_header.deleteLater()
    
    def refresh_data(self) -> None:
        self._load_dashboard_data()
        self._refresh_student_info()
        
    def set_session(self, token: str, user_id: str, full_name: str) -> None:
        self._token = token
        self._user_id = user_id
        self._full_name = full_name
        self._api.set_token(token)

        self._apply_student_info({
            "name": full_name,
            "system_safe": True,
            "identity_verified": False,
        })

        self.refresh_data()

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    page = DashboardPage()
    page.show()

    sys.exit(app.exec())
