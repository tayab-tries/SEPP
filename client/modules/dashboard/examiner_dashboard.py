"""Examiner dashboard with class management and live monitoring."""

from __future__ import annotations

import requests
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Slot, QTimer
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
from client.modules.dashboard.class_view_examiner import ExaminerClassView
from client.modules.dashboard.exam_creation_view import ExamCreationView
from client.modules.dashboard.examiner_exam_monitor_view import ExaminerExamMonitorView
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
        return {"status": r.status_code, "text": r.text}
    except requests.RequestException as exc:
        return {"status": -1, "text": str(exc)}


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
        exam_id = (r.json() or {}).get("exam_id")
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
        return {"ok": True, "exam_id": exam_id}
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def _http_fetch_sessions(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/exams/{exam_id}/sessions", headers=headers, timeout=10)
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


# ─────────────────────────────────────────────────────────────────────────────

class ExaminerDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._token = ""
        self._user_id = ""
        self._full_name = ""
        self._ws: ExaminerWsClient | None = None

        self._stack = QStackedWidget()
        self._home_page = QWidget()
        self._class_page = ExaminerClassView(self._apply_shadow)
        self._exam_creation_page = ExamCreationView(self._apply_shadow)
        self._exam_monitor_page = ExaminerExamMonitorView(self._apply_shadow)
        self._class_rows: list[dict] = []
        self._selected_class: dict = {}
        self._monitor_return_stack: str = "home"

        self._classes = QListWidget()
        self._my_exams = QListWidget()
        self._refresh_my_exams_btn = QPushButton("Refresh my exams")
        self._exam_id_input = QLineEdit()
        self._status = QLabel("Enter exam id and connect.")
        self._sessions = QListWidget()
        self._events = QListWidget()

        # Workers — always stored as instance vars to prevent GC mid-run
        self._classes_worker:    Optional[ApiWorker] = None
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

        self._build()
        self._wire()
        # Single overlay reused for every internal page switch
        self._page_spinner = SpinnerOverlay(parent=self._stack)

    def _switch_page(self, widget: QWidget):
        """Show spinner, switch internal page, hide spinner after first paint."""
        self._page_spinner.show()

        def _do():
            self._stack.setCurrentWidget(widget)
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
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Examiner Dashboard")
        title.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {COLOR_TEXT_HEAD};")
        root.addWidget(title)

        self._build_home_page()
        self._stack.addWidget(self._home_page)
        self._stack.addWidget(self._class_page)
        self._stack.addWidget(self._exam_creation_page)
        self._stack.addWidget(self._exam_monitor_page)
        root.addWidget(self._stack, 1)

    def _build_home_page(self):
        root = QVBoxLayout(self._home_page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        classes_row = QHBoxLayout()
        classes_heading = QLabel("Classes")
        classes_heading.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLOR_TEXT_HEAD};")
        create_class_btn = QPushButton("Create Class")
        create_class_btn.clicked.connect(self._open_create_class_dialog)
        classes_row.addWidget(classes_heading)
        classes_row.addStretch(1)
        classes_row.addWidget(create_class_btn)
        root.addLayout(classes_row)
        self._classes.setMinimumHeight(160)
        root.addWidget(self._classes)

        exams_row = QHBoxLayout()
        exams_heading = QLabel("Your exams (draft / scheduled / live)")
        exams_heading.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLOR_TEXT_HEAD};")
        exams_row.addWidget(exams_heading)
        exams_row.addStretch(1)
        exams_row.addWidget(self._refresh_my_exams_btn)
        root.addLayout(exams_row)
        self._my_exams.setMinimumHeight(120)
        root.addWidget(self._my_exams)

        top = QHBoxLayout()
        self._exam_id_input.setPlaceholderText("Exam ID")
        connect_btn = QPushButton("Connect Live Monitor")
        connect_btn.clicked.connect(self._connect_exam)
        refresh_btn = QPushButton("Refresh Sessions")
        refresh_btn.clicked.connect(self._refresh_sessions)
        pause_btn = QPushButton("Pause Exam")
        pause_btn.clicked.connect(self._pause_exam)
        end_btn = QPushButton("End Exam")
        end_btn.clicked.connect(self._end_exam)
        top.addWidget(self._exam_id_input, 2)
        top.addWidget(connect_btn)
        top.addWidget(refresh_btn)
        top.addWidget(pause_btn)
        top.addWidget(end_btn)
        root.addLayout(top)
        root.addWidget(self._status)

        lists = QHBoxLayout()
        lists.addWidget(self._sessions, 1)
        lists.addWidget(self._events, 2)
        root.addLayout(lists, 1)

        terminate_btn = QPushButton("Terminate Selected Session")
        terminate_btn.clicked.connect(self._terminate_selected_session)
        root.addWidget(terminate_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _wire(self):
        self._classes.itemDoubleClicked.connect(self._open_class)
        self._my_exams.itemDoubleClicked.connect(self._open_monitor_from_my_exams_item)
        self._refresh_my_exams_btn.clicked.connect(self._load_my_exams)
        self._sessions.itemDoubleClicked.connect(self._show_session_details)
        self._class_page.back_requested.connect(self._go_home)
        self._class_page.create_exam_requested.connect(self._create_exam_from_class)
        self._class_page.refresh_exams_requested.connect(self._load_class_exams_for_selected)
        self._class_page.refresh_enrollments_requested.connect(self._load_class_enrollments_for_selected)
        self._class_page.enrollment_approve_requested.connect(self._approve_enrollment)
        self._class_page.enrollment_reject_requested.connect(self._reject_enrollment)
        self._class_page.exam_monitor_requested.connect(self._open_exam_monitor_from_class)
        self._class_page.exam_status_change_requested.connect(self._patch_exam_status)
        self._exam_creation_page.back_requested.connect(
            lambda: self._switch_page(self._class_page)
        )
        self._exam_creation_page.submit_requested.connect(self._submit_exam_with_questions)
        self._exam_monitor_page.back_requested.connect(self._on_exam_monitor_back)

    def set_session(self, token: str, user_id: str, full_name: str):
        self._token = token
        self._user_id = user_id
        self._full_name = full_name
        self._status.setText(f"Signed in as {full_name}.")
        self._refresh_classes()
        # _load_my_exams is always called by _apply_classes (both success and
        # error paths), so do not call it here — calling both in parallel would
        # overwrite self._my_exams_worker while the first run is still alive,
        # causing "QThread: Destroyed while thread is still running".

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
                self._refresh_classes()

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
        self._classes_worker = ApiWorker(_http_fetch_classes, self._headers())
        self._classes_worker.finished.connect(self._apply_classes)
        self._classes_worker.errored.connect(self._on_classes_error)
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
        self._my_exams.clear()
        if not self._token:
            return
        if self._my_exams_worker and self._my_exams_worker.isRunning():
            return
        self._my_exams_worker = ApiWorker(_http_fetch_my_exams, self._headers())
        self._my_exams_worker.finished.connect(self._apply_my_exams)
        self._my_exams_worker.errored.connect(
            lambda e: self._my_exams.addItem("Network error while loading exams.")
        )
        self._my_exams_worker.start()

    @Slot(object)
    def _apply_my_exams(self, result: dict):
        self._my_exams.clear()
        if result["status"] != 200:
            self._my_exams.addItem("Unable to load exams.")
            return
        rows = result["data"] or []
        if not rows:
            self._my_exams.addItem("No exams yet. Create one inside a class.")
            return
        for row in rows:
            item = QListWidgetItem(
                f"{row.get('title', 'Exam')} | {row.get('class_name', 'Class')} | {row.get('status', '')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._my_exams.addItem(item)

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
        self._switch_page(self._home_page)
        self._load_my_exams()

    @Slot(dict)
    def _create_exam_from_class(self, class_payload: dict):
        self._selected_class = dict(class_payload or {})
        self._exam_creation_page.set_class_payload(class_payload)
        self._switch_page(self._exam_creation_page)

    @Slot(dict)
    def _open_exam_monitor_from_class(self, exam_row: dict):
        self._monitor_return_stack = "class"
        self._exam_monitor_page.configure(self._token, exam_row)
        self._switch_page(self._exam_monitor_page)

    @Slot(QListWidgetItem)
    def _open_monitor_from_my_exams_item(self, item: QListWidgetItem):
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        if not row.get("exam_id"):
            return
        self._monitor_return_stack = "home"
        self._exam_monitor_page.configure(self._token, row)
        self._switch_page(self._exam_monitor_page)

    @Slot()
    def _on_exam_monitor_back(self):
        if self._monitor_return_stack == "class":
            self._switch_page(self._class_page)
            self._load_class_exams_for_selected()
        else:
            self._switch_page(self._home_page)
            self._load_my_exams()

    @Slot(str, str)
    def _patch_exam_status(self, exam_id: str, new_status: str):
        if not exam_id or not self._token:
            return
        self._patch_worker = ApiWorker(_http_patch_exam_status, self._headers(), exam_id, new_status)

        def _on_done(result: dict):
            if result["status"] != 200:
                self._status.setText(f"Status update failed: {result['text'][:300]}")
                return
            self._status.setText(f"Exam {exam_id} → {new_status}")
            self._load_class_exams_for_selected()
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
        self._status.setText("Creating exam…")
        self._exam_submit_worker = ApiWorker(
            _http_submit_exam_with_questions, self._headers(), exam_payload, questions
        )

        def _on_done(result: dict):
            if not result.get("ok"):
                self._status.setText(result.get("error", "Unknown error."))
                return
            exam_id = result.get("exam_id", "")
            self._status.setText(
                f"Draft exam created with questions (exam_id={exam_id}). "
                "Use class view to schedule, go live, or open the session monitor."
            )
            self._load_class_exams_for_selected()
            self._load_my_exams()
            self._switch_page(self._class_page)

        self._exam_submit_worker.finished.connect(_on_done)
        self._exam_submit_worker.errored.connect(
            lambda e: self._status.setText("Network error while creating exam/questions.")
        )
        self._exam_submit_worker.start()

    @Slot()
    def _connect_exam(self):
        exam_id = self._exam_id_input.text().strip()
        if not exam_id:
            self._status.setText("Enter exam id first.")
            return
        if self._ws:
            self._ws.stop()
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
