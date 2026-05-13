"""
client/modules/proctoring/camera_monitor.py
Module 4b — Camera Monitor (Multiprocessing Architecture)

Two-phase design using separate OS processes:

  Phase 1 — EntryProcess
    - Captures at configured resolution; runs FaceMesh on 320x240 (same as Phase 2)
    - Liveness check: blink detection (EAR) + head movement challenge
    - On pass: puts LIVENESS_PASS into liveness_queue → exits
    - On fail: puts LIVENESS_FAIL reason → exits
    - OS reclaims ALL ~152MB immediately on exit (guaranteed)

  Phase 2 — MonitoringProcess
    - Starts only after EntryProcess exits cleanly
    - Runs FaceMesh at 320x240 (4x fewer pixels)
    - Face absent / multiple faces / head pose / gaze
    - Periodic re-verification via server API every 5 minutes
    - Puts ProctoringEvent dicts into event_queue
    - Reads stop_event to know when to exit cleanly

  MainProcess (CameraMonitor class)
    - Owns all queues and events
    - Reads liveness_queue to know when to start monitoring
    - Runs QueueReaderThread to drain event_queue into EventLogger
    - Handles all process lifecycle (start, stop, force-kill on hang)

Stability mitigations applied:
  S1. All processes are daemon=True — auto-killed if main process dies
  S2. Camera released in finally block — no resource leak on crash
  S3. Sequential camera access — entry releases before monitoring opens
  S4. process.join(timeout) + terminate() fallback — no hang on stop
  S5. Unlimited event_queue (maxsize=0) — producer never blocks
  S6. Module-level process targets — Windows picklable, no bound methods
  S7. Queue reader uses get(timeout=0.5) — checks stop flag regularly

Security mitigations applied:
  E1. Event type validation on queue read — rejects unknown event types
  E2. Malformed event fields caught and discarded
  E3. liveness_queue maxsize=1 — cannot be flooded
  E4. Token passed inside config dict via queue arg — not a CLI arg

Optimizations applied:
  3.  Resolution scaling — analysis at 320x240
  4.  Adaptive FPS — 10fps active, 2fps idle
  7.  Lazy model loading — monitoring loads after entry exits
  8.  Single FaceMesh instance covers head pose + iris (refine_landmarks)
  9.  Explicit frame del after each tick
  10. JPEG compression for snapshots (85%) and uploads (80%)
  12. pause()/resume() — stops processing during exam pause
"""

import gc
import logging
import multiprocessing
import multiprocessing.synchronize
import os
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime
from queue import Empty
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _liveness_entry_emit(msg: str) -> None:
    """
    Log from the CameraEntry child process. Also prints to stderr so lines show
    in the parent terminal even when the child does not inherit logging handlers.
    """
    line = f"[liveness.entry pid={os.getpid()}] {msg}"
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass
    logger.info("%s", line)

# ── Queue message type constants ───────────────────────────────────────────
MSG_LIVENESS_PASS    = "LIVENESS_PASS"
MSG_LIVENESS_FAIL    = "LIVENESS_FAIL"
MSG_PROCTORING_EVENT = "PROCTORING_EVENT"
MSG_PREVIEW_FRAME    = "PREVIEW_FRAME"

# ── Liveness config ────────────────────────────────────────────────────────
EAR_BLINK_THRESHOLD   = 0.25
BLINKS_REQUIRED       = 2
HEAD_TURN_THRESHOLD = 12.0

# ── Resolution (optimization 3) ───────────────────────────────────────────
ANALYSIS_WIDTH  = 320
ANALYSIS_HEIGHT = 240

# ── Adaptive FPS (optimization 4) ─────────────────────────────────────────
FPS_ACTIVE = 0.10    # 10 fps
FPS_IDLE   = 0.50    # 2 fps
IDLE_SECS  = 30

# ── JPEG quality (optimization 10) ────────────────────────────────────────
SNAPSHOT_QUALITY = 85
RECHECK_QUALITY  = 80
PREVIEW_QUALITY  = 60
PREVIEW_INTERVAL_SECS = 0.2
# Cap how often preview bytes hit the Qt thread (queued signals can backlog the GUI).
PREVIEW_UI_MIN_INTERVAL_SECS = 0.12

# ── MediaPipe landmark indices ─────────────────────────────────────────────
LM_NOSE_TIP        = 4
LM_LEFT_EYE_OUTER  = 33
LM_RIGHT_EYE_OUTER = 263
LM_CHIN            = 152
LM_LEFT_EYE        = [362, 385, 387, 263, 373, 380]
LM_RIGHT_EYE       = [33,  160, 158, 133, 153, 144]

# ── Valid event types — security allowlist (mitigation E1) ────────────────
VALID_EVENT_TYPES = {
    "face_absent",
    "multiple_faces",
    "face_mismatch",
    "gaze_away",
    "liveness_fail",
}


# ══════════════════════════════════════════════════════════════════════════════
# Helper functions — module level for Windows pickling (mitigation S6)
# ══════════════════════════════════════════════════════════════════════════════

def _calc_ear(landmarks, h: int, w: int) -> float:
    """Eye Aspect Ratio. Below EAR_BLINK_THRESHOLD = eye closed."""
    import numpy as np

    def pt(idx):
        p = landmarks.landmark[idx]
        return np.array([p.x * w, p.y * h])

    def eye_ear(indices):
        p = [pt(i) for i in indices]
        v1 = float(((p[1] - p[5]) ** 2).sum() ** 0.5)
        v2 = float(((p[2] - p[4]) ** 2).sum() ** 0.5)
        hd = float(((p[0] - p[3]) ** 2).sum() ** 0.5)
        return (v1 + v2) / (2.0 * hd) if hd > 1e-6 else 1.0

    return (eye_ear(LM_LEFT_EYE) + eye_ear(LM_RIGHT_EYE)) / 2.0


def _calc_head_pose(landmarks, h: int, w: int) -> tuple:
    """Returns (yaw_degrees, pitch_degrees) from 4 key landmarks."""
    import numpy as np

    def pt(idx):
        p = landmarks.landmark[idx]
        return np.array([p.x * w, p.y * h])

    nose      = pt(LM_NOSE_TIP)
    left_eye  = pt(LM_LEFT_EYE_OUTER)
    right_eye = pt(LM_RIGHT_EYE_OUTER)
    chin      = pt(LM_CHIN)

    eye_mid     = (left_eye + right_eye) / 2.0
    eye_width   = float(((right_eye - left_eye) ** 2).sum() ** 0.5)
    face_height = float(((chin - eye_mid) ** 2).sum() ** 0.5)

    if eye_width < 1e-6 or face_height < 1e-6:
        return 0.0, 0.0

    yaw   = float((nose[0] - eye_mid[0]) / eye_width * 90)
    pitch = float((nose[1] - eye_mid[1]) / face_height * 60 - 15)
    return yaw, pitch


def _save_snapshot(frame, snapshot_dir: str) -> Optional[str]:
    """Save compressed JPEG. Returns path or None on failure."""
    import cv2
    try:
        filename = (
            f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            f"_{uuid.uuid4().hex[:6]}.jpg"
        )
        path = os.path.join(snapshot_dir, filename)
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_QUALITY])
        return path
    except Exception:
        return None


def _put_event(queue: multiprocessing.Queue, event: dict):
    """
    Non-blocking put. Discards if queue is unavailable.
    Never blocks the monitoring process. (mitigation S5)
    """
    try:
        queue.put_nowait(event)
    except Exception:
        pass


def _open_camera_capture(index: int):
    """
    OpenCV VideoCapture with OS-friendly defaults.
    On Windows, try CAP_DSHOW first (lower latency); fall back to default API.
    """
    import cv2

    if sys.platform == "win32":
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(index)
    else:
        cap = cv2.VideoCapture(index)
    return cap


def _configure_capture_latency(cap) -> None:
    """Reduce internal frame buffering where the backend supports it."""
    import cv2

    if not cap.isOpened():
        return
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass


def _put_preview_frame(queue: multiprocessing.Queue, frame):
    """Best-effort compressed frame preview for the liveness overlay."""
    import cv2
    try:
        small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
        ok, buffer = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_QUALITY])
        if not ok:
            return
        if queue.qsize() > 1:
            return
        queue.put_nowait({
            "type": MSG_PREVIEW_FRAME,
            "image": bytes(buffer),
        })
    except Exception:
        pass


def _recheck_identity(
    frame,
    base_url: str,
    token: str,
    event_queue: multiprocessing.Queue,
    snapshot_dir: str,
    now: datetime,
):
    """
    In-memory JPEG encode + upload to server for GPU re-verification.
    No temp file written. (optimization 10)
    Network errors are silently ignored — do NOT flag as mismatch.
    """
    import cv2
    import requests
    from shared.constants import EventType, EventSeverity

    try:
        success, buffer = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, RECHECK_QUALITY],
        )
        if not success:
            return

        resp = requests.post(
            f"{base_url}/auth/verify-face",
            files={"image": ("recheck.jpg", buffer.tobytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )

        if resp.status_code == 200:
            result = resp.json()
            if not result.get("verified", False):
                snap = _save_snapshot(frame, snapshot_dir)
                _put_event(event_queue, {
                    "type":          MSG_PROCTORING_EVENT,
                    "event_type":    EventType.FACE_MISMATCH.value,
                    "severity":      EventSeverity.CRITICAL.value,
                    "timestamp":     now.isoformat(),
                    "metadata": {
                        "similarity": result.get("similarity", 0),
                        "distance":   result.get("distance", 1),
                        "source":     "periodic_recheck",
                    },
                    "snapshot_path": snap,
                })
    except requests.RequestException:
        pass  # Network error — never treat as mismatch
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Process target functions — module level (mitigation S6)
# ══════════════════════════════════════════════════════════════════════════════

def _entry_process_target(
    liveness_queue: multiprocessing.Queue,
    preview_queue: multiprocessing.Queue,
    config: dict,
):
    """
    Phase 1 OS process.
    Captures at configured resolution; runs FaceMesh on downscaled frames (same
    as monitoring) so preview and liveness stay responsive. Verification JPEG
    uses the full-resolution frame on pass.
    Puts result into liveness_queue and exits.
    OS reclaims all memory on exit — guaranteed.
    """
    try:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            force=True,
        )
    except TypeError:
        logging.basicConfig(level=logging.INFO)

    import cv2

    cap = None
    face_mesh = None
    liveness_passed = False
    verify_image = None
    liveness_timeout = max(10, int(config.get("liveness_timeout_secs", 45)))
    blink_count = 0
    head_turned = False

    _liveness_entry_emit(
        f"start camera_index={config.get('camera_index')} "
        f"liveness_timeout_secs={liveness_timeout} "
        f"requested_size={config.get('camera_width')}x{config.get('camera_height')}"
    )

    try:
        import mediapipe as mp

        cap = _open_camera_capture(config["camera_index"])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config["camera_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config["camera_height"])
        _configure_capture_latency(cap)

        if not cap.isOpened():
            _liveness_entry_emit("FAIL camera not opened after VideoCapture + set props")
            try:
                liveness_queue.put(
                    {
                        "type":   MSG_LIVENESS_FAIL,
                        "reason": "Camera could not be opened for liveness check.",
                    },
                    timeout=5,
                )
            except Exception as qe:
                _liveness_entry_emit(f"FAIL could not enqueue open-failure message: {qe}")
            return

        try:
            backend = cap.getBackendName()
        except Exception:
            backend = "unknown"
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        _liveness_entry_emit(
            f"camera opened backend={backend} actual_frame_size={aw}x{ah}"
        )

        _liveness_entry_emit("creating FaceMesh…")
        face_mesh = mp.solutions.face_mesh.FaceMesh( #type: ignore[attr-defined]
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5,
        )
        _liveness_entry_emit("FaceMesh ready — entering capture loop")

        blink_count     = 0
        eye_was_open    = True
        head_turned     = False
        baseline_yaw    = None
        start_time      = time.time()
        last_preview    = 0.0
        last_diag       = start_time
        read_fail_streak = 0
        frames_with_face = 0

        while True:
            now = time.time()
            if now - start_time > liveness_timeout:
                _liveness_entry_emit(
                    f"loop break: wall-clock timeout ({liveness_timeout}s) "
                    f"blinks={blink_count}/{BLINKS_REQUIRED} head_turn={head_turned}"
                )
                break

            if now - last_diag >= 2.0:
                last_diag = now
                _liveness_entry_emit(
                    f"tick elapsed={now - start_time:.1f}s blinks={blink_count}/{BLINKS_REQUIRED} "
                    f"head_turn={head_turned} read_fail_streak={read_fail_streak} "
                    f"frames_with_face={frames_with_face}"
                )

            ret, frame = cap.read()
            if not ret:
                read_fail_streak += 1
                if read_fail_streak in (1, 5, 10, 25):
                    _liveness_entry_emit(f"cap.read() failed (streak={read_fail_streak})")
                time.sleep(0.1)
                continue
            read_fail_streak = 0

            if time.time() - last_preview >= PREVIEW_INTERVAL_SECS:
                _put_preview_frame(preview_queue, frame)
                last_preview = time.time()

            small = cv2.resize(
                frame,
                (ANALYSIS_WIDTH, ANALYSIS_HEIGHT),
                interpolation=cv2.INTER_LINEAR,
            )
            rgb    = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            result = face_mesh.process(rgb)

            if not result.multi_face_landmarks:
                del frame, rgb, small
                time.sleep(0.05)
                continue

            frames_with_face += 1
            landmarks = result.multi_face_landmarks[0]
            h, w      = small.shape[:2]

            # Blink detection (EAR)
            ear = _calc_ear(landmarks, h, w)
            if eye_was_open and ear < EAR_BLINK_THRESHOLD:
                eye_was_open = False
            elif not eye_was_open and ear >= EAR_BLINK_THRESHOLD:
                blink_count += 1
                eye_was_open = True
                _liveness_entry_emit(f"blink detected count={blink_count} ear={ear:.3f}")

            # Head turn detection
            yaw, _ = _calc_head_pose(landmarks, h, w)
            if baseline_yaw is None:
                baseline_yaw = yaw
                _liveness_entry_emit(f"baseline_yaw set to {yaw:.2f}°")
            elif abs(yaw - baseline_yaw) > HEAD_TURN_THRESHOLD:
                if not head_turned:
                    _liveness_entry_emit(
                        f"head turn detected yaw={yaw:.2f}° delta={abs(yaw - baseline_yaw):.2f}°"
                    )
                head_turned = True

            if blink_count >= BLINKS_REQUIRED and head_turned:
                ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, RECHECK_QUALITY])
                if ok:
                    verify_image = bytes(buffer)
                liveness_passed = True
                _liveness_entry_emit(
                    f"PASS local liveness ok={ok} jpeg_bytes={len(verify_image or b'')}"
                )
                break

            del frame, rgb, small  # optimization 9
            time.sleep(0.05)

    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("Entry liveness process crashed")
        _liveness_entry_emit(f"EXCEPTION {type(e).__name__}: {e}")
        try:
            liveness_queue.put(
                {
                    "type":   MSG_LIVENESS_FAIL,
                    "reason": f"Entry process error: {e}",
                    "traceback": tb,
                },
                timeout=5,
            )
        except Exception as qe:
            _liveness_entry_emit(f"could not enqueue crash FAIL message: {qe}")
        return

    finally:
        _liveness_entry_emit("finally: closing FaceMesh / releasing camera")
        if face_mesh is not None:
            face_mesh.close()
            del face_mesh
            gc.collect()
        if cap is not None:
            cap.release()

    try:
        if liveness_passed:
            liveness_queue.put(
                {"type": MSG_LIVENESS_PASS, "verify_image": verify_image},
                timeout=5,
            )
            _liveness_entry_emit(
                f"queued {MSG_LIVENESS_PASS} verify_image_len={len(verify_image or b'')}"
            )
        else:
            msg = (
                f"Liveness check timed out after {liveness_timeout}s. "
                f"Blinks: {blink_count}/{BLINKS_REQUIRED}. "
                f"Head turn: {'yes' if head_turned else 'no'}."
            )
            liveness_queue.put(
                {"type": MSG_LIVENESS_FAIL, "reason": msg},
                timeout=5,
            )
            _liveness_entry_emit(f"queued {MSG_LIVENESS_FAIL}: {msg}")
    except Exception as qe:
        _liveness_entry_emit(f"FATAL liveness_queue.put failed: {type(qe).__name__}: {qe}")


def _monitoring_process_target(
    event_queue:  multiprocessing.Queue,
    stop_event:   multiprocessing.synchronize.Event,
    pause_event:  multiprocessing.synchronize.Event,
    config:       dict,
):
    """
    Phase 2 OS process.
    Continuous monitoring at reduced resolution.
    Exits cleanly when stop_event is set.
    """
    logging.basicConfig(level=logging.INFO)

    import cv2
    from shared.constants import (
        EventType, EventSeverity,
        FACE_ABSENT_THRESHOLD_SECONDS,
        GAZE_DEVIATION_THRESHOLD_SECONDS,
        FACE_RECHECK_INTERVAL_SECONDS,
    )

    cap       = None
    face_mesh = None

    try:
        import mediapipe as mp

        # Lazy load after entry process has exited (optimization 7)
        face_mesh = mp.solutions.face_mesh.FaceMesh( #type: ignore[attr-defined]
            max_num_faces=2,
            refine_landmarks=True,     # Covers iris + head pose (optimization 8)
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        cap = _open_camera_capture(config["camera_index"])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config["camera_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config["camera_height"])
        _configure_capture_latency(cap)

        if not cap.isOpened():
            _put_event(event_queue, {
                "type": MSG_PROCTORING_EVENT,
                "event_type": EventType.FACE_ABSENT.value,
                "severity": EventSeverity.MEDIUM.value,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"source": "monitoring_process", "error": "camera_open_failed"},
                "snapshot_path": None,
            })
            return

        face_absent_since:  Optional[datetime] = None
        gaze_away_since:    Optional[datetime] = None
        face_absent_flagged = False
        gaze_flagged        = False
        last_recheck        = time.time()
        last_activity_time  = time.time()

        while not stop_event.is_set():

            # Paused — skip processing (optimization 12)
            if pause_event.is_set():
                time.sleep(0.5)
                continue

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            now = datetime.utcnow()

            # Downscale for analysis (optimization 3)
            small = cv2.resize(
                frame,
                (ANALYSIS_WIDTH, ANALYSIS_HEIGHT),
                interpolation=cv2.INTER_LINEAR,
            )
            rgb    = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            result = face_mesh.process(rgb)

            num_faces = (
                len(result.multi_face_landmarks)
                if result.multi_face_landmarks else 0
            )

            # ── Face absent ────────────────────────────────────────────
            if num_faces == 0:
                if face_absent_since is None:
                    face_absent_since = now
                else:
                    absent_secs = (now - face_absent_since).total_seconds()
                    if (
                        absent_secs >= FACE_ABSENT_THRESHOLD_SECONDS
                        and not face_absent_flagged
                    ):
                        snap = _save_snapshot(frame, config["snapshot_dir"])
                        _put_event(event_queue, {
                            "type":          MSG_PROCTORING_EVENT,
                            "event_type":    EventType.FACE_ABSENT.value,
                            "severity":      EventSeverity.MEDIUM.value,
                            "timestamp":     now.isoformat(),
                            "metadata":      {"absent_seconds": round(absent_secs, 1)},
                            "snapshot_path": snap,
                        })
                        face_absent_flagged = True
            else:
                face_absent_since   = None
                face_absent_flagged = False
                last_activity_time  = time.time()

                # ── Multiple faces ─────────────────────────────────────
                if num_faces > 1:
                    snap = _save_snapshot(frame, config["snapshot_dir"])
                    _put_event(event_queue, {
                        "type":          MSG_PROCTORING_EVENT,
                        "event_type":    EventType.MULTIPLE_FACES.value,
                        "severity":      EventSeverity.HIGH.value,
                        "timestamp":     now.isoformat(),
                        "metadata":      {"face_count": num_faces},
                        "snapshot_path": snap,
                    })

            # ── Head pose + gaze (single face only) ────────────────────
            if num_faces == 1:
                landmarks = result.multi_face_landmarks[0]
                yaw, pitch = _calc_head_pose(
                    landmarks, ANALYSIS_HEIGHT, ANALYSIS_WIDTH
                )
                gaze_ok = abs(yaw) < 30 and abs(pitch) < 20

                if not gaze_ok:
                    if gaze_away_since is None:
                        gaze_away_since = now
                    else:
                        away_secs = (now - gaze_away_since).total_seconds()
                        if (
                            away_secs >= GAZE_DEVIATION_THRESHOLD_SECONDS
                            and not gaze_flagged
                        ):
                            snap = _save_snapshot(frame, config["snapshot_dir"])
                            _put_event(event_queue, {
                                "type":          MSG_PROCTORING_EVENT,
                                "event_type":    EventType.GAZE_AWAY.value,
                                "severity":      EventSeverity.LOW.value,
                                "timestamp":     now.isoformat(),
                                "metadata": {
                                    "yaw":              round(yaw, 1),
                                    "pitch":            round(pitch, 1),
                                    "duration_seconds": round(away_secs, 1),
                                    "yaw_threshold":    30,
                                    "pitch_threshold":  20,
                                    "duration_threshold_seconds": GAZE_DEVIATION_THRESHOLD_SECONDS,
                                    "source":           "client_head_pose",
                                },
                                "snapshot_path": snap,
                            })
                            gaze_flagged = True
                else:
                    gaze_away_since = None
                    gaze_flagged    = False

            # ── Periodic server re-verification ────────────────────────
            if (
                time.time() - last_recheck >= FACE_RECHECK_INTERVAL_SECONDS
                and num_faces == 1
            ):
                _recheck_identity(
                    frame,
                    config["base_url"],
                    config["token"],
                    event_queue,
                    config["snapshot_dir"],
                    now,
                )
                last_recheck = time.time()

            # Release frames immediately (optimization 9)
            del small, rgb, frame

            # Adaptive FPS (optimization 4)
            idle = time.time() - last_activity_time
            time.sleep(FPS_IDLE if idle > IDLE_SECS else FPS_ACTIVE)

    except Exception:
        logger.exception("Camera monitoring process crashed")

    finally:
        # Always release — mitigation S2
        if face_mesh is not None:
            face_mesh.close()
            del face_mesh
            gc.collect()
        if cap is not None:
            cap.release()


# ══════════════════════════════════════════════════════════════════════════════
# CameraMonitor — main process controller class
# ══════════════════════════════════════════════════════════════════════════════

class CameraMonitor:
    """
    Orchestrates two-phase multiprocessing camera pipeline.

    Usage in exam_window.py:
        monitor = CameraMonitor(
            emit_event=event_logger.log,
            token=token,
            on_liveness_pass=self._on_liveness_passed,
            on_liveness_fail=self._on_liveness_failed,
        )
        monitor.start_entry()
        # on_liveness_pass fires when student passes liveness
        # exam_window then calls monitor.start_monitoring()
    """

    def __init__(
        self,
        emit_event: Callable,
        token: str,
        on_liveness_pass: Callable,
        on_liveness_fail: Callable,
        on_preview_frame: Optional[Callable[[bytes], None]] = None,
    ):
        self.emit_event       = emit_event
        self.on_liveness_pass = on_liveness_pass
        self.on_liveness_fail = on_liveness_fail
        self.on_preview_frame = on_preview_frame

        from client.config import (
            BASE_URL,
            CAMERA_HEIGHT,
            CAMERA_INDEX,
            CAMERA_WIDTH,
            LIVENESS_TIMEOUT_SECONDS,
            SNAPSHOT_DIR,
        )

        # Config dict passed to processes (mitigation E4 — token in dict not CLI arg)
        self._config = {
            "camera_index":  CAMERA_INDEX,
            "camera_width":  CAMERA_WIDTH,
            "camera_height": CAMERA_HEIGHT,
            "liveness_timeout_secs": LIVENESS_TIMEOUT_SECONDS,
            "snapshot_dir":  str(SNAPSHOT_DIR),
            "base_url":      BASE_URL,
            "token":         token,
        }

        # IPC primitives
        self._liveness_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)   # mitigation E3
        self._preview_queue:  multiprocessing.Queue = multiprocessing.Queue(maxsize=2)
        self._event_queue:    multiprocessing.Queue = multiprocessing.Queue(maxsize=0)   # mitigation S5
        self._stop_event:     multiprocessing.synchronize.Event = multiprocessing.Event()
        self._pause_event:    multiprocessing.synchronize.Event = multiprocessing.Event()

        # Process handles
        self._entry_process:      Optional[multiprocessing.Process] = None
        self._monitoring_process: Optional[multiprocessing.Process] = None

        # Main-process threads
        self._reader_thread:   Optional[threading.Thread] = None
        self._liveness_thread: Optional[threading.Thread] = None
        self._preview_thread:  Optional[threading.Thread] = None
        self._reader_running   = False
        self._preview_running  = False
        self._preview_emit_lock = threading.Lock()
        self._last_preview_emit_at = 0.0

    # ── Public API ─────────────────────────────────────────────────────────

    def start_entry(self):
        """Start Phase 1 — liveness verification."""
        self._start_queue_reader()

        self._entry_process = multiprocessing.Process(
            target=_entry_process_target,
            args=(self._liveness_queue, self._preview_queue, self._config),
            daemon=True,       # mitigation S1
            name="CameraEntry",
        )
        self._entry_process.start()
        logger.info("Entry process started (PID %d)", self._entry_process.pid)

        self._liveness_thread = threading.Thread(
            target=self._watch_liveness,
            daemon=True,
            name="LivenessWatcher",
        )
        self._liveness_thread.start()
        self._preview_running = True
        self._preview_thread = threading.Thread(
            target=self._read_preview_queue,
            daemon=True,
            name="LivenessPreviewReader",
        )
        self._preview_thread.start()

    def start_monitoring(self):
        """
        Start Phase 2 — continuous monitoring.
        Waits for entry process to fully exit first (mitigation S3).
        If start_entry() was never used, starts the queue reader here so events drain.
        """
        if not self._reader_running:
            self._start_queue_reader()

        if self._entry_process and self._entry_process.is_alive():
            self._entry_process.join(timeout=5)
            if self._entry_process.is_alive():
                logger.warning(
                    "[liveness] entry process still alive after join(5s) — terminating"
                )
                self._entry_process.terminate()
                self._entry_process.join(timeout=2)
        if self._entry_process is not None:
            logger.info(
                "[liveness] entry process finished exitcode=%s (None=still running)",
                self._entry_process.exitcode,
            )

        logger.info("Entry process exited — starting monitoring process")

        self._monitoring_process = multiprocessing.Process(
            target=_monitoring_process_target,
            args=(
                self._event_queue,
                self._stop_event,
                self._pause_event,
                self._config,
            ),
            daemon=True,       # mitigation S1
            name="CameraMonitoring",
        )
        self._monitoring_process.start()
        logger.info(
            "Monitoring process started (PID %d)",
            self._monitoring_process.pid,
        )

    def pause(self):
        """Pause monitoring during exam pause."""
        self._pause_event.set()
        logger.info("Camera monitoring paused")

    def resume(self):
        """Resume after exam pause."""
        self._pause_event.clear()
        logger.info("Camera monitoring resumed")

    def stop(self):
        """
        Stop all processes cleanly.
        Uses join(timeout) + terminate() — no hang possible (mitigation S4).
        """
        logger.info("Stopping camera monitor", stack_info=True)
        self._stop_event.set()
        self._reader_running = False
        self._preview_running = False

        for proc, name in [
            (self._entry_process,      "entry"),
            (self._monitoring_process, "monitoring"),
        ]:
            if proc is None:
                continue
            proc.join(timeout=5)
            if proc.is_alive():
                logger.warning("Force-killing %s process", name)
                proc.terminate()
                proc.join(timeout=2)
                if proc.is_alive():
                    proc.kill()  # Last resort

        logger.info("Camera monitor stopped")

    def _stop_preview_pump_and_join(self, join_timeout: float = 2.0) -> None:
        """
        Stop the preview reader thread so we stop enqueueing pixmap work on Qt.
        Without this, thousands of QueuedConnection deliveries can run ahead of
        QTimer callbacks and make the app appear hung after liveness completes.
        """
        self._preview_running = False
        t = self._preview_thread
        if t is not None and t.is_alive():
            t.join(timeout=join_timeout)

    # ── Internal — liveness watcher thread ────────────────────────────────

    def _watch_liveness(self):
        """
        Blocks on liveness_queue until entry process puts a result.
        Fires the appropriate callback then exits.
        """
        timeout_cfg = max(10, int(self._config.get("liveness_timeout_secs", 45)))
        last_diag = time.time()
        try:
            deadline = time.time() + timeout_cfg + 25
            logger.info(
                "[liveness.watcher] start timeout_cfg=%ss watcher_deadline_s=%s",
                timeout_cfg,
                timeout_cfg + 25,
            )
            result = None
            while time.time() < deadline:
                now = time.time()
                if now - last_diag >= 2.0:
                    last_diag = now
                    proc = self._entry_process
                    alive = proc.is_alive() if proc else None
                    ec = proc.exitcode if proc else None
                    try:
                        qsz = self._liveness_queue.qsize()
                    except Exception:
                        qsz = "?"
                    logger.info(
                        "[liveness.watcher] tick alive=%s exitcode=%s queue_size~%s "
                        "deadline_in=%.1fs",
                        alive,
                        ec,
                        qsz,
                        deadline - now,
                    )

                if self._entry_process and self._entry_process.exitcode is not None:
                    ec = self._entry_process.exitcode
                    if ec != 0 and self._liveness_queue.empty():
                        logger.warning(
                            "[liveness.watcher] child exitcode=%s with empty queue — failing",
                            ec,
                        )
                        self._stop_preview_pump_and_join()
                        self.on_liveness_fail(
                            f"Liveness process exited unexpectedly with code {ec}."
                        )
                        return
                    if ec == 0 and self._liveness_queue.empty() and not self._entry_process.is_alive():
                        logger.warning(
                            "[liveness.watcher] child exitcode=0 but queue still empty "
                            "(waiting for message or deadline)"
                        )
                try:
                    result = self._liveness_queue.get(timeout=0.5)
                    logger.info(
                        "[liveness.watcher] received queue message type=%r keys=%s",
                        result.get("type") if isinstance(result, dict) else type(result),
                        list(result.keys()) if isinstance(result, dict) else None,
                    )
                    break
                except Empty:
                    continue
            if result is None:
                logger.error(
                    "[liveness.watcher] no result before deadline entry_exitcode=%s",
                    self._entry_process.exitcode if self._entry_process else None,
                )
                self._stop_preview_pump_and_join()
                exit_code = self._entry_process.exitcode if self._entry_process else None
                self.on_liveness_fail(
                    f"Liveness check timed out waiting for worker response. Worker exit code: {exit_code}."
                )
                return
            self._stop_preview_pump_and_join()
            if result.get("type") == MSG_LIVENESS_PASS:
                logger.info("Liveness passed")
                self.on_liveness_pass(result.get("verify_image"))
            else:
                reason = result.get("reason", "Liveness check failed")
                tb = result.get("traceback")
                if tb:
                    logger.error("Liveness failed: %s\n%s", reason, tb)
                else:
                    logger.warning("Liveness failed: %s", reason)
                self.on_liveness_fail(reason)
        except Exception as e:
            logger.exception("Liveness watcher failed")
            self._stop_preview_pump_and_join()
            self.on_liveness_fail(f"Liveness watcher error: {e}")

    def _read_preview_queue(self):
        """Drain best-effort liveness preview frames for the UI."""
        while self._preview_running:
            try:
                item = self._preview_queue.get(timeout=0.5)
            except Empty:
                continue
            except Exception:
                continue
            if item.get("type") != MSG_PREVIEW_FRAME:
                continue
            image = item.get("image")
            if image and self.on_preview_frame:
                now = time.time()
                with self._preview_emit_lock:
                    if now - self._last_preview_emit_at < PREVIEW_UI_MIN_INTERVAL_SECS:
                        continue
                    self._last_preview_emit_at = now
                try:
                    self.on_preview_frame(image)
                except Exception:
                    logger.exception("Preview frame callback failed")

    # ── Internal — event queue reader thread ──────────────────────────────

    def _start_queue_reader(self):
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._read_event_queue,
            daemon=True,
            name="CameraQueueReader",
        )
        self._reader_thread.start()

    def _read_event_queue(self):
        """
        Drains event_queue continuously.
        Validates every event before passing to EventLogger (mitigation E1, E2).
        Uses get(timeout=0.5) to check _reader_running regularly (mitigation S7).
        """
        from client.modules.proctoring.event_logger import ProctoringEvent
        from shared.constants import EventType, EventSeverity

        while self._reader_running:
            try:
                item = self._event_queue.get(timeout=0.5)
            except Exception:
                continue  # Timeout — normal

            # Only process proctoring events
            if item.get("type") != MSG_PROCTORING_EVENT:
                continue

            # Security allowlist check (mitigation E1)
            event_type_str = item.get("event_type", "")
            if event_type_str not in VALID_EVENT_TYPES:
                logger.warning("Rejected unknown event type: %s", event_type_str)
                continue

            # Reconstruct and validate fields (mitigation E2)
            try:
                event = ProctoringEvent(
                    event_type=EventType(event_type_str),
                    severity=EventSeverity(item.get("severity", "medium")),
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    metadata=item.get("metadata") or {},
                    snapshot_path=item.get("snapshot_path"),
                )
                self.emit_event(event)
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Malformed camera event discarded: %s", e)
