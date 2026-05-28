"""
client/main_window.py
Single fullscreen window — owns all navigation via QStackedWidget.
Resets signup state whenever navigating to signup page.
"""

import logging
import os
from typing import Optional

import requests
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QKeyEvent, QCloseEvent

from client.modules.common.loading_spinner import SpinnerOverlay

logger = logging.getLogger(__name__)

PAGE_STARTUP = 0
PAGE_LOGIN   = 1
PAGE_SIGNUP  = 2
PAGE_STUDENT_DASHBOARD = 3
PAGE_EXAMINER_DASHBOARD = 4
PAGE_EXAMS = 5
PAGE_REPORTS = 6


def _extract_http_error(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"Request failed with status {response.status_code}."

    detail = data.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            msg = first.get("msg")
            if msg:
                return str(msg)

    return f"Request failed with status {response.status_code}."


def _http_prepare_exam_launch(token: str, base_url: str, exam_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    base = base_url.rstrip("/")

    try:
        session_resp = requests.post(
            f"{base}/sessions/start",
            headers=headers,
            json={"exam_id": exam_id},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not start exam session: {exc}") from exc

    if session_resp.status_code >= 400:
        raise RuntimeError(_extract_http_error(session_resp))
    session = session_resp.json()

    try:
        exam_resp = requests.get(
            f"{base}/exams/{exam_id}",
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not load exam details: {exc}") from exc

    if exam_resp.status_code >= 400:
        raise RuntimeError(_extract_http_error(exam_resp))
    exam = exam_resp.json()

    try:
        questions_resp = requests.get(
            f"{base}/exams/{exam_id}/questions",
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not load exam questions: {exc}") from exc

    if questions_resp.status_code >= 400:
        raise RuntimeError(_extract_http_error(questions_resp))
    questions = questions_resp.json()

    return {
        "session": session,
        "exam": exam,
        "questions": questions,
    }


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
        self._student_face_enrolled = False
        self._exam_launch_worker = None

        # Auth/session state
        self._auth_token: Optional[str] = None
        self._active_user_id: Optional[str] = None
        self._active_full_name: Optional[str] = None

        # Lazily built on first login/navigation
        self._student_dashboard  = None
        self._examiner_dashboard = None
        self._exams_page = None
        self._reports_page = None

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Single overlay instance — reused for every page switch
        self._nav_spinner = SpinnerOverlay(parent=self._stack)

        self._settings = QSettings("SEPP", "ExamApp")

        self._load_pages()
        
        saved_token = self._settings.value("auth_token")
        if saved_token:
            self._validate_saved_token(saved_token)
        else:
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

        # Pages 3, 4 & 5 — lazy placeholders only.
        self._student_placeholder  = QWidget()
        self._examiner_placeholder = QWidget()
        self._exams_placeholder    = QWidget()
        self._reports_placeholder  = QWidget()
        self._stack.addWidget(self._student_placeholder)   # index 3
        self._stack.addWidget(self._examiner_placeholder)  # index 4
        self._stack.addWidget(self._exams_placeholder)     # index 5
        self._stack.addWidget(self._reports_placeholder)   # index 6

    def _build_student_dashboard(self):
        from client.dashboard.views.dashboard_page import DashboardPage
        # Or use the real project path, for example:
        # from dashboard.dashboard_page import DashboardPage
        # from client.modules.dashboard.dashboard_page import DashboardPage

        self._student_dashboard = DashboardPage()
        self._student_dashboard.nav_requested.connect(self._on_dashboard_nav_requested)
        self._student_dashboard.sign_out_requested.connect(self._on_sign_out_requested)
        self._student_dashboard.review_requested.connect(self._on_review_requested)

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
        self._examiner_dashboard.sign_out_requested.connect(self._on_sign_out_requested)
        self._stack.insertWidget(PAGE_EXAMINER_DASHBOARD, self._examiner_dashboard)
        ph = self._examiner_placeholder
        if ph is not None:
            self._stack.removeWidget(ph)
            ph.deleteLater()
        self._examiner_placeholder = None
        
    def _build_exams_page(self):
        from client.exam.views.exams_page import ExamsPage
        from client.exam.services.api_client import ApiClient

        if not self._auth_token:
            logger.warning("Cannot build ExamsPage without auth token")
            return

        api = ApiClient(
            base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
            access_token=self._auth_token,
        )
        self._exams_page = ExamsPage(api=api)
        self._exams_page.nav_requested.connect(self._on_dashboard_nav_requested)
        self._exams_page.check_in_navigated.connect(self._on_exam_check_in_requested)
        self._exams_page.review_requested.connect(self._on_review_requested)
        self._exams_page.sign_out_requested.connect(self._on_sign_out_requested)
        self._stack.insertWidget(PAGE_EXAMS, self._exams_page)

        ph = self._exams_placeholder
        if ph is not None:
            self._stack.removeWidget(ph)
            ph.deleteLater()
        self._exams_placeholder = None

    def _build_reports_page(self):
        from client.reports.views.reports_page import ReportsPage
        from client.reports.services.api_client import ReportsApiClient
        
        if not self._auth_token:
            logger.warning("Cannot build ReportsPage without auth token")
            return
            
        api = ReportsApiClient(
            base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
            access_token=self._auth_token,
        )
        
        self._reports_page = ReportsPage(api=api)
        self._reports_page.nav_requested.connect(self._on_dashboard_nav_requested)
        self._reports_page.sign_out_requested.connect(self._on_sign_out_requested)
        self._reports_page.review_requested.connect(self._on_review_requested)
        self._stack.insertWidget(PAGE_REPORTS, self._reports_page)
        
        ph = self._reports_placeholder
        if ph is not None:
            self._stack.removeWidget(ph)
            ph.deleteLater()
        self._reports_placeholder = None

    # ── Authentication / Auto-Login ────────────────────────────────────────

    def _validate_saved_token(self, token: str):
        from client.core.api_worker import ApiWorker
        self._nav_spinner.show()
        base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        
        def _http_val(t, b):
            try:
                r = requests.get(f"{b.rstrip('/')}/auth/me", headers={"Authorization": f"Bearer {t}"}, timeout=10)
                if r.status_code == 200:
                    return r.json()
                raise RuntimeError("Invalid token")
            except Exception as e:
                raise RuntimeError(str(e))

        self._val_worker = ApiWorker(_http_val, token, base_url)
        self._val_worker.finished.connect(lambda user: self._on_token_validated(token, user))
        self._val_worker.errored.connect(self._on_token_invalid)
        self._val_worker.start()

    def _on_token_validated(self, token: str, user: dict):
        self._nav_spinner.hide()
        # Some endpoints return "role", others return "account_type".
        role = user.get("role", user.get("account_type", "student"))
        self._on_login_success(
            token=token,
            role=role,
            user_id=user.get("user_id", user.get("id", "")),
            full_name=user.get("full_name", user.get("name", "User")),
            face_enrolled=user.get("face_enrolled", False)
        )

    def _on_token_invalid(self, msg: str):
        self._nav_spinner.hide()
        logger.warning(f"Auto-login failed: {msg}")
        self._settings.clear()
        self._navigate_to(PAGE_STARTUP)

    def _on_sign_out_requested(self):
        self._settings.clear()
        self._auth_token = None
        self._active_user_id = None
        self._active_role = None

        if hasattr(self, "_login_ui"):
            self._login_ui.reset()
        
        if self._student_dashboard is not None:
            self._stack.removeWidget(self._student_dashboard)
            self._student_dashboard.deleteLater()
            self._student_dashboard = None
            self._student_placeholder = QWidget()
            self._stack.insertWidget(PAGE_STUDENT_DASHBOARD, self._student_placeholder)

        if self._examiner_dashboard is not None:
            self._stack.removeWidget(self._examiner_dashboard)
            self._examiner_dashboard.deleteLater()
            self._examiner_dashboard = None
            self._examiner_placeholder = QWidget()
            self._stack.insertWidget(PAGE_EXAMINER_DASHBOARD, self._examiner_placeholder)

        if self._exams_page is not None:
            self._stack.removeWidget(self._exams_page)
            self._exams_page.deleteLater()
            self._exams_page = None
            self._exams_placeholder = QWidget()
            self._stack.insertWidget(PAGE_EXAMS, self._exams_placeholder)

        self._navigate_to(PAGE_STARTUP)

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

        self._auth_token = token
        self._active_user_id = user_id
        self._active_full_name = full_name
        self._student_face_enrolled = bool(face_enrolled)

        self._settings.setValue("auth_token", token)

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
        
    def _on_exam_check_in_requested(self, exam_id: str) -> None:
        """
        Temporary handler for ExamsPage check-in button.

        Later this should:
        1. call ApiClient.start_session(exam_id)
        2. run face/check-in flow
        3. load questions
        4. call _on_start_exam_requested(...)
        """
        logger.info("Check-in requested for exam_id=%s", exam_id)

        from client.Shared.info_dialog import InfoDialog

        dlg = InfoDialog(
            title="Check-In",
            body="Check-in navigation is connected, but the check-in/start flow is not wired yet.",
            parent=self,
        )
        dlg.exec_()

    def _on_exam_check_in_requested(self, exam_id: str) -> None:
        logger.info("Check-in requested for exam_id=%s", exam_id)

        if self._active_exam_window is not None:
            logger.warning("Check-in requested while another exam is active")
            return

        if not self._auth_token:
            self._show_info_dialog("Check-In", "You must be signed in to start an exam.")
            return

        if not self._student_face_enrolled:
            self._show_info_dialog(
                "Face Enrollment Required",
                "You must complete face enrollment before starting an exam.",
            )
            return

        if self._exam_launch_worker is not None and self._exam_launch_worker.isRunning():
            logger.warning("Exam launch already in progress")
            return

        from client.core.api_worker import ApiWorker

        self._nav_spinner.show()
        self._exam_launch_worker = ApiWorker(
            _http_prepare_exam_launch,
            self._auth_token,
            os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
            exam_id,
        )
        self._exam_launch_worker.finished.connect(self._on_exam_launch_ready)
        self._exam_launch_worker.errored.connect(self._on_exam_launch_error)
        self._exam_launch_worker.finished.connect(
            lambda _result, w=self._exam_launch_worker: self._cleanup_exam_launch_worker(w)
        )
        self._exam_launch_worker.errored.connect(
            lambda _msg, w=self._exam_launch_worker: self._cleanup_exam_launch_worker(w)
        )
        self._exam_launch_worker.start()

    def _on_exam_launch_ready(self, payload: dict) -> None:
        self._nav_spinner.hide()
        if not self._auth_token:
            self._show_info_dialog("Exam Start Failed", "Your session expired. Please sign in again.")
            return

        self._on_start_exam_requested(
            payload["session"],
            payload["exam"],
            payload["questions"],
            self._auth_token,
        )

    def _on_exam_launch_error(self, message: str) -> None:
        self._nav_spinner.hide()
        self._show_info_dialog("Exam Start Failed", message)

    def _cleanup_exam_launch_worker(self, worker) -> None:
        if worker is None:
            return
        if self._exam_launch_worker is worker:
            self._exam_launch_worker = None
        worker.deleteLater()

    def _show_info_dialog(self, title: str, body: str) -> None:
        from client.Shared.info_dialog import InfoDialog

        dlg = InfoDialog(
            title=title,
            body=body,
            parent=self,
        )
        dlg.exec_()

    def _on_start_exam_requested(self, session: dict, exam: dict, questions: list, token: str):
        if self._active_exam_window is not None:
            logger.warning("Exam launch requested while another exam is active")
            return

        if not questions:
            self._show_info_dialog(
                "Exam Start Failed",
                "This exam does not have any questions yet. Ask the examiner to finish configuring it before going live.",
            )
            return

        from client.student_exam_screen.exam_window import ExamWindow

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
            self._show_info_dialog(
                "Exam Start Failed",
                f"The exam window could not be started.\n\n{exc}",
            )
            return

        exam_page = self._active_exam_window

        def _on_exam_finished():
            # Always switch back to the dashboard first. After a modal dialog (submit /
            # verification failure) the stack's current widget may not compare equal to
            # exam_page even though the exam is still the visible page — skipping the switch
            # then removeWidget() left the stack in an invalid state and the app could exit.
            self._stack.setCurrentIndex(
                PAGE_EXAMS if self._exams_page is not None else PAGE_STUDENT_DASHBOARD
            )
            index = self._stack.indexOf(exam_page)
            if index != -1:
                self._stack.removeWidget(exam_page)
            exam_page.deleteLater()
            if self._active_exam_window is exam_page:
                self._active_exam_window = None
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
            if self._exams_page is not None:
                self._exams_page.refresh_data()
            elif self._student_dashboard is not None:
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

    def _on_review_requested(self, session_id: str) -> None:
        self._nav_spinner.show()
        
        from client.review.services.api_client import ReviewApiClient
        from client.review.services.api_worker import ApiWorker
        
        self._review_api = ReviewApiClient()
        self._review_api.set_token(self._auth_token)
        self._review_worker = ApiWorker(self._review_api.fetch_review_data, session_id)
        
        def on_success(data):
            self._nav_spinner.hide()
            from client.review.views.review_screen_widget import ReviewScreenWidget
            review_page = ReviewScreenWidget(
                questions=data.get("questions", []),
                answers=data.get("answers", []),
                exam=data.get("exam", {}),
                session=data.get("session", {}),
            )
            
            def _close_review():
                self._stack.setCurrentIndex(PAGE_EXAMS if self._exams_page is not None else PAGE_STUDENT_DASHBOARD)
                self._stack.removeWidget(review_page)
                review_page.deleteLater()
                self.showFullScreen()
                self.raise_()
                self.activateWindow()

            review_page.close_requested.connect(_close_review)
            
            self._stack.addWidget(review_page)
            QTimer.singleShot(0, lambda: (
                self._stack.setCurrentWidget(review_page),
                self.showFullScreen(),
                self.raise_(),
                self.activateWindow(),
            ))

        def on_error(msg):
            self._nav_spinner.hide()
            self._show_info_dialog("Review Error", f"Could not load review data:\n{msg}")

        self._review_worker.finished.connect(on_success)
        self._review_worker.errored.connect(on_error)
        self._review_worker.start()

    def closeEvent(self, event: QCloseEvent):
        # Ensure signup camera/background workers are stopped before teardown.
        try:
            self._signup_ctrl.reset()
        except Exception:
            pass
        try:
            if self._examiner_dashboard is not None:
                self._examiner_dashboard.shutdown()
        except Exception:
            pass
        try:
            if self._exam_launch_worker is not None and self._exam_launch_worker.isRunning():
                self._exam_launch_worker.wait(2000)
        except Exception:
            pass
        try:
            if hasattr(self, '_val_worker') and self._val_worker is not None and self._val_worker.isRunning():
                self._val_worker.wait(2000)
        except Exception:
            pass
        try:
            if hasattr(self, '_review_worker') and self._review_worker is not None and self._review_worker.isRunning():
                self._review_worker.wait(2000)
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

        if key in {"dashboard", "home"}:
            self._navigate_to(PAGE_STUDENT_DASHBOARD)
            return

        if key in {"exams", "my exams", "assessments"}:
            if self._exams_page is None:
                self._build_exams_page()
            if self._exams_page is None:
                logger.warning("Exams page could not be built")
                return
            try:
                self._exams_page.refresh_data()
            except Exception as exc:
                logger.warning("Could not refresh Exams page: %s", exc)
            self._navigate_to(PAGE_EXAMS)
            return

        if key in {"reports", "my reports"}:
            if self._reports_page is None:
                self._build_reports_page()
            if self._reports_page is None:
                logger.warning("Reports page could not be built")
                return
            try:
                self._reports_page.refresh_data()
            except Exception as exc:
                logger.warning("Could not refresh Reports page: %s", exc)
            self._navigate_to(PAGE_REPORTS)
            return

        # Page does not exist yet, so keep showing the same dashboard-style dialog.
        if self._student_dashboard is not None:
            self._student_dashboard.show_nav_dialog(label)
