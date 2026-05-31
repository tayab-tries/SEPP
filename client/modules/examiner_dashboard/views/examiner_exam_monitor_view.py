from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from PySide6.QtCore import Qt, Signal, QTimer, Slot
from client.core.api_worker import ApiWorker
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QMessageBox,
    QStackedWidget,
    QTextEdit,
    QDoubleSpinBox,
)

from client.config import BASE_URL
from client.core.examiner_ws import ExaminerWsClient
from client.core.contracts import normalize_question_list
from client.modules.exam_engine.essay_widget import EssayWidget
from client.modules.exam_engine.mcq_widget import MCQWidget
from client.modules.common.design_tokens import severity_color

logger = logging.getLogger(__name__)

_HIGH_SEV = frozenset({"high", "critical"})


# ── HTTP helpers (module-level, safe for ApiWorker threads) ──────────────────

def _http_poll_sessions(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/exams/{exam_id}/sessions",
            headers=headers,
            timeout=10,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_load_questions(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/exams/{exam_id}/questions",
            headers=headers,
            timeout=10,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_load_events(headers: dict, session_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/sessions/{session_id}/proctoring-events",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_load_answers(headers: dict, session_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/sessions/{session_id}/answers",
            headers=headers,
            timeout=12,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_save_review(headers: dict, sid: str, qid: str, score: float, comment: str) -> dict:
    try:
        r = requests.patch(
            f"{BASE_URL}/sessions/{sid}/answers/{qid}/review",
            headers=headers,
            json={"examiner_score": score, "examiner_comment": comment or None},
            timeout=10,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_terminate_session_monitor(headers: dict, session_id: str, reason: str) -> None:
    try:
        requests.post(
            f"{BASE_URL}/sessions/{session_id}/terminate",
            headers=headers,
            json={"reason": reason},
            timeout=10,
        )
    except requests.RequestException:
        pass


# ─────────────────────────────────────────────────────────────────────────────


def _sev_key(s: object) -> str:
    return str(s or "").strip().lower()


class ExaminerExamMonitorView(QWidget):
    """Separate routed view: sessions + proctoring events for one exam."""

    back_requested = Signal()

    def __init__(self, apply_shadow, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._apply_shadow = apply_shadow
        self._token = ""
        self._exam_id = ""
        self._exam_title = ""
        self._ws: ExaminerWsClient | None = None

        self._title = QLabel("Exam monitor")
        self._subtitle = QLabel("")
        self._alerts = QListWidget()
        self._sessions = QListWidget()
        self._events = QListWidget()
        self._answers = QListWidget()
        self._answer_stack = QStackedWidget()
        self._score_input = QDoubleSpinBox()
        self._comment_input = QTextEdit()
        self._save_review_btn = QPushButton("Save review")
        self._refresh_btn = QPushButton("Refresh now")
        self._terminate_btn = QPushButton("Terminate selected session")
        self._pause_btn = QPushButton("Pause exam (WS)")
        self._end_btn = QPushButton("End exam (WS)")
        self._status = QLabel("")
        self._questions: list[dict] = []
        self._answer_rows_by_question: dict[str, dict] = {}
        self._review_allowed = False

        # Workers — stored as instance vars to prevent GC mid-run
        self._poll_worker:      Optional[ApiWorker] = None
        self._questions_worker: Optional[ApiWorker] = None
        self._events_worker:    Optional[ApiWorker] = None
        self._answers_worker:   Optional[ApiWorker] = None
        self._review_worker:    Optional[ApiWorker] = None
        self._terminate_worker: Optional[ApiWorker] = None

        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_rest)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("Back")
        back.clicked.connect(self._on_back)
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(self._refresh_btn)
        root.addLayout(top)

        self._title.setObjectName("sectionHeading")
        root.addWidget(self._title)
        root.addWidget(self._subtitle)

        alerts_card = QFrame()
        alerts_card.setObjectName("mainCard")
        self._apply_shadow(alerts_card)
        ac = QVBoxLayout(alerts_card)
        ac.setContentsMargins(14, 14, 14, 14)
        ac.addWidget(QLabel("High / critical alerts (live WS + newest first)"))
        ac.addWidget(self._alerts, 1)

        body = QHBoxLayout()
        body.setSpacing(12)

        sess_card = QFrame()
        sess_card.setObjectName("mainCard")
        self._apply_shadow(sess_card)
        sc = QVBoxLayout(sess_card)
        sc.setContentsMargins(14, 14, 14, 14)
        sc.addWidget(QLabel("Sessions"))
        sc.addWidget(self._sessions, 1)
        ctrl = QHBoxLayout()
        ctrl.addWidget(self._terminate_btn)
        ctrl.addWidget(self._pause_btn)
        ctrl.addWidget(self._end_btn)
        sc.addLayout(ctrl)

        ev_card = QFrame()
        ev_card.setObjectName("mainCard")
        self._apply_shadow(ev_card)
        ec = QVBoxLayout(ev_card)
        ec.setContentsMargins(14, 14, 14, 14)
        ec.addWidget(QLabel("Proctoring events (selected session)"))
        ec.addWidget(self._events, 1)

        review_card = QFrame()
        review_card.setObjectName("mainCard")
        self._apply_shadow(review_card)
        rc = QVBoxLayout(review_card)
        rc.setContentsMargins(14, 14, 14, 14)
        rc.addWidget(QLabel("Student answers / grading review (available after session is done)"))
        review_body = QHBoxLayout()
        review_body.addWidget(self._answers, 1)
        review_body.addWidget(self._answer_stack, 2)
        rc.addLayout(review_body, 2)
        score_row = QHBoxLayout()
        self._score_input.setRange(0, 1000)
        self._score_input.setSingleStep(0.5)
        score_row.addWidget(QLabel("Score"))
        score_row.addWidget(self._score_input)
        score_row.addStretch(1)
        rc.addLayout(score_row)
        self._comment_input.setPlaceholderText("Examiner comment for this answer")
        self._comment_input.setFixedHeight(80)
        rc.addWidget(self._comment_input)
        rc.addWidget(self._save_review_btn)

        body.addWidget(sess_card, 1)
        body.addWidget(ev_card, 2)
        root.addWidget(alerts_card, 2)
        root.addLayout(body, 2)
        root.addWidget(review_card, 2)
        root.addWidget(self._status)

        self._refresh_btn.clicked.connect(self._poll_rest)
        self._sessions.currentItemChanged.connect(self._load_selection_details)
        self._answers.currentRowChanged.connect(self._answer_stack.setCurrentIndex)
        self._answers.currentItemChanged.connect(self._load_review_form)
        self._save_review_btn.clicked.connect(self._save_answer_review)
        self._terminate_btn.clicked.connect(self._terminate_selected)
        self._pause_btn.clicked.connect(self._pause_ws)
        self._end_btn.clicked.connect(self._end_ws)

    def configure(self, token: str, exam_row: dict):
        self._stop_ws()
        self._token = token
        self._exam_id = str(exam_row.get("exam_id") or "")
        self._exam_title = str(exam_row.get("title") or "Exam")
        self._title.setText(self._exam_title)
        self._subtitle.setText(f"Exam ID: {self._exam_id}")
        self._alerts.clear()
        self._sessions.clear()
        self._events.clear()
        self._answers.clear()
        self._clear_answer_stack()
        self._questions = []
        self._answer_rows_by_question = {}
        self._review_allowed = False
        self._set_review_enabled(False)
        self._status.setText("")
        self._load_questions()
        self._start_ws()
        self._timer.start(8000)
        self._poll_rest()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _on_back(self):
        self._timer.stop()
        self._stop_ws()
        self.back_requested.emit()

    def _start_ws(self):
        if not self._exam_id or not self._token:
            return
        self._ws = ExaminerWsClient(exam_id=self._exam_id, token=self._token)
        self._ws.event_received.connect(self._on_ws_payload)
        self._ws.error.connect(lambda m: self._status.setText(m))
        self._ws.start()

    def _stop_ws(self):
        if self._ws:
            try:
                self._ws.stop()
            except Exception:
                logger.exception("Stopping examiner WS")
            self._ws = None

    @Slot(dict)
    def _on_ws_payload(self, payload: dict):
        sev = _sev_key(payload.get("severity"))
        if sev in _HIGH_SEV or payload.get("type") == "student_flag":
            item = QListWidgetItem(json.dumps(payload, default=str)[:500])
            item.setForeground(QColor(severity_color(sev or "info")))
            self._alerts.insertItem(0, item)
            if self._alerts.count() > 200:
                self._alerts.takeItem(self._alerts.count() - 1)

    @Slot()
    def _pause_ws(self):
        if self._ws:
            self._ws.pause_exam()

    @Slot()
    def _end_ws(self):
        if self._ws:
            self._ws.end_exam()

    @Slot()
    def _poll_rest(self):
        if not self._exam_id or not self._token:
            return
        if self._poll_worker and self._poll_worker.isRunning():
            return  # skip if previous poll still in flight
        self._poll_worker = ApiWorker(_http_poll_sessions, self._headers(), self._exam_id)
        self._poll_worker.finished.connect(self._apply_poll_result)
        self._poll_worker.errored.connect(
            lambda e: self._status.setText(f"Network error: {e}")
        )
        self._poll_worker.start()

    @Slot(object)
    def _apply_poll_result(self, result: dict):
        if result["status"] != 200:
            self._status.setText(f"Sessions: {result['data']!s:.200}")
            return
        rows = result["data"] or []
        current_sid = None
        cur = self._sessions.currentItem()
        if cur:
            d = cur.data(Qt.ItemDataRole.UserRole)
            if isinstance(d, dict):
                current_sid = d.get("session_id")

        self._sessions.blockSignals(True)
        self._sessions.clear()
        for row in rows:
            from client.core.contracts import resolve_student_name
            sid = row.get("session_id", "")
            student_disp = resolve_student_name(row)
            student_disp_short = student_disp[:12] + "…" if len(student_disp) > 12 else student_disp
            sid_short = str(sid)[:10] + "…" if len(str(sid)) > 10 else str(sid)
            integrity = row.get("integrity_score")
            integrity_text = f"{float(integrity):.0f}" if integrity is not None else "N/A"
            recommendation = str(row.get("integrity_recommendation") or "not_calculated")
            gaze_count = int(row.get("gaze_away_count") or 0)
            label = (
                f"{sid_short} | {row.get('status')} | student {student_disp_short} | "
                f"integrity {integrity_text} ({recommendation}) | gaze {gaze_count}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._sessions.addItem(item)
            if current_sid and str(sid) == str(current_sid):
                self._sessions.setCurrentItem(item)
        self._sessions.blockSignals(False)
        if self._sessions.currentRow() < 0 and self._sessions.count():
            self._sessions.setCurrentRow(0)
        self._load_selection_details()
        self._status.setText(f"Loaded {len(rows)} session(s).")

    def _load_selection_details(self, *_args):
        self._load_events_for_selection()
        self._load_answers_for_selection()

    def _load_questions(self):
        if not self._exam_id or not self._token:
            return
        if self._questions_worker and self._questions_worker.isRunning():
            return
        self._questions_worker = ApiWorker(_http_load_questions, self._headers(), self._exam_id)

        def _on_done(result: dict):
            if result["status"] != 200:
                self._status.setText(f"Questions: {result['data']!s:.200}")
                self._questions = []
                return
            self._questions = normalize_question_list(result["data"] or [])

        self._questions_worker.finished.connect(_on_done)
        self._questions_worker.errored.connect(
            lambda e: setattr(self, "_questions", []) or self._status.setText(f"Question load error: {e}")
        )
        self._questions_worker.start()

    @Slot()
    def _load_events_for_selection(self):
        self._events.clear()
        item = self._sessions.currentItem()
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        sid = row.get("session_id")
        if not sid:
            return
        if self._events_worker and self._events_worker.isRunning():
            return
        self._events_worker = ApiWorker(_http_load_events, self._headers(), sid)
        self._events_worker.finished.connect(self._apply_events)
        self._events_worker.errored.connect(
            lambda e: self._events.addItem(f"Network error: {e}")
        )
        self._events_worker.start()

    @Slot(object)
    def _apply_events(self, result: dict):
        self._events.clear()
        if result["status"] != 200:
            self._events.addItem(f"Events error: {result['data']!s:.300}")
            return
        events = result["data"] or []
        severe = [e for e in events if _sev_key(e.get("severity")) in _HIGH_SEV]
        rest   = [e for e in events if _sev_key(e.get("severity")) not in _HIGH_SEV]
        severe.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
        rest.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
        for ev in severe + rest:
            sev  = _sev_key(ev.get("severity"))
            meta = ev.get("metadata")
            meta_s = json.dumps(meta, default=str)[:200] if meta is not None else ""
            line = f"[{sev}] {ev.get('event_type')} @ {ev.get('timestamp')}"
            w = QListWidgetItem(f"{line}  {meta_s}")
            w.setData(Qt.ItemDataRole.UserRole, ev)
            w.setForeground(QColor(severity_color(sev or "info")))
            self._events.addItem(w)

    @Slot()
    def _load_answers_for_selection(self):
        self._answers.clear()
        self._clear_answer_stack()
        self._answer_rows_by_question = {}
        self._review_allowed = False
        self._set_review_enabled(False)
        item = self._sessions.currentItem()
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        sid = row.get("session_id")
        if not sid:
            return
        session_status = str(row.get("status") or "").strip().lower()
        self._review_allowed = session_status in {"submitted", "terminated"}
        if not self._review_allowed:
            self._answers.addItem("Answer review unlocks after the session is submitted or terminated.")
            return
        if self._answers_worker and self._answers_worker.isRunning():
            return
        self._answers_worker = ApiWorker(_http_load_answers, self._headers(), sid)
        self._answers_worker.finished.connect(self._apply_answers)
        self._answers_worker.errored.connect(
            lambda e: self._answers.addItem(f"Network error: {e}")
        )
        self._answers_worker.start()

    @Slot(object)
    def _apply_answers(self, result: dict):
        if result["status"] != 200:
            self._answers.addItem(f"Answers error: {result['data']!s:.300}")
            return
        answers = result["data"] or []
        self._answer_rows_by_question = {
            str(a.get("question_id")): dict(a) for a in answers if a.get("question_id")
        }
        for idx, question in enumerate(self._questions, start=1):
            qid    = str(question.get("question_id") or question.get("id") or "")
            q_type = str(question.get("question_type", "unknown"))
            prompt = str(question.get("text", "Question"))[:50]
            list_item = QListWidgetItem(f"{idx}. [{q_type}] {prompt}")
            list_item.setData(Qt.ItemDataRole.UserRole, question)
            self._answers.addItem(list_item)

            answer_row = self._answer_rows_by_question.get(qid) or {}
            if q_type == "mcq":
                widget = MCQWidget(question, mode="review", readonly=True)
                widget.restore_answer(str(answer_row.get("selected_option") or ""))
            else:
                widget = EssayWidget(question, mode="review", readonly=True)
                widget.restore_answer(str(answer_row.get("answer_text") or ""))
            self._answer_stack.addWidget(widget)
        if self._answers.count():
            self._answers.setCurrentRow(0)
            self._set_review_enabled(True)
        else:
            self._comment_input.clear()
            self._score_input.setValue(0)

    def _load_review_form(self, *_args):
        item = self._answers.currentItem()
        if item is None:
            self._comment_input.clear()
            self._score_input.setValue(0)
            return
        question = item.data(Qt.ItemDataRole.UserRole) or {}
        qid = str(question.get("question_id") or question.get("id") or "")
        answer_row = self._answer_rows_by_question.get(qid) or {}
        self._score_input.setValue(float(answer_row.get("examiner_score") or 0))
        self._comment_input.setPlainText(str(answer_row.get("examiner_comment") or ""))

    @Slot()
    def _save_answer_review(self):
        session_item = self._sessions.currentItem()
        answer_item  = self._answers.currentItem()
        if not self._review_allowed:
            QMessageBox.information(
                self,
                "Review locked",
                "Answers can be graded only after the session is submitted or terminated.",
            )
            return
        if session_item is None or answer_item is None:
            QMessageBox.warning(self, "Review", "Select a session and answer first.")
            return
        session_row = session_item.data(Qt.ItemDataRole.UserRole) or {}
        question    = answer_item.data(Qt.ItemDataRole.UserRole) or {}
        sid = str(session_row.get("session_id") or "")
        qid = str(question.get("question_id") or question.get("id") or "")
        if not sid or not qid:
            return
        score   = float(self._score_input.value())
        comment = self._comment_input.toPlainText().strip()
        if self._review_worker and self._review_worker.isRunning():
            return
        self._save_review_btn.setEnabled(False)
        self._review_worker = ApiWorker(_http_save_review, self._headers(), sid, qid, score, comment)

        def _on_done(result: dict):
            self._save_review_btn.setEnabled(True)
            if result["status"] != 200:
                self._status.setText(f"Review save failed: {result['data']!s:.300}")
                return
            self._answer_rows_by_question[qid] = result["data"] or {}
            self._status.setText("Answer review saved.")

        self._review_worker.finished.connect(_on_done)
        self._review_worker.errored.connect(
            lambda e: (
                self._save_review_btn.setEnabled(True),
                self._status.setText(f"Review save network error: {e}"),
            )
        )
        self._review_worker.start()

    def _clear_answer_stack(self):
        while self._answer_stack.count():
            widget = self._answer_stack.widget(0)
            self._answer_stack.removeWidget(widget)
            widget.deleteLater()

    def _set_review_enabled(self, enabled: bool):
        self._answer_stack.setEnabled(enabled)
        self._score_input.setEnabled(enabled)
        self._comment_input.setEnabled(enabled)
        self._save_review_btn.setEnabled(enabled)

    @Slot()
    def _terminate_selected(self):
        item = self._sessions.currentItem()
        if item is None:
            QMessageBox.warning(self, "Terminate", "Select a session first.")
            return
        row = item.data(Qt.ItemDataRole.UserRole) or {}
        sid = str(row.get("session_id", ""))
        if not sid:
            return
        ok = QMessageBox.question(
            self,
            "Terminate session",
            "Terminate this student session? Use for unrecognized or policy-violating attempts.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        reason = "Session terminated by examiner (monitor)"
        if self._ws:
            self._ws.terminate_session(sid, reason=reason)
        if self._terminate_worker and self._terminate_worker.isRunning():
            return
        self._terminate_worker = ApiWorker(
            _http_terminate_session_monitor, self._headers(), sid, reason
        )
        self._terminate_worker.finished.connect(lambda _: self._poll_rest())
        self._terminate_worker.errored.connect(lambda e: self._poll_rest())
        self._terminate_worker.start()

    def closeEvent(self, event):
        self._timer.stop()
        self._stop_ws()
        super().closeEvent(event)
