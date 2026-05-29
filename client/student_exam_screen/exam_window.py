"""
client/modules/exam_engine/exam_window.py
Module 3 — Exam Engine Controller (Logic Only)

Pure controller — zero UI code, zero stylesheets, zero layouts.
All UI delegated to:
    ui/exam_ui.py           → question area, timer, navigation
    ui/liveness_overlay.py  → liveness verification overlay
    ui/lockdown_overlay.py  → network lockdown / pause overlay

Three-phase lifecycle:
    Phase 1 — Liveness verification (camera entry process)
    Phase 2 — Active exam (all monitors running)
    Phase 3 — Submitted or terminated (cleanup)

Security features:
    - VM detection on startup
    - Keyboard hooks (C++ DLL) block Alt+Tab, Win, PrintScreen etc.
    - Fullscreen exit detection every 2s + immediate re-entry
    - Screenshot detection via DLL callback
    - Kiosk enforcement (closeEvent blocks, keyPressEvent swallows)
    - Camera liveness at entry, server-side re-verification every 5 min
    - Activity monitoring (window, cursor, clipboard, processes)
    - Network lockdown state machine (120s before termination)
"""

import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Optional
import cv2

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QKeyEvent

from shared.constants import WSMessageType, EventType, EventSeverity, SessionStatus
from client.config import BASE_URL, CAMERA_INDEX, LIVENESS_TIMEOUT_SECONDS
from client.core.contracts import normalize_question_payload, resolve_id
from client.core.heartbeat import HeartbeatManager
from client.core.local_cache import LocalCache
from client.core.input_hooks import InputHooks
from client.modules.proctoring.camera_monitor import CameraMonitor
from client.modules.proctoring.activity_monitor import (
    ActivityMonitor, detect_virtual_machine,
)
from client.modules.proctoring.event_logger import EventLogger, ProctoringEvent
from client.student_exam_screen import StudentExamScreenWidget, FinalizingOverlay
from client.Shared.info_dialog import InfoDialog
from client.modules.exam_engine.ui.liveness_overlay import LivenessOverlay
from client.modules.exam_engine.ui.lockdown_overlay import LockdownOverlay
from client.student_exam_screen.services import StudentExamApiClient

logger = logging.getLogger(__name__)


def _http_activate_session(token: str, base_url: str, session_id: str) -> dict:
    """POST /sessions/{id}/activate — safe to call from any QThread."""
    try:
        resp = requests.post(
            f"{base_url}/sessions/{session_id}/activate",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        return {"status": resp.status_code, "text": resp.text}
    except requests.RequestException as exc:
        return {"status": -1, "text": str(exc)}

def _http_finalize_session(token: str, base_url: str, session_id: str, payload: dict) -> dict:
    resp = requests.post(
        f"{base_url}/sessions/{session_id}/finalize",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if resp.status_code >= 400:
        raise RuntimeError(resp.text[:500])
    return resp.json() or {}

class _EntryVerifyWorker(QThread):
    """
    Runs verify-face POST + activate-session POST off the GUI thread.
    Emits one of:
        verified()             — both calls succeeded
        liveness_failed(str)   — face did not match; show reason in overlay
        activation_failed(str) — session could not be activated; show QMessageBox
    """

    verified          = Signal()
    liveness_failed   = Signal(str)
    activation_failed = Signal(str)

    def __init__(self, api: StudentExamApiClient, session_id: str, session: dict, image_bytes: Optional[bytes],
                 camera_index: int):
        super().__init__()
        self._api = api
        self._session_id   = session_id
        self._session      = dict(session)
        self._image_bytes  = image_bytes
        self._camera_index = camera_index

    def run(self):
        image_bytes = self._image_bytes
        if not image_bytes:
            cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                self.liveness_failed.emit("Unable to access camera for identity verification.")
                return
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                self.liveness_failed.emit("Could not capture face image for identity verification.")
                return
            enc_ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not enc_ok:
                self.liveness_failed.emit("Could not encode face image for identity verification.")
                return
            image_bytes = buffer.tobytes()

        # Step 1 — server-side face match
        try:
            body = self._api.verify_face(image_bytes)
        except Exception as exc:
            logger.exception("Entry face verification request failed")
            self.liveness_failed.emit(f"Face verification network error: {exc}")
            return

        if not body.get("verified"):
            self.liveness_failed.emit(
                "Face verification failed: identity did not match enrolled profile."
            )
            return

        # Step 2 — activate session (skip if already active/locked)
        try:
            self._api.activate_session(self._session_id)
        except Exception as exc:
            self.activation_failed.emit(f"Could not activate the exam session: {exc}")
            return

        self.verified.emit()


class ExamWindow(QMainWindow):
    """
    Exam engine controller — logic only, no UI code.

    Args:
        session:   Session dict from POST /sessions/start
        exam:      Exam dict from GET /exams/{id}
        questions: Question list from GET /exams/{id}/questions
        token:     JWT for API calls and WebSocket auth
    """

    # ── Signals to UI components ───────────────────────────────────────────
    _sig_timer_update    = Signal(str)
    _sig_timer_warning   = Signal(bool)
    _sig_progress        = Signal(int, int)
    _sig_nav_enabled     = Signal(bool, bool, bool)
    _sig_liveness_status = Signal(str)
    _sig_liveness_state  = Signal(str)
    _sig_liveness_preview = Signal(bytes)
    # Marshalled from CameraMonitor's LivenessWatcher thread onto the GUI thread
    # (QTimer.singleShot from a plain Python thread does not reliably run slots on the main loop).
    _sig_run_complete_entry_liveness = Signal()
    _sig_run_liveness_failure = Signal(str)
    _sig_lockdown_show   = Signal()
    _sig_lockdown_paused = Signal()
    _sig_lockdown_hide   = Signal()
    _sig_lockdown_tick   = Signal(int)
    finished             = Signal()

    def __init__(
        self,
        session:   dict,
        exam:      dict,
        questions: list,
        token:     str,
        embedded:  bool = False,
        api: StudentExamApiClient | None = None,
    ):
        super().__init__()
        self.embedded = embedded
        if not self.embedded:
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        else:
            # Prevent this QMainWindow from triggering quitOnLastWindowClosed
            # when it's removed from the host QStackedWidget (which reparents
            # it to null, making it a top-level window whose destruction would
            # otherwise cause QApplication to quit).
            self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.session       = session
        self.exam          = exam
        self.questions     = [normalize_question_payload(q) for q in questions]
        self.token         = token
        self.api = api or StudentExamApiClient(
            base_url=BASE_URL,
            access_token=token,
        )
        self.current_index = 0

        self.session_id = resolve_id(session, "session_id")
        self.exam_id = resolve_id(exam, "exam_id")

        self._in_lockdown     = False
        self._terminated      = False
        self._liveness_passed = False
        self._started         = False
        self._cleaned_up      = False
        self._finish_exit_dispatched = False
        self._entry_verify_image: bytes | None = None
        self._entry_verify_worker: Optional[_EntryVerifyWorker] = None
        self._skip_activate_worker = None  # ApiWorker — set at runtime to avoid circular import
        # Account has face enrolled globally; this flag gates entry liveness + verify-face at start.
        self._require_liveness = bool(exam.get("require_liveness_check", True))

        # ── Local cache ────────────────────────────────────────────────────
        self.cache = LocalCache()
        self.cache.purge_session(self.session_id)
        self.cache.set_meta("session_id", self.session_id)
        self.cache.set_meta("exam_id", self.exam_id)

        # ── Infrastructure ─────────────────────────────────────────────────
        self.heartbeat = HeartbeatManager(
            session_id=self.session_id,
            exam_id=self.exam_id,
            token=token,
            cache=self.cache,
        )

        self.event_logger = EventLogger(
            session_id=self.session_id,
            cache=self.cache,
            send_batch=self.heartbeat.send_event_batch,
        )

        self.camera_monitor = CameraMonitor(
            emit_event=self.event_logger.log,
            token=token,
            on_liveness_pass=self._on_liveness_passed,
            on_liveness_fail=self._on_liveness_failed,
            on_preview_frame=self._on_liveness_preview,
        )

        self.activity_monitor = ActivityMonitor(
            emit_event=self.event_logger.log,
        )

        self.input_hooks: Optional[InputHooks] = None

        # ── UI ─────────────────────────────────────────────────────────────
        self._build_ui()
        self._wire_signals()

        # ── Timers ─────────────────────────────────────────────────────────
        self._exam_end_time: Optional[datetime] = None

        self._save_timer = QTimer()
        self._save_timer.timeout.connect(self._save_current_answer)
        self._save_timer.start(3000)

        self._countdown_timer = QTimer()
        self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start(1000)

        # Fullscreen exit detection — every 2 seconds
        self._fullscreen_timer = QTimer()
        self._fullscreen_timer.timeout.connect(self._check_fullscreen)
        self._fullscreen_timer.start(2000)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("ExamApp")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.exam_ui = StudentExamScreenWidget(
            questions=self.questions,
            exam=self.exam,
            parent=central,
        )
        layout.addWidget(self.exam_ui)
        self.question_widgets = self.exam_ui.question_widgets

        self.liveness_overlay = LivenessOverlay(parent=central)
        self.lockdown_overlay = LockdownOverlay(parent=central)
        self.finalizing_overlay = FinalizingOverlay(parent=central)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.centralWidget().rect()
        for widget in ("exam_ui", "liveness_overlay", "lockdown_overlay", "finalizing_overlay"):
            if hasattr(self, widget):
                getattr(self, widget).setGeometry(rect)
                
    def _wire_signals(self):
        """Connect all signals between controller and UI components."""
        # Controller → StudentExamScreenWidget
        self._sig_timer_update.connect(self.exam_ui.update_timer)
        self._sig_timer_warning.connect(self.exam_ui.set_timer_warning)
        self._sig_progress.connect(self.exam_ui.update_progress)
        self._sig_nav_enabled.connect(self.exam_ui.set_navigation_enabled)

        # StudentExamScreenWidget → Controller
        self.exam_ui.prev_requested.connect(self._go_prev)
        self.exam_ui.next_requested.connect(self._go_next)
        self.exam_ui.submit_requested.connect(self._submit_exam)

        # StudentExamScreenWidget → Proctoring logs
        self.exam_ui.keystroke.connect(self.event_logger.log_keystroke)
        self.exam_ui.paste_attempted.connect(self.event_logger.log_paste_attempt)

        # Controller → LivenessOverlay
        self._sig_liveness_status.connect(self.liveness_overlay.set_status)
        self._sig_liveness_state.connect(self.liveness_overlay.set_state)
        # Preview bytes: Phase 1 → liveness overlay (disconnected after liveness passes).
        # Phase 2 → sidebar (reconnected by _rewire_liveness_preview_signal).
        # Initial connection is to liveness_overlay for proctored exams.
        # For open-book exams _rewire_liveness_preview_signal is called immediately in _on_skip_activated.
        self._sig_liveness_preview.connect(
            self.liveness_overlay.set_preview_frame,
            Qt.ConnectionType.QueuedConnection,
        )
        self._sig_run_complete_entry_liveness.connect(
            self._complete_entry_liveness,
            Qt.ConnectionType.QueuedConnection,
        )
        self._sig_run_liveness_failure.connect(
            self._handle_liveness_failure,
            Qt.ConnectionType.QueuedConnection,
        )

        # Controller → LockdownOverlay
        self._sig_lockdown_show.connect(self.lockdown_overlay.show_lockdown)
        self._sig_lockdown_paused.connect(self.lockdown_overlay.show_paused)
        self._sig_lockdown_hide.connect(self.lockdown_overlay.hide_overlay)
        self._sig_lockdown_tick.connect(self.lockdown_overlay.update_countdown)

        # HeartbeatManager → Controller
        self.heartbeat.connection_lost.connect(self._on_connection_lost)
        self.heartbeat.connection_restored.connect(self._on_connection_restored)
        self.heartbeat.session_terminated.connect(self._on_terminated)
        self.heartbeat.lockdown_tick.connect(self._on_lockdown_tick)
        self.heartbeat.answer_sync_requested.connect(self._sync_answers_now)
        self.heartbeat.examiner_command.connect(self._handle_examiner_command)

    def _rewire_liveness_preview_signal(self) -> None:
        """
        Called once after liveness passes (or immediately for open-book exams).
        Disconnects preview signal from the liveness overlay and reconnects it to
        the sidebar live-feed slot, keeping delivery QueuedConnection so pixmap
        updates always land on the GUI thread.
        """
        try:
            self._sig_liveness_preview.disconnect(self.liveness_overlay.set_preview_frame)
        except (RuntimeError, TypeError):
            pass
        try:
            self._sig_liveness_preview.disconnect(self.exam_ui.set_preview_frame)
        except (RuntimeError, TypeError):
            pass
        self._sig_liveness_preview.connect(
            self.exam_ui.set_preview_frame,
            Qt.ConnectionType.QueuedConnection,
        )

    # ── Window show ────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if self._started:
            return
        self._started = True

        if not self.embedded:
            self.showFullScreen()
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint,
            )

        self._check_vm()

        kiosk_window = self.window() if self.embedded else self
        hwnd = int(kiosk_window.winId())
        self.input_hooks = InputHooks(hwnd, self._on_blocked_key)
        if not self.input_hooks.install():
            logger.warning("Keyboard hooks failed to install")

        self.heartbeat.start()
        self.event_logger.start()
        self.activity_monitor.start()
        self.activity_monitor.set_exam_window(hwnd)

        if self._require_liveness:
            self.heartbeat.send_session_state(SessionStatus.VERIFYING.value)
            # Phase 1 — liveness + face match at entry
            self.liveness_overlay.show()
            self.liveness_overlay.raise_()
            self._sig_liveness_status.emit(
                "Starting camera… When the live picture appears, blink twice "
                "then turn your head clearly to the left or right. "
                f"The camera light usually turns off as soon as this step finishes "
                f"(often well under {LIVENESS_TIMEOUT_SECONDS}s), not only when the time limit is reached. "
                f"If you do not complete the steps, the check ends automatically after about "
                f"{LIVENESS_TIMEOUT_SECONDS}s."
            )
            self._sig_nav_enabled.emit(False, False, False)
            self.camera_monitor.start_entry()
        else:
            self.liveness_overlay.hide()
            self.heartbeat.send_session_state(SessionStatus.ACTIVE.value)
            QTimer.singleShot(0, self._skip_entry_liveness)

    # ── Security checks ────────────────────────────────────────────────────

    def _check_vm(self):
        is_vm, indicators = detect_virtual_machine()
        if is_vm:
            self.event_logger.log(ProctoringEvent(
                event_type=EventType.VM_DETECTED,
                severity=EventSeverity.CRITICAL,
                timestamp=datetime.utcnow(),
                metadata={"indicators": indicators},
            ))

    def _check_fullscreen(self):
        """
        Fullscreen exit detection — fires every 2 seconds.
        Detects and recovers from:
          - Win+D (show desktop) if DLL hook failed
          - Qt losing fullscreen state unexpectedly
          - VM or RDP resizing the window

        Logs FULLSCREEN_EXIT event and immediately re-enters fullscreen.
        """
        if not self._liveness_passed or self._in_lockdown:
            return

        kiosk_window = self.window() if self.embedded else self
        if not kiosk_window.isFullScreen():
            logger.warning("Fullscreen exit detected — recovering")
            self.event_logger.log(ProctoringEvent(
                event_type=EventType.FULLSCREEN_EXIT,
                severity=EventSeverity.HIGH,
                timestamp=datetime.utcnow(),
                metadata={"recovered": True},
            ))
            kiosk_window.showFullScreen()
            kiosk_window.raise_()
            kiosk_window.activateWindow()

    def _on_blocked_key(self, event_type: str, vk_code: int):
        """Map DLL blocked key strings to proctoring events."""
        is_screenshot = event_type == "PRINT_SCREEN"
        self.event_logger.log(ProctoringEvent(
            event_type=(
                EventType.SCREENSHOT_ATTEMPT
                if is_screenshot
                else EventType.WINDOW_SWITCH
            ),
            severity=(
                EventSeverity.HIGH
                if is_screenshot
                else EventSeverity.MEDIUM
            ),
            timestamp=datetime.utcnow(),
            metadata={"blocked_key": event_type, "vk_code": vk_code},
        ))

    # ── Liveness ───────────────────────────────────────────────────────────

    def _on_liveness_passed(self, verify_image: bytes | None = None):
        # Called from CameraMonitor's LivenessWatcher thread — do not touch Qt
        # objects here (disconnect/connect is main-thread only).
        n = len(verify_image) if verify_image else 0
        logger.info(
            "[liveness.ui] passed (verify_image_bytes=%s) — marshalling completion to GUI thread",
            n,
        )
        self._entry_verify_image = verify_image
        self._sig_run_complete_entry_liveness.emit()

    def _on_liveness_failed(self, reason: str):
        # Called from LivenessWatcher thread — only marshal to GUI thread.
        self._sig_run_liveness_failure.emit(reason)

    def _on_liveness_preview(self, image_bytes: bytes):
        self._sig_liveness_preview.emit(image_bytes)

    def _skip_entry_liveness(self):
        """Exam has require_liveness_check=false — no entry overlay; activate session then start."""
        self._sig_liveness_status.emit("Entry liveness disabled for this exam — starting without camera gate.")
        self._sig_liveness_state.emit("skipped")

        status = str(self.session.get("status") or "").lower()
        if status in {SessionStatus.ACTIVE.value, SessionStatus.LOCKED.value}:
            self._on_skip_activated()
            return

        from client.core.api_worker import ApiWorker
        self._skip_activate_worker = ApiWorker(
            self.api.activate_session,
            self.session_id,
        )
        self._skip_activate_worker.finished.connect(self._on_skip_activate_result)
        self._skip_activate_worker.errored.connect(
            lambda e: self._on_activation_failed("Network error while activating the exam session.")
        )
        self._skip_activate_worker.start()

    @Slot(object)
    def _on_skip_activate_result(self, result: dict):
        self.session["status"] = result.get("status", SessionStatus.ACTIVE.value)
        self._on_skip_activated()

    def _on_skip_activated(self):
        self._liveness_passed = True
        self._start_exam_timer_after_activation()
        self.liveness_overlay.hide()
        # Camera monitoring is NOT started for open-book exams (require_liveness_check=False).
        # The same flag that disables liveness also disables continuous monitoring.
        self.exam_ui.set_camera_status("Camera monitoring disabled for this exam.")
        self._sig_nav_enabled.emit(False, len(self.questions) > 1, True)
        self.event_logger.log(ProctoringEvent(
            event_type=EventType.EXAM_STARTED,
            severity=EventSeverity.INFO,
            timestamp=datetime.utcnow(),
            metadata={"session_id": self.session_id, "liveness_gate": "skipped", "monitoring": "disabled"},
        ))

    @Slot()
    def _complete_entry_liveness(self):
        self._rewire_liveness_preview_signal()
        logger.info("[liveness.ui] _complete_entry_liveness running (verify-face + activate)")
        self._sig_liveness_status.emit("✓ Liveness passed. Verifying identity...")
        self._sig_liveness_state.emit("passed")

        if self._entry_verify_worker and self._entry_verify_worker.isRunning():
            logger.warning("[liveness.ui] entry verify already running — ignoring duplicate")
            return

        self._entry_verify_worker = _EntryVerifyWorker(
            api=self.api,
            session_id=self.session_id,
            session=self.session,
            image_bytes=self._entry_verify_image,
            camera_index=CAMERA_INDEX,
        )
        self._entry_verify_worker.verified.connect(self._on_entry_verified)
        self._entry_verify_worker.liveness_failed.connect(self._handle_liveness_failure)
        self._entry_verify_worker.activation_failed.connect(self._on_activation_failed)
        self._entry_verify_worker.start()

    @Slot()
    def _on_entry_verified(self):
        """Called on the main thread when verify-face + activate both succeeded."""
        self.session["status"] = SessionStatus.ACTIVE.value
        self._liveness_passed = True
        self._start_exam_timer_after_activation()
        self.liveness_overlay.hide()
        self.camera_monitor.start_monitoring()
        self.heartbeat.send_session_state(SessionStatus.ACTIVE.value)
        self._sig_nav_enabled.emit(False, len(self.questions) > 1, True)
        self.event_logger.log(ProctoringEvent(
            event_type=EventType.EXAM_STARTED,
            severity=EventSeverity.INFO,
            timestamp=datetime.utcnow(),
            metadata={"session_id": self.session_id},
        ))

    @Slot(str)
    def _on_activation_failed(self, reason: str):
        dlg = InfoDialog(title="Activation Failed", body=reason, parent=self)
        dlg.exec_()
        self._finish_exam()

    @Slot(str)
    def _handle_liveness_failure(self, reason: str):
        self._rewire_liveness_preview_signal()
        logger.warning("[liveness.ui] failure: %s", reason)
        self._sig_liveness_state.emit("failed")
        self._sig_liveness_status.emit(reason)
        self.event_logger.log(ProctoringEvent(
            event_type=EventType.LIVENESS_FAIL,
            severity=EventSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
            metadata={"reason": reason},
        ))
        dlg = InfoDialog(title="Verification Failed", body=reason, parent=self)
        dlg.exec_()
        self._finish_exam()

    # ── Navigation ─────────────────────────────────────────────────────────

    @Slot()
    def _go_prev(self):
        if self._in_lockdown or self.current_index == 0:
            return
        self._save_current_answer()
        self.current_index -= 1
        self._show_question(self.current_index)

    @Slot()
    def _go_next(self):
        if self._in_lockdown or self.current_index >= len(self.questions) - 1:
            return
        self._save_current_answer()
        self.current_index += 1
        self._show_question(self.current_index)

    def _show_question(self, index: int):
        self.exam_ui.set_current_question(index)
        self._sig_progress.emit(index + 1, len(self.questions))
        self._sig_nav_enabled.emit(
            index > 0,
            index < len(self.questions) - 1,
            True,
        )

    # ── Answer persistence ─────────────────────────────────────────────────

    @Slot()
    def _save_current_answer(self):
        if not self._liveness_passed:
            return
        q = self.questions[self.current_index]
        answer = self.exam_ui.get_current_answer()
        q_type = getattr(q.get("question_type"), "value", q.get("question_type"))
        if q_type == "mcq":
            self.cache.save_answer(self.session_id, q["id"], selected_option=answer)
        else:
            self.cache.save_answer(self.session_id, q["id"], answer_text=answer)

    @Slot()
    def _sync_answers_now(self):
        self._save_current_answer()
        answers = self.cache.get_all_answers(self.session_id)
        self.heartbeat.send_answer_sync(answers)
        self._restore_answers_from_cache()

    def _restore_answers_from_cache(self):
        for q in self.questions:
            cached = self.cache.get_answer(q["id"])
            if not cached:
                continue
            q_type = getattr(q.get("question_type"), "value", q.get("question_type"))
            if q_type == "mcq" and cached.get("selected_option"):
                self.exam_ui.restore_answer(q["id"], cached["selected_option"])
            elif cached.get("answer_text"):
                self.exam_ui.restore_answer(q["id"], cached["answer_text"])

    # ── Heartbeat / lockdown ───────────────────────────────────────────────

    @Slot()
    def _on_connection_lost(self):
        self._in_lockdown = True
        self._sig_lockdown_show.emit()
        self._sig_nav_enabled.emit(False, False, False)
        self.camera_monitor.pause()

    @Slot()
    def _on_connection_restored(self):
        self._in_lockdown = False
        self._sig_lockdown_hide.emit()
        self._sig_nav_enabled.emit(
            self.current_index > 0,
            self.current_index < len(self.questions) - 1,
            True,
        )
        self.camera_monitor.resume()

    @Slot(int)
    def _on_lockdown_tick(self, seconds_remaining: int):
        self._sig_lockdown_tick.emit(seconds_remaining)

    @Slot(str)
    def _on_terminated(self, reason: str):
        self._finalize_exam(
            reason="examiner_terminate",
            title="Session terminated",
            message=reason,
        )

    # ── Examiner commands ──────────────────────────────────────────────────

    @Slot(dict)
    def _handle_examiner_command(self, msg: dict):
        msg_type = msg.get("type")
        if msg_type == WSMessageType.EXAM_PAUSE:
            self._in_lockdown = True
            self._sig_lockdown_paused.emit()
            self._sig_nav_enabled.emit(False, False, False)
            self.camera_monitor.pause()
        elif msg_type == WSMessageType.EXAM_END:
            self._finalize_exam(
                reason="examiner_end",
                title="Exam ended by examiner",
                message="The examiner has ended the exam. Your completed answers are being submitted.",
            )
        elif msg_type == WSMessageType.TIME_SYNC:
            end_time_str = msg.get("exam_end_time")
            if end_time_str:
                try:
                    self._exam_end_time = datetime.fromisoformat(end_time_str)
                except ValueError:
                    pass

    # ── Submission ─────────────────────────────────────────────────────────
    @Slot()
    def _submit_exam(self):
        dlg = InfoDialog(
            title="Submit Exam",
            body="Are you sure you want to submit your exam? You cannot make changes after submission.",
            parent=self,
            confirm_label="Submit Exam",
            cancel_label="Keep Working",
        )

        confirmed = {"value": False}
        dlg.confirmed.connect(lambda: confirmed.__setitem__("value", True))
        dlg.exec_()

        if confirmed["value"]:
            self._finalize_exam(
                reason="manual_submit",
                title="Submitting exam",
                message="Please wait while your answers are saved and submitted.",
            )
    def _finalize_exam(self, reason: str, title: str, message: str) -> None:
        if getattr(self, "_finalizing", False):
            return

        self._finalizing = True
        self._save_current_answer()

        answers = self.cache.get_all_answers(self.session_id)
        self.heartbeat.send_answer_sync(answers)

        self._sig_nav_enabled.emit(False, False, False)
        self.exam_ui.set_exam_enabled(False)
        self.finalizing_overlay.show_message(title, message)

        payload = {
            "reason": reason,
            "message": message,
            "client_time": datetime.utcnow().isoformat(),
            "answers": answers,
        }

        from client.core.api_worker import ApiWorker

        self._finalize_worker = ApiWorker(
            self.api.finalize_session,
            self.session_id,
            payload,
        )
        self._finalize_worker.finished.connect(
            lambda result: self._on_finalize_success(reason, result)
        )
        self._finalize_worker.errored.connect(
            lambda error: self._on_finalize_error(reason, title, message, error)
        )
        self._finalize_worker.start()


    @Slot(object)
    def _on_finalize_success(self, reason: str, result: dict) -> None:
        self._finalizing = False

        self.event_logger.log(ProctoringEvent(
            event_type=EventType.EXAM_SUBMITTED,
            severity=EventSeverity.INFO,
            timestamp=datetime.utcnow(),
            metadata={"session_id": self.session_id, "reason": reason},
        ))

        status = str(result.get("status") or "").lower()

        if "terminated" in status or reason in {
            "examiner_terminate",
            "server_terminate",
            "network_timeout",
        }:
            self.heartbeat.send_session_state(SessionStatus.TERMINATED.value)
        else:
            self.heartbeat.send_session_state(SessionStatus.SUBMITTED.value)

        self._terminated = True
        self._finish_exam()


    def _on_finalize_error(self, reason: str, title: str, message: str, error: str) -> None:
        self._finalizing = False

        if reason == "network_timeout":
            self.finalizing_overlay.show_message(
                "Connection timeout",
                (
                    "Session ended due to connection timeout. Please do not close the app "
                    "while we keep trying to sync and submit the answers you completed."
                ),
            )
            QTimer.singleShot(5000, lambda: self._finalize_exam(reason, title, message))
            return

        dlg = InfoDialog(
            title="Submission Warning",
            body=f"Answers are saved locally, but server finalization failed.\n\n{error}",
            parent=self,
        )
        dlg.exec_()
    # ── Countdown ──────────────────────────────────────────────────────────

    def _update_countdown(self):
        if not self._exam_end_time or not self._liveness_passed:
            return
        remaining = (self._exam_end_time - datetime.utcnow()).total_seconds()
        if remaining <= 0:
            self._finalize_exam(
                reason="time_up",
                title="Time is up",
                message="Time is up. Your answers are being submitted automatically.",
            )
            return
        mins, secs = divmod(int(remaining), 60)
        self._sig_timer_update.emit(f"Time remaining: {mins:02d}:{secs:02d}")
        if remaining <= 300:
            self._sig_timer_warning.emit(True)

    def _start_exam_timer_after_activation(self) -> None:
        duration = (
            self.exam.get("duration_minutes")
            or self.session.get("duration_minutes")
            or 0
        )
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            duration = 0

        if duration <= 0:
            logger.warning("No valid duration_minutes found for exam timer")
            self._sig_timer_update.emit("Time remaining: --:--")
            return

        self._exam_end_time = datetime.utcnow() + timedelta(minutes=duration)
        self._update_countdown()

    # ── Kiosk enforcement ──────────────────────────────────────────────────

    def closeEvent(self, event):
        if not self._terminated:
            event.ignore()
        else:
            self._cleanup()
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        # Dev-only emergency escape while preserving kiosk rules in production.
        if os.getenv("DEBUG", "false").lower() == "true" and event.key() == Qt.Key.Key_F12:
            logger.info("DEBUG F12 — emergency exit (_finish_exam)")
            self._finish_exam()
            return
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F4):
            return
        super().keyPressEvent(event)

    # ── Cleanup ────────────────────────────────────────────────────────────

    def _join_background_qthreads(self) -> None:
        """
        Wait for QThread workers to finish before tearing down this window.

        Without this, ``finished.emit()`` leads to ``deleteLater()`` on this
        widget while ``_EntryVerifyWorker`` / ``ApiWorker`` may still be in
        ``run()`` — Python then drops the last ref to the QThread and Qt prints
        "QThread: Destroyed while thread is still running" (common after face
        verification failure when the modal dialog returns into ``_finish_exam``).
        """
        for attr in ("_entry_verify_worker", "_skip_activate_worker", "_finalize_worker"):
            th = getattr(self, attr, None)
            if th is None:
                continue
            try:
                th.disconnect(self)
            except (RuntimeError, TypeError):
                pass
            
            # Always call wait() to ensure the OS thread is fully reaped 
            # even if isRunning() is False, avoiding "Destroyed while thread is still running"
            if th.isRunning():
                if not th.wait(2000):
                    logger.warning("%s did not finish within 2s — forcing terminate", attr)
                    th.terminate()
                    th.wait(1000)
            else:
                th.wait()
                
            th.deleteLater()
            # DO NOT setattr(self, attr, None) here.
            # Dropping the Python reference immediately causes Python to invoke the C++
            # destructor synchronously BEFORE deleteLater has a chance to execute in the event loop!

    def _cleanup(self):
        if self._cleaned_up:
            return
        self._join_background_qthreads()
        self._cleaned_up = True
        self._save_timer.stop()
        self._countdown_timer.stop()
        self._fullscreen_timer.stop()
        if self.input_hooks:
            self.input_hooks.uninstall()
        self.heartbeat.stop()
        self.event_logger.stop()
        self.camera_monitor.stop()
        self.activity_monitor.stop()
        self.cache.close()
        logger.info("ExamWindow cleanup complete")

    def _finish_exam(self):
        """End the exam session and return to the host (embedded: student dashboard)."""
        if self._finish_exit_dispatched:
            return
        self._finish_exit_dispatched = True
        self._terminated = True
        try:
            self._cleanup()
        except Exception:
            logger.exception("Exam cleanup error (still leaving exam)")
        finally:
            if self.embedded:
                self.finished.emit()
            else:
                self.close()
