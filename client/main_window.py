"""
client/main_window.py
Single fullscreen window — owns all navigation via QStackedWidget.
Resets signup state whenever navigating to signup page.
"""

import logging
import os
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent, QCloseEvent

from client.modules.common.loading_spinner import SpinnerOverlay

logger = logging.getLogger(__name__)

PAGE_STARTUP = 0
PAGE_LOGIN   = 1
PAGE_SIGNUP  = 2
PAGE_STUDENT_DASHBOARD = 3
PAGE_EXAMINER_DASHBOARD = 4


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ExamApp")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint,
        )
        self.showFullScreen()

        self._is_transitioning = False
        self._pending_page: Optional[int] = None
        self._active_exam_window = None
        self._active_role: Optional[str] = None

        # Lazily built on first login for each role
        self._student_dashboard  = None
        self._examiner_dashboard = None

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Single overlay instance — reused for every page switch
        self._nav_spinner = SpinnerOverlay(parent=self._stack)

        self._load_pages()
        self._stack.setCurrentIndex(PAGE_STARTUP)
        logger.info("MainWindow ready")

    def _load_pages(self):
        from client.modules.auth.ui.startup_ui import StartupUI
        from client.auth.ui.login_ui   import LoginUI
        from client.auth.ui.signup_ui  import SignupUI
        from client.auth.login_window  import LoginWindow
        from client.auth.signup_window import SignupWindow

        # Page 0 — Startup
        self._startup_ui = StartupUI()
        self._startup_ui.login_requested.connect(lambda: self._navigate_to(PAGE_LOGIN))
        self._startup_ui.signup_requested.connect(lambda: self._navigate_to(PAGE_SIGNUP))
        self._stack.addWidget(self._startup_ui)

        # Page 1 — Login
        self._login_ui   = LoginUI()
        self._login_ctrl = LoginWindow(ui=self._login_ui)
        self._login_ui.back_requested.connect(lambda: self._navigate_to(PAGE_STARTUP))
        self._login_ui.register_requested.connect(lambda: self._navigate_to(PAGE_SIGNUP))
        self._login_ctrl.login_successful.connect(self._on_login_success)
        self._stack.addWidget(self._login_ui)

        # Page 2 — Signup
        self._signup_ui   = SignupUI()
        self._signup_ctrl = SignupWindow(ui=self._signup_ui)
        self._signup_ui.back_requested.connect(self._on_signup_back)
        self._signup_ctrl.signup_complete.connect(self._on_signup_complete)
        self._stack.addWidget(self._signup_ui)

        # Pages 3 & 4 — Dashboards: lightweight placeholders only.
        # Real widgets are built on first login for each role (_build_student_dashboard /
        # _build_examiner_dashboard) so startup never pays their construction cost.
        self._student_placeholder  = QWidget()
        self._examiner_placeholder = QWidget()
        self._stack.addWidget(self._student_placeholder)   # index 3
        self._stack.addWidget(self._examiner_placeholder)  # index 4

    def _build_student_dashboard(self):
        from client.dashboard.views.dashboard_page import DashboardPage
        # Or use the real project path, for example:
        # from dashboard.dashboard_page import DashboardPage
        # from client.modules.dashboard.dashboard_page import DashboardPage

        self._student_dashboard = DashboardPage()
        self._student_dashboard.nav_requested.connect(self._on_dashboard_nav_requested)

        # Replace the placeholder at index 3 without disturbing other indices.
        self._stack.insertWidget(PAGE_STUDENT_DASHBOARD, self._student_dashboard)

        ph = self._student_placeholder
        if ph is not None:
            self._stack.removeWidget(ph)
            ph.deleteLater()

        self._student_placeholder = None

    def _build_examiner_dashboard(self):
        from client.modules.dashboard.examiner_dashboard import ExaminerDashboard
        self._examiner_dashboard = ExaminerDashboard()
        self._stack.insertWidget(PAGE_EXAMINER_DASHBOARD, self._examiner_dashboard)
        ph = self._examiner_placeholder
        if ph is not None:
            self._stack.removeWidget(ph)
            ph.deleteLater()
        self._examiner_placeholder = None

    # ── Navigation ─────────────────────────────────────────────────────────

    def _navigate_to(self, page_index: int):
        if self._is_transitioning:
            self._pending_page = page_index
            return
        if self._stack.currentIndex() == page_index:
            return

        self._is_transitioning = True

        # Release camera/service resources when leaving signup.
        if self._stack.currentIndex() == PAGE_SIGNUP and page_index != PAGE_SIGNUP:
            self._signup_ctrl.reset()
        # Reset signup to step 1 whenever we navigate TO it.
        if page_index == PAGE_SIGNUP:
            self._signup_ctrl.reset()
            self._signup_ui.prewarm_camera()

        # Show spinner, switch on next tick (lets spinner paint first),
        # then hide after one frame so the new page can finish its first paint.
        self._nav_spinner.show()

        def _switch():
            self._stack.setCurrentIndex(page_index)
            QTimer.singleShot(80, _done)

        def _done():
            self._nav_spinner.hide()
            self._is_transitioning = False
            if (
                self._pending_page is not None
                and self._pending_page != self._stack.currentIndex()
            ):
                next_page = self._pending_page
                self._pending_page = None
                self._navigate_to(next_page)
                return
            self._pending_page = None

        QTimer.singleShot(0, _switch)

    def _on_signup_back(self):
        if self._signup_ui.current_step == 1:
            self._signup_ctrl.reset()
            self._navigate_to(PAGE_STARTUP)
        else:
            self._signup_ui.go_back()

    def _on_signup_complete(self):
        self._signup_ctrl.reset()
        self._navigate_to(PAGE_LOGIN)
        QTimer.singleShot(
            400,
            lambda: self._login_ui.set_status(
                "✓ Account created successfully. Please sign in.", "success"
            ),
        )

    def _on_login_success(
        self,
        token:         str,
        role:          str,
        user_id:       str,
        full_name:     str,
        face_enrolled: bool,
    ):
        logger.info("Login successful — %s (%s)", full_name, role)
        self._login_ui.set_loading(False)
        self._active_role = role
        
        role_key = str(role).strip().lower()
        self._active_role = role_key

        if role_key == "student":
            if self._student_dashboard is None:
                self._build_student_dashboard()
            dash_s = self._student_dashboard
            # Navigate first so the transition can start painting, then kick off
            # data fetch on the next event-loop tick (worker is near-instant to start).
            self._navigate_to(PAGE_STUDENT_DASHBOARD)
            QTimer.singleShot(
                0,
                lambda: dash_s.set_session(token, user_id, full_name),  # type: ignore[union-attr]
            )
            return

        if role_key == "examiner":
            if self._examiner_dashboard is None:
                self._build_examiner_dashboard()
            dash_e = self._examiner_dashboard
            self._navigate_to(PAGE_EXAMINER_DASHBOARD)
            QTimer.singleShot(
                0,
                lambda: dash_e.set_session(token, user_id, full_name),  # type: ignore[union-attr]
            )
            return

        self._login_ui.set_status(f"✓ Welcome {full_name}!", "success")

    def _on_start_exam_requested(self, session: dict, exam: dict, questions: list, token: str):
        from client.modules.exam_engine.exam_window import ExamWindow

        if self._active_exam_window is not None:
            logger.warning("Exam launch requested while another exam is active")
            return

        try:
            self._active_exam_window = ExamWindow(
                session=session,
                exam=exam,
                questions=questions,
                token=token,
                embedded=True,
            )
        except Exception as exc:
            logger.exception("Failed to launch exam window: %s", exc)
            return

        exam_page = self._active_exam_window

        def _on_exam_finished():
            # Always switch back to the dashboard first. After a modal dialog (submit /
            # verification failure) the stack's current widget may not compare equal to
            # exam_page even though the exam is still the visible page — skipping the switch
            # then removeWidget() left the stack in an invalid state and the app could exit.
            self._stack.setCurrentIndex(PAGE_STUDENT_DASHBOARD)
            index = self._stack.indexOf(exam_page)
            if index != -1:
                self._stack.removeWidget(exam_page)
            exam_page.deleteLater()
            if self._active_exam_window is exam_page:
                self._active_exam_window = None
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
            if self._student_dashboard is not None:
                self._student_dashboard.refresh_data()

        exam_page.finished.connect(_on_exam_finished)
        self._stack.addWidget(exam_page)
        self._nav_spinner.show()
        QTimer.singleShot(0, lambda: (
            self._stack.setCurrentWidget(exam_page),
            self.showFullScreen(),
            self.raise_(),
            self.activateWindow(),
        ))
        QTimer.singleShot(80, self._nav_spinner.hide)

    def closeEvent(self, event: QCloseEvent):
        # Ensure signup camera/background workers are stopped before teardown.
        try:
            self._signup_ctrl.reset()
        except Exception:
            pass
        super().closeEvent(event)

    # ── Debug exit ─────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if os.getenv("DEBUG", "false").lower() == "true":
            if event.key() == Qt.Key.Key_F12:
                self.close()
                return
        super().keyPressEvent(event)

    def _on_dashboard_nav_requested(self, label: str) -> None:
        key = label.strip().lower()

        routes = {
            "dashboard": PAGE_STUDENT_DASHBOARD,
            "home": PAGE_STUDENT_DASHBOARD,

            # Later, when you create these pages:
            # "exams": PAGE_EXAMS,
            # "results": PAGE_RESULTS,
            # "settings": PAGE_SETTINGS,
        }

        page_index = routes.get(key)

        if page_index is not None:
            self._navigate_to(page_index)
            return

        # Page does not exist yet, so keep showing the same dashboard-style dialog.
        if self._student_dashboard is not None:
            self._student_dashboard.show_nav_dialog(label)