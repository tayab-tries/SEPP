"""Examiner dashboard with class management and live monitoring."""

from __future__ import annotations

import requests
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QDialog,
    QFormLayout,
    QTextEdit,
    QStackedWidget,
)

from client.config import BASE_URL
from client.core.api_worker import ApiWorker
from client.modules.common.loading_spinner import SpinnerOverlay
from client.core.examiner_ws import ExaminerWsClient
from client.modules.examiner_dashboard.views.exam_access_requests_view import ExaminerAccessRequestsView
from client.modules.examiner_dashboard.views.class_view_examiner import ExaminerClassView
from client.modules.examiner_dashboard.views.dashboard_shell import (
    DashboardHeader,
    DashboardNavSpec,
    DashboardScaffold,
    DashboardSidebar,
    DashboardTopBar,
)
from client.modules.examiner_dashboard.views.exam_creation_view import ExamCreationView
from client.modules.examiner_dashboard.views.examiner_exam_monitor_view import ExaminerExamMonitorView
from client.modules.examiner_dashboard.views.examiner_overview import (
    AlertSpec,
    ExamRowSpec,
    ExaminerOverviewPage,
    MetricSpec,
)
from client.modules.examiner_dashboard.settings import ExaminerSettingsView
from client.modules.assessments.assessments_view import ExaminerAssessmentsView
from client.modules.assessments.assessment_details_view import AssessmentDetailsView
from client.modules.assessments.student_logs_view import StudentLogsView
from client.modules.common.design_tokens import (
    COLOR_BG_APP,
    COLOR_BG_CARD,
    COLOR_BG_SOFT,
    COLOR_BORDER_SOFT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_TEXT_DARK,
    COLOR_TEXT_HEAD,
    COLOR_TEXT_MUTED,
    FONT_FAMILY,
    severity_color,
)


# ── HTTP helpers (module-level, safe for ApiWorker threads) ──────────────────

def _http_fetch_classes(headers: dict) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/classes", headers=headers, timeout=10)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_fetch_my_exams(headers: dict) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/exams/examiner/owned", headers=headers, timeout=12)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_fetch_class_exams(headers: dict, class_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/classes/{class_id}/exams", headers=headers, timeout=12)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_fetch_enrollments(headers: dict, class_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/classes/{class_id}/enrollments", headers=headers, timeout=12)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_create_class(headers: dict, payload: dict) -> dict:
    try:
        r = requests.post(f"{BASE_URL}/classes", headers=headers, json=payload, timeout=10)
        return {
            "status": r.status_code,
            "data": r.json() if r.status_code in (200, 201) else None,
            "text": r.text,
        }
    except requests.RequestException as exc:
        return {"status": -1, "data": None, "text": str(exc)}


def _http_patch_exam_status(headers: dict, exam_id: str, new_status: str) -> dict:
    try:
        r = requests.patch(
            f"{BASE_URL}/exams/{exam_id}/status",
            headers=headers,
            json={"status": new_status},
            timeout=12,
        )
        return {"status": r.status_code, "text": r.text}
    except requests.RequestException as exc:
        return {"status": -1, "text": str(exc)}


def _http_delete_exam(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.delete(f"{BASE_URL}/exams/{exam_id}", headers=headers, timeout=12)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_update_enrollment(headers: dict, class_id: str, enrollment_id: str, action: str) -> dict:
    try:
        r = requests.put(
            f"{BASE_URL}/classes/{class_id}/enrollments/{enrollment_id}/{action}",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "text": r.text}
    except requests.RequestException as exc:
        return {"status": -1, "text": str(exc)}


def _http_submit_exam_with_questions(headers: dict, exam_payload: dict, questions: list) -> dict:
    try:
        r = requests.post(f"{BASE_URL}/exams", headers=headers, json=exam_payload, timeout=12)
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"Create exam failed: {r.text}"}
        exam_data = r.json() or {}
        exam_id = exam_data.get("exam_id")
        if not exam_id:
            return {"ok": False, "error": "Create exam succeeded but exam_id missing."}
        for idx, q in enumerate(questions, start=1):
            qr = requests.post(
                f"{BASE_URL}/exams/{exam_id}/questions",
                headers=headers,
                json=q,
                timeout=12,
            )
            if qr.status_code not in (200, 201):
                return {"ok": False, "error": f"Question {idx} failed: {qr.text}. Exam created with partial questions."}
        return {
            "ok": True,
            "exam_id": exam_id,
            "join_code": exam_data.get("join_code") or "",
        }
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def _http_fetch_sessions(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/exams/{exam_id}/sessions", headers=headers, timeout=10)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_fetch_session_events(headers: dict, session_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/sessions/{session_id}/proctoring-events", headers=headers, timeout=10)
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_terminate_session(headers: dict, session_id: str) -> None:
    try:
        requests.post(
            f"{BASE_URL}/sessions/{session_id}/terminate",
            headers=headers,
            json={"reason": "Terminated by examiner dashboard"},
            timeout=10,
        )
    except requests.RequestException:
        pass


def _http_fetch_session_details(headers: dict, session_id: str) -> dict:
    result: dict = {}
    try:
        s = requests.get(f"{BASE_URL}/sessions/{session_id}", headers=headers, timeout=10)
        result["session"] = s.json() if s.status_code == 200 else None
        a = requests.get(f"{BASE_URL}/sessions/{session_id}/answers", headers=headers, timeout=10)
        result["answers"] = a.json() if a.status_code == 200 else None
    except requests.RequestException:
        pass
    return result


def _http_fetch_grading_bundle(headers: dict, session_id: str, exam_id: str) -> dict:
    try:
        s = requests.get(f"{BASE_URL}/sessions/{session_id}", headers=headers, timeout=10)
        a = requests.get(f"{BASE_URL}/sessions/{session_id}/answers", headers=headers, timeout=10)
        e = requests.get(f"{BASE_URL}/exams/{exam_id}", headers=headers, timeout=10)
        q = requests.get(f"{BASE_URL}/exams/{exam_id}/questions", headers=headers, timeout=10)
        
        return {
            "status": 200,
            "session": s.json() if s.status_code == 200 else None,
            "answers": a.json() if a.status_code == 200 else None,
            "exam": e.json() if e.status_code == 200 else None,
            "questions": q.json() if q.status_code == 200 else None,
        }
    except requests.RequestException as exc:
        return {"status": -1, "text": str(exc)}


def _http_submit_grades(headers: dict, session_id: str, payload: dict) -> dict:
    try:
        # payload is { "grades": [ {"question_id": ..., "score": ..., "examiner_comment": ...}, ... ] }
        # Let's send PATCH /sessions/{session_id}/answers/{question_id}/review for each question
        grades = payload.get("grades", [])
        for g in grades:
            requests.patch(
                f"{BASE_URL}/sessions/{session_id}/answers/{g['question_id']}/review",
                headers=headers,
                json={"examiner_score": g["examiner_score"], "examiner_comment": g["examiner_comment"]},
                timeout=12
            )
        return {"status": 200}
    except requests.RequestException as exc:
        return {"status": -1, "text": str(exc)}


def _http_fetch_session_events(headers: dict, session_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/sessions/{session_id}/proctoring-events",
            headers=headers,
            timeout=10,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_fetch_exam_access_requests(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/exams/{exam_id}/access-requests",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_update_exam_access_request(headers: dict, exam_id: str, request_id: str, action: str) -> dict:
    try:
        r = requests.put(
            f"{BASE_URL}/exams/{exam_id}/access-requests/{request_id}/{action}",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_approve_all_access_requests(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.put(
            f"{BASE_URL}/exams/{exam_id}/access-requests/approve-all",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_revoke_all_access_requests(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.put(
            f"{BASE_URL}/exams/{exam_id}/access-requests/revoke-all",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_add_manual_candidate(headers: dict, exam_id: str, email: str) -> dict:
    try:
        r = requests.post(
            f"{BASE_URL}/exams/{exam_id}/access-requests/manual",
            headers=headers,
            json={"email": email},
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code in (200, 201) else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}



def _http_fetch_overview_bundle(headers: dict) -> dict:
    classes_result = _http_fetch_classes(headers)
    exams_result = _http_fetch_my_exams(headers)

    exams = exams_result["data"] if exams_result["status"] == 200 else []
    sessions_by_exam: dict[str, list[dict]] = {}
    recent_alerts: list[dict] = []

    candidate_sessions: list[dict] = []
    for exam in exams or []:
        exam_id = str(exam.get("exam_id") or "")
        if not exam_id:
            continue
        session_result = _http_fetch_sessions(headers, exam_id)
        if session_result["status"] == 200:
            session_rows = session_result["data"] or []
            sessions_by_exam[exam_id] = session_rows
            for row in session_rows:
                merged = dict(row)
                merged["exam_title"] = exam.get("title", "Exam")
                candidate_sessions.append(merged)

    candidate_sessions.sort(
        key=lambda row: (
            int((row.get("proctoring_event_counts") or {}).get("high", 0))
            + int((row.get("proctoring_event_counts") or {}).get("critical", 0))
            + int((row.get("proctoring_event_counts") or {}).get("medium", 0)),
            str(row.get("started_at") or ""),
        ),
        reverse=True,
    )

    for session in candidate_sessions[:6]:
        session_id = str(session.get("session_id") or "")
        if not session_id:
            continue
        events_result = _http_fetch_session_events(headers, session_id)
        if events_result["status"] != 200:
            continue
        for event in (events_result["data"] or [])[:3]:
            merged_event = dict(event)
            merged_event["exam_title"] = session.get("exam_title", "Exam")
            merged_event["student_id"] = session.get("student_id", "")
            merged_event["student_name"] = session.get("student_name", "")
            recent_alerts.append(merged_event)
        if len(recent_alerts) >= 8:
            break

    return {
        "classes": classes_result,
        "exams": exams_result,
        "sessions_by_exam": sessions_by_exam,
        "alerts": recent_alerts[:8],
    }


def _http_dismiss_alert(headers: dict, event_id: str) -> dict:
    try:
        r = requests.post(
            f"{BASE_URL}/proctoring-events/{event_id}/dismiss",
            headers=headers,
            timeout=10,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────

class ExaminerDashboard(QWidget):
    NAV_OVERVIEW = "dashboard"
    NAV_EXAMS = "exams"
    NAV_ASSESSMENTS = "assessments"
    NAV_MONITORING = "monitoring"
    NAV_REPORTS = "reports"
    NAV_SETTINGS = "settings"
    sign_out_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token = ""
        self._user_id = ""
        self._full_name = ""
        self._ws: ExaminerWsClient | None = None

        self._stack = QStackedWidget()
        self._overview_page = ExaminerOverviewPage()
        self._class_page = ExaminerClassView(self._apply_shadow)
        self._exam_creation_page = ExamCreationView(self._apply_shadow)
        self._exam_monitor_page = ExaminerExamMonitorView(self._apply_shadow)
        self._requests_page = ExaminerAccessRequestsView(self._apply_shadow)
        self._assessments_page = ExaminerAssessmentsView(self._apply_shadow)
        self._assessment_details_page = AssessmentDetailsView(self._apply_shadow)
        self._student_logs_page = StudentLogsView(self._apply_shadow)
        self._settings_page = ExaminerSettingsView(self._apply_shadow)
        self._class_rows: list[dict] = []
        self._owned_exam_rows: list[dict] = []
        self._selected_class: dict = {}
        self._selected_requests_exam_id = ""
        self._selected_requests_exam_title = ""
        self._monitor_return_stack: str = "home"
        self._exam_creation_return_stack: str = "overview"
        self._active_exam_title: str = ""
        self._session_generation = 0
        self._live_workers: set[ApiWorker] = set()
        self._overview_refresh_pending = False
        self._my_exams_refresh_pending = False
        self._access_requests_refresh_pending = False
        self._access_requests_pending_exam_id = ""
        self._is_deleted = False

        self._classes = QListWidget()
        self._my_exams = QListWidget()
        self._exam_id_input = QLineEdit()
        self._status = QLabel("Enter exam id and connect.")
        self._sessions = QListWidget()
        self._events = QListWidget()

        # Workers — always stored as instance vars to prevent GC mid-run
        self._classes_worker:    Optional[ApiWorker] = None
        self._overview_worker:   Optional[ApiWorker] = None
        self._my_exams_worker:   Optional[ApiWorker] = None
        self._cls_exams_worker:  Optional[ApiWorker] = None
        self._enrollments_worker:Optional[ApiWorker] = None
        self._create_cls_worker: Optional[ApiWorker] = None
        self._patch_worker:      Optional[ApiWorker] = None
        self._enroll_worker:     Optional[ApiWorker] = None
        self._exam_submit_worker:Optional[ApiWorker] = None
        self._sessions_worker:   Optional[ApiWorker] = None
        self._terminate_worker:  Optional[ApiWorker] = None
        self._details_worker:    Optional[ApiWorker] = None
        self._access_requests_worker: Optional[ApiWorker] = None
        self._access_request_action_worker: Optional[ApiWorker] = None
        self._delete_exam_worker: Optional[ApiWorker] = None

        self._sidebar = DashboardSidebar(
            "SEPP Secure",
            "v2.4.0 Active",
            [
                DashboardNavSpec(self.NAV_OVERVIEW, "Dashboard", "layout-dashboard"),
                DashboardNavSpec(self.NAV_EXAMS, "Exams", "book-open-text"),
                DashboardNavSpec(self.NAV_ASSESSMENTS, "Assessments", "pencil"),
                DashboardNavSpec(self.NAV_MONITORING, "Monitoring", "rotate-cw"),
                DashboardNavSpec(self.NAV_REPORTS, "Reports", "file-chart-line"),
                DashboardNavSpec(self.NAV_SETTINGS, "Settings", "settings"),
            ],
        )
        self._top_bar = DashboardTopBar("Examiner Control Center")
        self._header = DashboardHeader(
            "Examiner Dashboard",
            "A modular workspace for class operations and live invigilation.",
        )
        self._scaffold = DashboardScaffold(self._sidebar, self._top_bar, self._header)

        self._build()
        self._wire()
        # Single overlay reused for every internal page switch
        self._page_spinner = SpinnerOverlay(parent=self._stack)

    def shutdown(self):
        self._stop_ws_worker()
        for worker_name in (
            "_classes_worker",
            "_overview_worker",
            "_my_exams_worker",
            "_cls_exams_worker",
            "_enrollments_worker",
            "_create_cls_worker",
            "_patch_worker",
            "_enroll_worker",
            "_exam_submit_worker",
            "_sessions_worker",
            "_terminate_worker",
            "_details_worker",
            "_access_requests_worker",
            "_access_request_action_worker",
            "_delete_exam_worker",
        ):
            worker = getattr(self, worker_name, None)
            if worker is None:
                continue
            try:
                if worker.isRunning():
                    worker.wait(2000)
            except Exception:
                pass

    def deleteLater(self):
        self._is_deleted = True
        super().deleteLater()

    def _worker_is_running(self, attr_name: str) -> bool:
        worker = getattr(self, attr_name, None)
        if worker is None:
            return False
        try:
            return bool(worker.isRunning())
        except RuntimeError:
            setattr(self, attr_name, None)
            return False

    def _track_worker(self, worker: ApiWorker, attr_name: str | None = None) -> ApiWorker:
        self._live_workers.add(worker)

        def _release(*_args):
            self._live_workers.discard(worker)
            if attr_name and getattr(self, attr_name, None) is worker:
                setattr(self, attr_name, None)
            try:
                worker.deleteLater()
            except Exception:
                pass

        worker.finished.connect(_release)
        worker.errored.connect(_release)
        return worker

    def _reset_session_state(self):
        self._stop_ws_worker()
        self._class_rows = []
        self._owned_exam_rows = []
        self._selected_class = {}
        self._selected_requests_exam_id = ""
        self._selected_requests_exam_title = ""
        self._active_exam_title = ""
        self._my_exams_refresh_pending = False
        self._access_requests_refresh_pending = False
        self._access_requests_pending_exam_id = ""
        self._classes.clear()
        self._my_exams.clear()
        self._sessions.clear()
        self._events.clear()
        self._requests_page.set_exam_rows([])
        self._requests_page.set_status_message("")
        self._requests_page.set_busy(False)
        self._overview_refresh_pending = False

    def _stop_ws_worker(self):
        try:
            if self._ws is not None:
                self._ws.stop()
                self._ws.wait(2000)
        except Exception:
            pass
        finally:
            self._ws = None

    def _switch_page(self, widget: QWidget):
        """Show spinner, switch internal page, hide spinner after first paint."""
        self._page_spinner.show()

        def _do():
            self._stack.setCurrentWidget(widget)
            self._sync_shell_for_page(widget)
            QTimer.singleShot(80, self._page_spinner.hide)

        QTimer.singleShot(0, _do)

    def _build(self):
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BG_APP};
                color: {COLOR_TEXT_DARK};
                font-family: {FONT_FAMILY};
            }}
            QLineEdit {{
                background-color: {COLOR_BG_SOFT};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 8px;
                padding: 8px;
                color: {COLOR_TEXT_DARK};
            }}
            QPushButton {{
                background-color: {COLOR_PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLOR_PRIMARY_HOVER};
            }}
            QListWidget {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 10px;
            }}
            QFrame#mainCard {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 16px;
            }}
            QLabel#sectionHeading {{
                font-size: 18px;
                font-weight: 700;
                color: {COLOR_TEXT_HEAD};
            }}
            QLabel#subtitleLabel {{
                color: {COLOR_TEXT_MUTED};
                font-size: 13px;
            }}
            """
        )
        self._stack.addWidget(self._overview_page)
        self._stack.addWidget(self._class_page)
        self._stack.addWidget(self._exam_creation_page)
        self._stack.addWidget(self._exam_monitor_page)
        self._stack.addWidget(self._requests_page)
        self._stack.addWidget(self._assessments_page)
        self._stack.addWidget(self._assessment_details_page)
        self._stack.addWidget(self._student_logs_page)
        self._stack.addWidget(self._settings_page)
        self._sync_shell_for_page(self._overview_page)
        self._scaffold.set_body(self._stack)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scaffold)

    def _wire(self):
        self._sidebar.nav_selected.connect(self._on_nav_selected)
        self._sidebar.sign_out_requested.connect(self.sign_out_requested.emit)
        self._classes.itemDoubleClicked.connect(self._open_class)
        self._sessions.itemDoubleClicked.connect(self._show_session_details)
        self._class_page.back_requested.connect(self._go_home)
        self._class_page.create_exam_requested.connect(self._create_exam_from_class)
        self._overview_page.new_schedule_clicked.connect(self._open_create_exam_action)
        self._overview_page.delete_draft_requested.connect(self._confirm_delete_draft)
        self._overview_page.status_change_requested.connect(self._patch_exam_status)
        self._overview_page.dismiss_alert_requested.connect(self._dismiss_alert)
        self._class_page.refresh_exams_requested.connect(self._load_class_exams_for_selected)
        self._class_page.refresh_enrollments_requested.connect(self._load_class_enrollments_for_selected)
        self._class_page.enrollment_approve_requested.connect(self._approve_enrollment)
        self._class_page.enrollment_reject_requested.connect(self._reject_enrollment)
        self._class_page.exam_monitor_requested.connect(self._open_exam_monitor_from_class)
        self._class_page.exam_status_change_requested.connect(self._patch_exam_status)
        self._exam_creation_page.back_requested.connect(self._on_exam_creation_back)
        self._exam_creation_page.submit_requested.connect(self._submit_exam_with_questions)
        self._exam_monitor_page.back_requested.connect(self._on_exam_monitor_back)
        self._requests_page.refresh_requested.connect(self._refresh_access_requests_page)
        self._requests_page.exam_selected.connect(self._load_exam_access_requests)
        self._requests_page.approve_requested.connect(self._approve_exam_access_request)
        self._requests_page.reject_requested.connect(self._reject_exam_access_request)
        self._requests_page.approve_all_requested.connect(self._approve_all_access_requests)
        self._requests_page.revoke_all_requested.connect(self._revoke_all_access_requests)
        self._requests_page.add_candidate_requested.connect(self._add_candidate_manually)
        self._assessments_page.assessment_exam_selected.connect(self._on_assessment_exam_selected)
        self._assessment_details_page.back_requested.connect(self._on_assessment_details_back)
        self._assessment_details_page.view_logs_requested.connect(self._on_assessment_view_logs)
        self._assessment_details_page.grade_attempt_requested.connect(self._on_assessment_grade_attempt)
        self._student_logs_page.back_requested.connect(self._on_student_logs_back)

    @Slot(str)
    def _on_assessment_exam_selected(self, exam_id: str):
        self._assessment_details_page.set_exam_context(exam_id)
        self._assessment_details_page.set_loading()
        self._switch_page(self._assessment_details_page)

        if self._worker_is_running("_fetch_assessment_sessions_worker"):
            return
        
        self._fetch_assessment_sessions_worker = self._track_worker(
            ApiWorker(_http_fetch_sessions, self._headers(), exam_id),
            "_fetch_assessment_sessions_worker"
        )
        
        def _on_done(result: dict):
            if result["status"] != 200:
                self._assessment_details_page.set_error(result.get("text", "Unknown error"))
                return
            sessions = result.get("data", [])
            self._assessment_details_page.set_sessions(sessions)
            
        self._fetch_assessment_sessions_worker.finished.connect(_on_done)
        self._fetch_assessment_sessions_worker.errored.connect(
            lambda e: self._assessment_details_page.set_error(str(e))
        )
        self._fetch_assessment_sessions_worker.start()

    @Slot(str)
    def _on_assessment_view_logs(self, session_id: str):
        self._student_logs_page.set_loading()
        self._switch_page(self._student_logs_page)

        if self._worker_is_running("_fetch_session_events_worker"):
            return
        
        self._fetch_session_events_worker = self._track_worker(
            ApiWorker(_http_fetch_session_events, self._headers(), session_id),
            "_fetch_session_events_worker"
        )
        
        def _on_done(result: dict):
            if result["status"] != 200:
                self._student_logs_page.set_error(result.get("text", "Unknown error"))
                return
            events = result.get("data", [])
            self._student_logs_page.set_logs(events, session_id)
            
        self._fetch_session_events_worker.finished.connect(_on_done)
        self._fetch_session_events_worker.errored.connect(
            lambda e: self._student_logs_page.set_error(str(e))
        )
        self._fetch_session_events_worker.start()

    @Slot()
    def _on_student_logs_back(self):
        self._switch_page(self._assessment_details_page)

    @Slot(str)
    def _on_assessment_grade_attempt(self, session_id: str):
        exam_id = self._assessment_details_page._exam_id
        if not exam_id:
            self._assessment_details_page.set_error("No exam context available.")
            return

        if self._worker_is_running("_fetch_grading_bundle_worker"):
            return
            
        self._fetch_grading_bundle_worker = self._track_worker(
            ApiWorker(_http_fetch_grading_bundle, self._headers(), session_id, exam_id),
            "_fetch_grading_bundle_worker"
        )
        
        def _on_done(result: dict):
            if result.get("status") != 200:
                self._assessment_details_page.set_error(result.get("text", "Unknown error fetching grading data"))
                self._switch_page(self._assessment_details_page)
                return
                
            from client.modules.assessments.examinergradingview.views.review_screen_widget import ExaminerGradingScreenWidget
            
            # Unload the old grading page if it exists
            if hasattr(self, "_grading_page") and self._grading_page:
                self._stack.removeWidget(self._grading_page)
                self._grading_page.deleteLater()

            self._grading_page = ExaminerGradingScreenWidget(
                questions=result.get("questions") or [],
                answers=result.get("answers") or [],
                exam=result.get("exam") or {},
                session=result.get("session") or {},
                parent=self
            )
            
            # Connect signals
            self._grading_page.close_requested.connect(lambda: self._switch_page(self._assessment_details_page))
            self._grading_page.submit_grading_requested.connect(self._submit_grades)
            self._grading_page.batch_sync_requested.connect(self._sync_batch)
            
            self._stack.addWidget(self._grading_page)
            self._switch_page(self._grading_page)

        self._fetch_grading_bundle_worker.finished.connect(_on_done)
        self._fetch_grading_bundle_worker.errored.connect(
            lambda e: self._assessment_details_page.set_error(str(e))
        )
        self._fetch_grading_bundle_worker.start()

    @Slot(str, list)
    def _sync_batch(self, session_id: str, question_ids: list):
        if not question_ids:
            if hasattr(self, "_grading_page") and self._grading_page:
                self._grading_page.set_sync_status("")
            return

        from client.modules.assessments.examinergradingview.grading_cache import load_drafts, mark_as_synced
        drafts = load_drafts(session_id)
        grades_payload = []
        for q_id in question_ids:
            draft = drafts.get(q_id, {})
            grades_payload.append({
                "question_id": q_id,
                "examiner_score": draft.get("examiner_score", 0),
                "examiner_comment": draft.get("examiner_comment", "")
            })

        worker = self._track_worker(
            ApiWorker(_http_submit_grades, self._headers(), session_id, {"grades": grades_payload})
        )
        def _on_done(result: dict):
            if result.get("status") == 200:
                mark_as_synced(session_id, question_ids)
                if hasattr(self, "_grading_page") and self._grading_page:
                    self._grading_page.set_sync_status(f"Saved {len(question_ids)} drafts.")
            else:
                if hasattr(self, "_grading_page") and self._grading_page:
                    self._grading_page.set_sync_status("Sync failed, will retry.")

        worker.finished.connect(_on_done)
        worker.errored.connect(lambda e: _on_done({"status": -1}))
        worker.start()

    @Slot(str)
    def _submit_grades(self, session_id: str):
        from client.modules.assessments.examinergradingview.grading_cache import load_drafts, get_unsynced_drafts
        drafts = load_drafts(session_id)
        unsynced = get_unsynced_drafts(session_id)
        
        if not drafts:
            # Nothing to save
            self._switch_page(self._assessment_details_page)
            return
            
        grades_payload = []
        for q_id, draft in unsynced.items():
            grades_payload.append({
                "question_id": q_id,
                "examiner_score": draft.get("examiner_score", 0),
                "examiner_comment": draft.get("examiner_comment", "")
            })

        if self._worker_is_running("_submit_grades_worker"):
            return
            
        self._submit_grades_worker = self._track_worker(
            ApiWorker(_http_submit_grades, self._headers(), session_id, {"grades": grades_payload}),
            "_submit_grades_worker"
        )
        
        def _on_done(result: dict):
            if result.get("status") == 200:
                from client.modules.assessments.examinergradingview.grading_cache import clear_drafts
                clear_drafts(session_id)
            else:
                self._assessment_details_page.set_error(result.get("text", "Failed to submit grades"))
            # Re-fetch assessment sessions to update list
            exam_id = self._assessment_details_page._exam_id
            self._on_assessment_exam_selected(exam_id)
            
        self._submit_grades_worker.finished.connect(_on_done)
        self._submit_grades_worker.errored.connect(
            lambda e: self._assessment_details_page.set_error(str(e))
        )
        self._submit_grades_worker.start()

    @Slot()
    def _on_assessment_details_back(self):
        self._switch_page(self._assessments_page)

    def set_session(self, token: str, user_id: str, full_name: str):
        self._session_generation += 1
        self._reset_session_state()
        self._token = token
        self._user_id = user_id
        self._full_name = full_name
        self._top_bar.update_user_info(full_name)
        self._load_overview_data()

    def _headers(self):
        return {"Authorization": f"Bearer {self._token}"}

    def _apply_shadow(self, widget: QWidget):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor as QtColor

        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(20)
        effect.setOffset(0, 2)
        effect.setColor(QtColor(0, 0, 0, int(255 * 0.03)))
        widget.setGraphicsEffect(effect)

    def _load_overview_data(self):
        if not self._token:
            return
        if self._worker_is_running("_overview_worker"):
            self._overview_refresh_pending = True
            return
        generation = self._session_generation
        self._overview_worker = self._track_worker(
            ApiWorker(_http_fetch_overview_bundle, self._headers()),
            "_overview_worker",
        )
        self._overview_worker.finished.connect(
            lambda result, gen=generation: gen == self._session_generation and self._apply_overview_data(result)
        )
        self._overview_worker.errored.connect(
            lambda e, gen=generation: gen == self._session_generation and self._on_overview_error()
        )
        self._overview_worker.start()

    def _on_overview_error(self):
        self._status.setText("Failed to load examiner overview.")
        if self._overview_refresh_pending:
            self._overview_refresh_pending = False
            self._load_overview_data()

    @Slot(object)
    def _apply_overview_data(self, result: dict):
        if self._is_deleted:
            return

        classes_result = result.get("classes", {})
        exams_result = result.get("exams", {})
        if classes_result.get("status") == 200:
            self._class_rows = classes_result.get("data") or []
            if self._class_rows and not self._selected_class.get("class_id"):
                self._selected_class = dict(self._class_rows[0])

        exam_rows = exams_result.get("data") if exams_result.get("status") == 200 else []
        self._assessments_page.set_exams(exam_rows or [])
        sessions_by_exam = result.get("sessions_by_exam", {})
        alerts = result.get("alerts", [])

        all_sessions: list[dict] = []
        for rows in sessions_by_exam.values():
            all_sessions.extend(rows or [])

        active_sessions = [
            s for s in all_sessions
            if str(s.get("status", "")).lower() in {"active", "locked", "verifying"}
        ]
        live_exams = [
            exam for exam in (exam_rows or [])
            if str(exam.get("status", "")).lower() == "live"
        ]
        flagged_sessions = sum(
            1 for session in all_sessions
            if self._session_is_flagged(session)
        )

        metrics = [
            MetricSpec(
                "blue",
                f"{len(exam_rows or [])} total exams",
                False,
                f"{len(active_sessions):,}",
                "Total Active Students",
                "👥",
            ),
            MetricSpec(
                "red",
                "Live Alerts",
                True,
                str(len(alerts)),
                "Flagged Sessions",
                "⚑",
            ),
            MetricSpec(
                "amber",
                "Derived from live exams",
                False,
                str(len(live_exams)),
                "Proctors Online",
                "🛡",
            ),
        ]

        overview_exams: list[ExamRowSpec] = []
        for exam in (exam_rows or []):
            status = str(exam.get("status") or "").strip().title()
            title = str(exam.get("title") or "Untitled Exam")
            wrapped_title = title.replace(" Fundamentals", "\nFundamentals").replace(" Ethics ", " Ethics\n")
            exam_id = str(exam.get("exam_id") or "")
            join_code = str(exam.get("join_code") or "")
            duration = f"{int(exam.get('duration_minutes') or 0)} Mins"
            exam_sessions = sessions_by_exam.get(exam_id, []) or []
            active_count = sum(
                1 for session in exam_sessions
                if str(session.get("status", "")).lower() in {"active", "locked", "verifying"}
            )
            if str(status).lower() == "active" and active_count > 0:
                students = f"{active_count} Students"
                avatar_count = active_count
            else:
                students = f"{max(len(exam_sessions), 0)} Students"
                avatar_count = 0
            overview_exams.append(
                ExamRowSpec(
                    exam_id=exam_id,
                    exam_name=wrapped_title,
                    join_code=join_code or "Pending",
                    status=status or "Draft",
                    duration=duration,
                    students=students,
                    avatar_count=avatar_count,
                )
            )

        overview_alerts = [self._to_alert_spec(event) for event in alerts]
        self._overview_page.set_overview_data(metrics, overview_exams, overview_alerts, latency_ms=24)
        self._status.setText(f"Loaded examiner overview. {flagged_sessions} flagged sessions.")
        if self._overview_refresh_pending:
            self._overview_refresh_pending = False
            self._load_overview_data()

    def _session_is_flagged(self, session: dict) -> bool:
        counts = session.get("proctoring_event_counts") or {}
        return any(int(counts.get(level, 0)) > 0 for level in ("medium", "high", "critical"))

    def _to_alert_spec(self, event: dict) -> AlertSpec:
        from client.core.contracts import resolve_student_name
        severity = str(event.get("severity") or "info").lower()
        student_disp = resolve_student_name(event)
        event_type = str(event.get("event_type") or "event").replace("_", " ").title()
        body = self._event_body(event)
        event_id = str(event.get("event_id") or event.get("id") or "")
        return AlertSpec(
            event_id=event_id,
            severity=severity if severity in {"critical", "moderate", "info"} else ("moderate" if severity in {"medium", "high"} else "info"),
            title=f"{student_disp} - {event_type}",
            body=body,
            age=self._relative_age(event.get("timestamp") or event.get("server_received_at")),
            action_primary=self._primary_action_for_severity(severity),
            action_secondary="Dismiss" if severity in {"critical", "high"} else ("Warn" if severity in {"medium", "moderate"} else ""),
        )

    def _event_body(self, event: dict) -> str:
        metadata = event.get("metadata") or {}
        if isinstance(metadata, dict) and metadata:
            parts = [f"{key}: {value}" for key, value in list(metadata.items())[:2]]
            return " | ".join(parts)
        return f"Detected during {event.get('exam_title', 'exam monitoring')}."

    def _relative_age(self, value) -> str:
        if not value:
            return "just now"
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                dt = value
            now = datetime.utcnow().replace(tzinfo=getattr(dt, "tzinfo", None))
            delta = now - dt
            minutes = max(int(delta.total_seconds() // 60), 0)
            if minutes < 1:
                return "just now"
            if minutes == 1:
                return "1 min ago"
            if minutes < 60:
                return f"{minutes} mins ago"
            hours = minutes // 60
            return f"{hours}h ago"
        except Exception:
            return "recently"

    def _primary_action_for_severity(self, severity: str) -> str:
        normalized = severity.lower()
        if normalized in {"critical", "high"}:
            return "Intervene"
        if normalized in {"medium", "moderate"}:
            return "Review"
        return "Logged"

    def _sync_shell_for_page(self, widget: QWidget):
        if widget is self._overview_page:
            self._sidebar.set_active(self.NAV_OVERVIEW)
            self._top_bar.set_section_title("Examiner Control Center")
            self._scaffold.set_header_visible(False)
            return

        if widget is self._exam_creation_page:
            self._sidebar.set_active(self.NAV_EXAMS)
            self._top_bar.set_section_title("Exam Authoring")
            self._scaffold.set_header_visible(True)
            self._header.set_text(
                "Create Exam",
                "Author a joinable exam directly, then schedule it or move it live.",
            )
            return

        if widget is self._class_page:
            class_name = str(self._selected_class.get("name") or "Selected class")
            self._sidebar.set_active(self.NAV_EXAMS)
            self._top_bar.set_section_title("Exam Workspace")
            self._scaffold.set_header_visible(True)
            self._header.set_text(
                "Exam Workspace",
                f"Review legacy class-linked exam data for {class_name}.",
            )
            return

        if widget is self._exam_monitor_page:
            exam_title = self._active_exam_title or "Live monitoring"
            self._sidebar.set_active(self.NAV_MONITORING)
            self._top_bar.set_section_title("Monitoring Center")
            self._scaffold.set_header_visible(True)
            self._header.set_text(
                "Exam Monitor",
                f"Review alerts, sessions, and answers for {exam_title}.",
            )
            return

        if widget is self._assessments_page:
            self._sidebar.set_active(self.NAV_ASSESSMENTS)
            self._top_bar.set_section_title("Assessments")
            self._scaffold.set_header_visible(True)
            self._header.set_text(
                "Assessments",
                "View and grade all submitted exam assessments.",
            )
            return

        if widget is self._requests_page:
            self._sidebar.set_active(self.NAV_REPORTS)
            self._top_bar.set_section_title("Access Request Center")
            self._scaffold.set_header_visible(False)
            return

        if widget is self._settings_page:
            self._sidebar.set_active(self.NAV_SETTINGS)
            self._top_bar.set_section_title("Policy Controls")
            self._scaffold.set_header_visible(True)
            self._header.set_text(
                "Examiner Settings",
                "Adjust static monitoring thresholds, permissions, and lockdown defaults for the new examiner-side theme.",
            )

    @Slot(str)
    def _on_nav_selected(self, label: str):
        if label == self.NAV_OVERVIEW:
            self._go_home()
            return
        if label == self.NAV_EXAMS:
            self._open_create_exam_action()
            return
        if label == self.NAV_ASSESSMENTS:
            self._switch_page(self._assessments_page)
            return
        if label == self.NAV_MONITORING:
            if self._stack.currentWidget() is self._exam_monitor_page:
                return
            if self._active_exam_title:
                self._switch_page(self._exam_monitor_page)
            else:
                self._go_home()
            return
        if label == self.NAV_REPORTS:
            self._open_access_requests_page()
            return
        if label == self.NAV_SETTINGS:
            self._switch_page(self._settings_page)
            return

    @Slot()
    def _open_create_class_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Class")
        dialog.setModal(True)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_input = QLineEdit()
        desc_input = QTextEdit()
        desc_input.setFixedHeight(90)
        form.addRow("Course / Subject name", name_input)
        form.addRow("Description", desc_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        create = QPushButton("Create")
        row.addStretch(1)
        row.addWidget(cancel)
        row.addWidget(create)
        layout.addLayout(row)
        cancel.clicked.connect(dialog.reject)

        def _submit():
            name = name_input.text().strip()
            if not name:
                self._status.setText("Class name is required.")
                return
            payload = {
                "name": name,
                "description": desc_input.toPlainText().strip() or None,
            }
            create.setEnabled(False)
            cancel.setEnabled(False)
            self._create_cls_worker = ApiWorker(_http_create_class, self._headers(), payload)

            def _on_done(result: dict):
                if result["status"] not in (200, 201):
                    self._status.setText(f"Create class failed: {result['text']}")
                    create.setEnabled(True)
                    cancel.setEnabled(True)
                    return
                self._status.setText("Class created successfully.")
                dialog.accept()
                self._load_overview_data()

            self._create_cls_worker.finished.connect(_on_done)
            self._create_cls_worker.errored.connect(
                lambda e: (
                    self._status.setText("Network error while creating class."),
                    create.setEnabled(True),
                    cancel.setEnabled(True),
                )
            )
            self._create_cls_worker.start()

        create.clicked.connect(_submit)
        dialog.exec()

    def _refresh_classes(self):
        if not self._token:
            return
        generation = self._session_generation
        self._classes_worker = self._track_worker(
            ApiWorker(_http_fetch_classes, self._headers()),
            "_classes_worker",
        )
        self._classes_worker.finished.connect(
            lambda result, gen=generation: gen == self._session_generation and self._apply_classes(result)
        )
        self._classes_worker.errored.connect(
            lambda e, gen=generation: gen == self._session_generation and self._on_classes_error(e)
        )
        self._classes_worker.start()

    def _on_classes_error(self, e: str):
        self._classes.addItem("Network error while loading classes.")
        self._load_my_exams()

    @Slot(object)
    def _apply_classes(self, result: dict):
        self._classes.clear()
        if result["status"] != 200:
            self._classes.addItem("Unable to load classes.")
            self._load_my_exams()
            return
        self._class_rows = result["data"] or []
        if self._class_rows and not self._selected_class.get("class_id"):
            self._selected_class = dict(self._class_rows[0])
        if not self._class_rows:
            self._classes.addItem("No classes created yet.")
        else:
            for row in self._class_rows:
                item = QListWidgetItem(
                    f"{row.get('name', 'Class')} | Code: {row.get('join_code', 'N/A')}"
                )
                item.setData(Qt.ItemDataRole.UserRole, row)
                self._classes.addItem(item)
        self._load_my_exams()

    def _load_my_exams(self):
        if not self._token:
            return
        if self._worker_is_running("_my_exams_worker"):
            self._my_exams_refresh_pending = True
            return
        self._my_exams_refresh_pending = False
        self._my_exams.clear()
        generation = self._session_generation
        self._my_exams_worker = self._track_worker(
            ApiWorker(_http_fetch_my_exams, self._headers()),
            "_my_exams_worker",
        )
        self._my_exams_worker.finished.connect(
            lambda result, gen=generation: gen == self._session_generation and self._apply_my_exams(result)
        )
        self._my_exams_worker.errored.connect(
            lambda e, gen=generation: gen == self._session_generation and self._on_my_exams_error()
        )
        self._my_exams_worker.start()

    @Slot(object)
    def _apply_my_exams(self, result: dict):
        self._my_exams.clear()
        if result["status"] != 200:
            self._my_exams.addItem("Unable to load exams.")
            self._owned_exam_rows = []
            self._requests_page.set_exam_rows([])
            self._requests_page.set_busy(False)
            self._maybe_refresh_my_exams()
            return
        rows = result["data"] or []
        self._owned_exam_rows = rows
        if not rows:
            self._my_exams.addItem("No exams yet. Create one inside a class.")
            self._requests_page.set_exam_rows([])
            self._requests_page.set_busy(False)
            self._maybe_refresh_my_exams()
            return
        for row in rows:
            item = QListWidgetItem(
                f"{row.get('title', 'Exam')} | {row.get('class_name', 'Class')} | {row.get('status', '')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._my_exams.addItem(item)
        if self._selected_requests_exam_id and not any(
            str(row.get("exam_id") or "") == self._selected_requests_exam_id
            for row in rows
        ):
            self._selected_requests_exam_id = ""
            self._selected_requests_exam_title = ""
        self._requests_page.set_exam_rows(rows)
        if self._stack.currentWidget() is self._requests_page:
            if self._selected_requests_exam_id:
                self._load_exam_access_requests(self._selected_requests_exam_id)
            else:
                self._requests_page.set_busy(False)
        self._maybe_refresh_my_exams()

    def _on_my_exams_error(self):
        self._my_exams.addItem("Network error while loading exams.")
        self._requests_page.set_exam_rows([])
        self._requests_page.set_status_message("Network error while loading owned exams.")
        self._maybe_refresh_my_exams()

    def _maybe_refresh_my_exams(self):
        if self._my_exams_refresh_pending:
            self._my_exams_refresh_pending = False
            QTimer.singleShot(0, self._load_my_exams)

    def _load_class_exams_for_selected(self):
        class_id = self._selected_class.get("class_id")
        if not class_id or not self._token:
            return
        self._cls_exams_worker = ApiWorker(_http_fetch_class_exams, self._headers(), class_id)
        self._cls_exams_worker.finished.connect(self._apply_class_exams)
        self._cls_exams_worker.errored.connect(
            lambda e: (self._class_page.set_exams([]), self._status.setText("Network error while loading class exams."))
        )
        self._cls_exams_worker.start()

    @Slot(object)
    def _apply_class_exams(self, result: dict):
        if result["status"] != 200:
            self._class_page.set_exams([])
            self._status.setText(f"Class exams load failed: {result['data']!s:.200}")
            return
        self._class_page.set_exams(result["data"] or [])

    def _load_class_enrollments_for_selected(self):
        class_id = self._selected_class.get("class_id")
        if not class_id or not self._token:
            return
        self._enrollments_worker = ApiWorker(_http_fetch_enrollments, self._headers(), class_id)
        self._enrollments_worker.finished.connect(self._apply_enrollments)
        self._enrollments_worker.errored.connect(
            lambda e: (self._class_page.set_enrollments([]), self._status.setText("Network error while loading enrollments."))
        )
        self._enrollments_worker.start()

    @Slot(object)
    def _apply_enrollments(self, result: dict):
        if result["status"] != 200:
            self._class_page.set_enrollments([])
            self._status.setText(f"Enrollments load failed: {result['data']!s:.200}")
            return
        self._class_page.set_enrollments(result["data"] or [])

    @Slot(QListWidgetItem)
    def _open_class(self, item: QListWidgetItem):
        payload = item.data(Qt.ItemDataRole.UserRole) or {}
        if not payload.get("class_id"):
            return
        self._selected_class = payload
        self._class_page.set_class_payload(payload)
        self._load_class_exams_for_selected()
        self._load_class_enrollments_for_selected()
        self._switch_page(self._class_page)

    @Slot()
    def _go_home(self):
        self._switch_page(self._overview_page)
        self._load_overview_data()

    @Slot(dict)
    def _create_exam_from_class(self, class_payload: dict):
        self._selected_class = dict(class_payload or {})
        self._exam_creation_return_stack = "class"
        self._exam_creation_page.set_class_payload(class_payload)
        self._switch_page(self._exam_creation_page)

    @Slot()
    def _open_create_exam_action(self):
        self._exam_creation_return_stack = "overview"
        if not self._selected_class.get("class_id") and self._class_rows:
            self._selected_class = dict(self._class_rows[0])
        self._exam_creation_page.set_exam_context("Create a joinable exam")
        self._exam_creation_page.set_status_message("")
        self._switch_page(self._exam_creation_page)

    @Slot(str)
    def _confirm_delete_draft(self, exam_id: str):
        if not exam_id:
            return
        row = next(
            (exam for exam in self._owned_exam_rows if str(exam.get("exam_id") or "") == exam_id),
            {},
        )
        title = str(row.get("title") or "this draft exam")
        from client.Shared.info_dialog import InfoDialog

        dlg = InfoDialog(
            title="Delete Draft Exam",
            body=(
                f'Are you sure you want to delete "{title}"?\n\n'
                "This removes the draft exam and its questions permanently."
            ),
            parent=self,
            confirm_label="Delete Draft",
            cancel_label="Keep",
        )
        dlg.confirmed.connect(lambda eid=exam_id: self._delete_draft_exam(eid))
        dlg.exec_()

    def _delete_draft_exam(self, exam_id: str):
        if not exam_id or not self._token:
            return
        if self._worker_is_running("_delete_exam_worker"):
            return
        self._status.setText("Deleting draft exam…")
        generation = self._session_generation
        self._delete_exam_worker = self._track_worker(
            ApiWorker(_http_delete_exam, self._headers(), exam_id),
            "_delete_exam_worker",
        )

        def _on_done(result: dict):
            if generation != self._session_generation:
                return
            if result["status"] != 200:
                detail = str(result.get("data") or "Unknown error.")
                self._status.setText(f"Delete draft failed: {detail[:300]}")
                return
            if self._selected_requests_exam_id == exam_id:
                self._selected_requests_exam_id = ""
                self._selected_requests_exam_title = ""
            self._status.setText("Draft exam deleted.")
            self._load_overview_data()
            self._load_my_exams()
            if self._stack.currentWidget() is self._requests_page:
                self._requests_page.set_status_message("Draft exam deleted.")
                self._requests_page.set_busy(False)

        self._delete_exam_worker.finished.connect(_on_done)
        self._delete_exam_worker.errored.connect(
            lambda e: generation == self._session_generation and self._status.setText(
                "Network error while deleting draft exam."
            )
        )
        self._delete_exam_worker.start()

    @Slot()
    def _open_access_requests_page(self):
        self._switch_page(self._requests_page)
        self._refresh_access_requests_page()

    @Slot()
    def _on_exam_creation_back(self):
        if self._exam_creation_return_stack == "class" and self._selected_class.get("class_id"):
            self._switch_page(self._class_page)
            return
        self._switch_page(self._overview_page)

    @Slot(dict)
    def _open_exam_monitor_from_class(self, exam_row: dict):
        self._monitor_return_stack = "class"
        self._active_exam_title = str(exam_row.get("title") or "Exam")
        self._exam_monitor_page.configure(self._token, exam_row)
        self._switch_page(self._exam_monitor_page)

    @Slot(QListWidgetItem)
    def _open_monitor_from_my_exams_item(self, item: QListWidgetItem):
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        if not row.get("exam_id"):
            return
        self._monitor_return_stack = "home"
        self._active_exam_title = str(row.get("title") or "Exam")
        self._exam_monitor_page.configure(self._token, row)
        self._switch_page(self._exam_monitor_page)

    @Slot()
    def _on_exam_monitor_back(self):
        if self._monitor_return_stack == "class":
            self._switch_page(self._class_page)
            self._load_class_exams_for_selected()
        else:
            self._switch_page(self._overview_page)

    def _refresh_access_requests_page(self):
        self._requests_page.set_status_message("Refreshing exam access requests…")
        self._load_my_exams()
        if self._selected_requests_exam_id:
            self._load_exam_access_requests(self._selected_requests_exam_id)

    @Slot(str)
    def _load_exam_access_requests(self, exam_id: str):
        if not exam_id or not self._token:
            return
        selected_row = next(
            (row for row in self._owned_exam_rows if str(row.get("exam_id") or "") == exam_id),
            {},
        )
        self._selected_requests_exam_id = exam_id
        self._selected_requests_exam_title = str(selected_row.get("title") or "Selected exam")
        self._requests_page.set_selected_exam(selected_row)
        if self._worker_is_running("_access_requests_worker"):
            self._access_requests_refresh_pending = True
            self._access_requests_pending_exam_id = exam_id
            self._requests_page.set_status_message(
                f"Refreshing access requests for {self._selected_requests_exam_title}…"
            )
            self._requests_page.set_busy(True)
            return
        self._access_requests_refresh_pending = False
        self._access_requests_pending_exam_id = ""
        self._requests_page.set_status_message(
            f"Loading access requests for {self._selected_requests_exam_title}…"
        )
        self._requests_page.set_busy(True)
        generation = self._session_generation
        self._access_requests_worker = self._track_worker(
            ApiWorker(
                _http_fetch_exam_access_requests,
                self._headers(),
                exam_id,
            ),
            "_access_requests_worker",
        )
        self._access_requests_worker.finished.connect(
            lambda result, gen=generation, requested_exam_id=exam_id: gen == self._session_generation and self._apply_exam_access_requests(result, requested_exam_id)
        )
        self._access_requests_worker.errored.connect(
            lambda e, gen=generation: gen == self._session_generation and (
                self._requests_page.set_busy(False),
                self._requests_page.set_status_message(
                    "Network error while loading exam access requests."
                ),
                self._maybe_refresh_access_requests(),
            )
        )
        self._access_requests_worker.start()

    @Slot(object)
    def _apply_exam_access_requests(self, result: dict, requested_exam_id: str | None = None):
        if requested_exam_id and requested_exam_id != self._selected_requests_exam_id:
            self._maybe_refresh_access_requests()
            return
        self._requests_page.set_busy(False)
        if result["status"] != 200:
            self._requests_page.set_requests(self._selected_requests_exam_title, [])
            self._requests_page.set_status_message(
                f"Access request load failed: {str(result['data'])[:300]}"
            )
            self._maybe_refresh_access_requests()
            return
        rows = result["data"] or []
        self._requests_page.set_requests(self._selected_requests_exam_title, rows)
        pending = sum(1 for row in rows if not bool(row.get("approved")))
        self._requests_page.set_status_message(
            f"{len(rows)} total requests loaded for {self._selected_requests_exam_title}. {pending} pending approval."
        )
        self._maybe_refresh_access_requests()

    def _maybe_refresh_access_requests(self):
        target_exam_id = self._access_requests_pending_exam_id or self._selected_requests_exam_id
        if self._access_requests_refresh_pending and target_exam_id:
            self._access_requests_refresh_pending = False
            self._access_requests_pending_exam_id = ""
            QTimer.singleShot(
                0,
                lambda exam_id=target_exam_id: self._load_exam_access_requests(exam_id),
            )

    @Slot(str, str)
    def _approve_exam_access_request(self, exam_id: str, request_id: str):
        self._update_exam_access_request(exam_id, request_id, "approve")

    @Slot(str, str)
    def _reject_exam_access_request(self, exam_id: str, request_id: str):
        self._update_exam_access_request(exam_id, request_id, "reject")

    def _update_exam_access_request(self, exam_id: str, request_id: str, action: str):
        if not exam_id or not request_id or not self._token:
            return
        self._requests_page.set_status_message(f"{action.title()}ing request…")
        self._requests_page.set_busy(True)
        generation = self._session_generation
        self._access_request_action_worker = self._track_worker(
            ApiWorker(
                _http_update_exam_access_request,
                self._headers(),
                exam_id,
                request_id,
                action,
            ),
            "_access_request_action_worker",
        )

        def _on_done(result: dict):
            if generation != self._session_generation:
                return
            if result["status"] != 200:
                self._requests_page.set_busy(False)
                self._requests_page.set_status_message(
                    f"Request {action} failed: {str(result['data'])[:300]}"
                )
                return
            self._requests_page.set_status_message(f"Request {action}d successfully.")
            self._refresh_access_requests_page()
            self._load_overview_data()

        self._access_request_action_worker.finished.connect(_on_done)
        self._access_request_action_worker.errored.connect(
            lambda e: generation == self._session_generation and (
                self._requests_page.set_busy(False),
                self._requests_page.set_status_message(
                    f"Network error while trying to {action} the request."
                ),
            )
        )
        self._access_request_action_worker.start()

    @Slot(str)
    def _dismiss_alert(self, event_id: str):
        if not event_id or not self._token:
            return
        # We start an ApiWorker to call the dismiss endpoint on the server
        worker = self._track_worker(
            ApiWorker(_http_dismiss_alert, self._headers(), event_id)
        )
        def _on_done(result: dict):
            if result.get("status") == 200:
                self._status.setText("Alert dismissed successfully.")
                self._load_overview_data()  # Refresh overview data
            else:
                self._status.setText(f"Failed to dismiss alert: {result.get('text', 'Unknown error')}")

        worker.finished.connect(_on_done)
        worker.errored.connect(lambda e: self._status.setText(f"Network error dismissing alert: {e}"))
        worker.start()

    @Slot(str, str)
    def _patch_exam_status(self, exam_id: str, new_status: str):
        if not exam_id or not self._token:
            return
        if self._worker_is_running("_patch_worker"):
            return
        self._patch_worker = self._track_worker(
            ApiWorker(_http_patch_exam_status, self._headers(), exam_id, new_status),
            "_patch_worker"
        )

        def _on_done(result: dict):
            if result["status"] != 200:
                self._status.setText(f"Status update failed: {result['text'][:300]}")
                return
            self._status.setText(f"Exam {exam_id} → {new_status}")
            self._load_class_exams_for_selected()
            self._load_overview_data()
            self._load_my_exams()

        self._patch_worker.finished.connect(_on_done)
        self._patch_worker.errored.connect(
            lambda e: self._status.setText("Network error while updating exam status.")
        )
        self._patch_worker.start()

    @Slot(str, str)
    def _approve_enrollment(self, class_id: str, enrollment_id: str):
        self._update_enrollment(class_id, enrollment_id, "approve")

    @Slot(str, str)
    def _reject_enrollment(self, class_id: str, enrollment_id: str):
        self._update_enrollment(class_id, enrollment_id, "reject")

    def _update_enrollment(self, class_id: str, enrollment_id: str, action: str):
        if not class_id or not enrollment_id or not self._token:
            return
        self._enroll_worker = ApiWorker(
            _http_update_enrollment, self._headers(), class_id, enrollment_id, action
        )

        def _on_done(result: dict):
            if result["status"] != 200:
                self._status.setText(f"Enrollment {action} failed: {result['text'][:300]}")
                return
            self._status.setText(f"Enrollment {action}d.")
            self._load_class_enrollments_for_selected()

        self._enroll_worker.finished.connect(_on_done)
        self._enroll_worker.errored.connect(
            lambda e: self._status.setText(f"Network error while trying to {action} enrollment.")
        )
        self._enroll_worker.start()

    @Slot(dict, list)
    def _submit_exam_with_questions(self, exam_payload: dict, questions: list):
        if self._worker_is_running("_exam_submit_worker"):
            return
        self._exam_creation_page.set_submit_busy(True)
        class_id = str(exam_payload.get("class_id") or self._selected_class.get("class_id") or "")
        if not class_id and self._class_rows:
            class_id = str((self._class_rows[0] or {}).get("class_id") or "")
            if class_id:
                self._selected_class = dict(self._class_rows[0])
        if not class_id:
            self._status.setText("Creating default exam group…")
            self._exam_creation_page.set_status_message(
                "No exam group found. Creating a default compatibility group first…"
            )
            default_class_payload = {
                "name": "General Exam Group",
                "description": "Auto-created to support exam draft creation while the backend still requires class ownership.",
            }
            self._create_cls_worker = ApiWorker(_http_create_class, self._headers(), default_class_payload)

            def _on_class_created(result: dict):
                if result["status"] not in (200, 201):
                    message = f"Auto-create class failed: {result['text']}"
                    self._status.setText(message)
                    self._exam_creation_page.set_status_message(message)
                    self._exam_creation_page.set_submit_busy(False)
                    return
                row = result.get("data") or {}
                if not row.get("class_id"):
                    message = "Auto-created class response was missing class_id."
                    self._status.setText(message)
                    self._exam_creation_page.set_status_message(message)
                    self._exam_creation_page.set_submit_busy(False)
                    return
                self._selected_class = dict(row)
                self._class_rows = [dict(row), *[existing for existing in self._class_rows if str(existing.get("class_id") or "") != str(row.get("class_id") or "")]]
                self._submit_exam_with_questions(exam_payload, questions)

            self._create_cls_worker.finished.connect(_on_class_created)
            self._create_cls_worker.errored.connect(
                lambda e: (
                    self._status.setText("Network error while auto-creating the default exam group."),
                    self._exam_creation_page.set_status_message(
                        "Network error while auto-creating the default exam group."
                    ),
                    self._exam_creation_page.set_submit_busy(False),
                )
            )
            self._create_cls_worker.start()
            return

        payload = dict(exam_payload)
        payload["class_id"] = class_id
        self._status.setText("Creating exam…")
        self._exam_creation_page.set_status_message("Creating draft exam…")
        self._exam_submit_worker = ApiWorker(
            _http_submit_exam_with_questions, self._headers(), payload, questions
        )

        def _on_done(result: dict):
            if not result.get("ok"):
                message = result.get("error", "Unknown error.")
                self._status.setText(message)
                self._exam_creation_page.set_status_message(message)
                self._exam_creation_page.set_submit_busy(False)
                return
            exam_id = result.get("exam_id", "")
            join_code = result.get("join_code", "")
            message = (
                f"Draft exam created (exam_id={exam_id}, join_code={join_code}). "
                "Use the examiner dashboard to schedule it or move it live."
            )
            self._status.setText(message)
            self._exam_creation_page.set_submit_busy(False)
            self._load_overview_data()
            self._switch_page(self._overview_page)

        self._exam_submit_worker.finished.connect(_on_done)
        self._exam_submit_worker.errored.connect(
            lambda e: (
                self._status.setText("Network error while creating exam/questions."),
                self._exam_creation_page.set_status_message("Network error while creating exam/questions."),
                self._exam_creation_page.set_submit_busy(False),
            )
        )
        self._exam_submit_worker.start()

    @Slot()
    def _connect_exam(self):
        exam_id = self._exam_id_input.text().strip()
        if not exam_id:
            self._status.setText("Enter exam id first.")
            return
        self._stop_ws_worker()
        self._ws = ExaminerWsClient(exam_id=exam_id, token=self._token)
        self._ws.connected.connect(lambda: self._status.setText(f"Connected to exam {exam_id}."))
        self._ws.disconnected.connect(lambda: self._status.setText("Live monitor disconnected. Retrying..."))
        self._ws.error.connect(self._append_error_event)
        self._ws.event_received.connect(self._on_ws_event)
        self._ws.start()
        self._refresh_sessions()

    @Slot()
    def _refresh_sessions(self):
        exam_id = self._exam_id_input.text().strip()
        if not exam_id:
            return
        self._sessions_worker = ApiWorker(_http_fetch_sessions, self._headers(), exam_id)
        self._sessions_worker.finished.connect(self._apply_sessions)
        self._sessions_worker.errored.connect(
            lambda e: self._status.setText("Network error while loading sessions.")
        )
        self._sessions_worker.start()

    @Slot(object)
    def _apply_sessions(self, result: dict):
        if result["status"] != 200:
            self._status.setText(f"Session load failed: {result['data']}")
            return
        rows = result["data"] or []
        self._sessions.clear()
        for row in rows:
            integrity = row.get("integrity_score")
            integrity_text = f"{float(integrity):.0f}" if integrity is not None else "N/A"
            gaze_count = int(row.get("gaze_away_count") or 0)
            label = (
                f"{row.get('session_id')} | {row.get('status')} | "
                f"student {row.get('student_id')} | integrity {integrity_text} | gaze {gaze_count}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._sessions.addItem(item)
        self._status.setText(f"Loaded {len(rows)} session cards.")

    @Slot(dict)
    def _on_ws_event(self, payload: dict):
        stamp = datetime.utcnow().strftime("%H:%M:%S")
        event_type = str(payload.get("type", "unknown"))
        severity = str(payload.get("severity", "info"))
        item = QListWidgetItem(f"[{stamp}] {event_type} | {payload}")
        item.setForeground(QColor(severity_color(severity)))
        self._events.insertItem(0, item)

        # Real-time update of metrics and active students counts
        if event_type in ("student_status_update", "student_flag"):
            self._load_overview_data()
            self._refresh_sessions()

    @Slot(str)
    def _append_error_event(self, message: str):
        self._events.insertItem(0, f"[error] {message}")

    @Slot()
    def _pause_exam(self):
        if self._ws:
            self._ws.pause_exam()

    @Slot()
    def _end_exam(self):
        if self._ws:
            self._ws.end_exam()

    @Slot()
    def _terminate_selected_session(self):
        item = self._sessions.currentItem()
        if item is None:
            self._status.setText("Select a session to terminate.")
            return
        session = item.data(Qt.ItemDataRole.UserRole) or {}
        session_id = str(session.get("session_id", ""))
        if not session_id:
            return
        if self._ws:
            self._ws.terminate_session(session_id)
        self._terminate_worker = ApiWorker(_http_terminate_session, self._headers(), session_id)
        self._terminate_worker.finished.connect(lambda _: self._refresh_sessions())
        self._terminate_worker.errored.connect(lambda e: self._refresh_sessions())
        self._terminate_worker.start()

    @Slot(QListWidgetItem)
    def _show_session_details(self, item: QListWidgetItem):
        payload = item.data(Qt.ItemDataRole.UserRole) or {}
        session_id = str(payload.get("session_id", ""))
        if not session_id:
            return
        self._details_worker = ApiWorker(_http_fetch_session_details, self._headers(), session_id)

        def _on_done(result: dict):
            if result.get("session") is not None:
                self._events.insertItem(0, f"[session] {result['session']}")
            if result.get("answers") is not None:
                self._events.insertItem(0, f"[answers] count={len(result['answers'] or [])}")

        self._details_worker.finished.connect(_on_done)
        self._details_worker.errored.connect(
            lambda e: self._status.setText("Failed to load session detail.")
        )
        self._details_worker.start()

    @Slot(str)
    def _approve_all_access_requests(self, exam_id: str):
        if not exam_id or not self._token:
            return
        self._requests_page.set_status_message("Approving all requests…")
        self._requests_page.set_busy(True)
        generation = self._session_generation
        self._access_request_action_worker = self._track_worker(
            ApiWorker(
                _http_approve_all_access_requests,
                self._headers(),
                exam_id,
            ),
            "_access_request_action_worker",
        )

        def _on_done(result: dict):
            if generation != self._session_generation:
                return
            if result["status"] != 200:
                self._requests_page.set_busy(False)
                self._requests_page.set_status_message(
                    f"Approve all failed: {str(result['data'])[:300]}"
                )
                return
            self._requests_page.set_status_message("All requests approved successfully.")
            self._refresh_access_requests_page()
            self._load_overview_data()

        self._access_request_action_worker.finished.connect(_on_done)
        self._access_request_action_worker.errored.connect(
            lambda e: generation == self._session_generation and (
                self._requests_page.set_busy(False),
                self._requests_page.set_status_message("Network error while trying to approve all requests."),
            )
        )
        self._access_request_action_worker.start()

    @Slot(str)
    def _revoke_all_access_requests(self, exam_id: str):
        if not exam_id or not self._token:
            return
        self._requests_page.set_status_message("Revoking all access…")
        self._requests_page.set_busy(True)
        generation = self._session_generation
        self._access_request_action_worker = self._track_worker(
            ApiWorker(
                _http_revoke_all_access_requests,
                self._headers(),
                exam_id,
            ),
            "_access_request_action_worker",
        )

        def _on_done(result: dict):
            if generation != self._session_generation:
                return
            if result["status"] != 200:
                self._requests_page.set_busy(False)
                self._requests_page.set_status_message(
                    f"Revoke all failed: {str(result['data'])[:300]}"
                )
                return
            self._requests_page.set_status_message("All access revoked successfully.")
            self._refresh_access_requests_page()
            self._load_overview_data()

        self._access_request_action_worker.finished.connect(_on_done)
        self._access_request_action_worker.errored.connect(
            lambda e: generation == self._session_generation and (
                self._requests_page.set_busy(False),
                self._requests_page.set_status_message("Network error while trying to revoke all access."),
            )
        )
        self._access_request_action_worker.start()

    @Slot(str, str)
    def _add_candidate_manually(self, exam_id: str, email: str):
        if not exam_id or not email or not self._token:
            return
        self._requests_page.set_status_message(f"Adding candidate {email}…")
        self._requests_page.set_busy(True)
        generation = self._session_generation
        self._access_request_action_worker = self._track_worker(
            ApiWorker(
                _http_add_manual_candidate,
                self._headers(),
                exam_id,
                email,
            ),
            "_access_request_action_worker",
        )

        def _on_done(result: dict):
            if generation != self._session_generation:
                return
            if result["status"] not in (200, 201):
                self._requests_page.set_busy(False)
                self._requests_page.set_status_message(
                    f"Add candidate failed: {str(result['data'])[:300]}"
                )
                return
            self._requests_page.set_status_message(f"Candidate {email} added successfully.")
            self._refresh_access_requests_page()
            self._load_overview_data()

        self._access_request_action_worker.finished.connect(_on_done)
        self._access_request_action_worker.errored.connect(
            lambda e: generation == self._session_generation and (
                self._requests_page.set_busy(False),
                self._requests_page.set_status_message("Network error while trying to add candidate."),
            )
        )
        self._access_request_action_worker.start()

