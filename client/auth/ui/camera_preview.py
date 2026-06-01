"""
client/modules/auth/ui/embedded_camera_capture.py

Reusable embedded camera capture widget for signup-style flows.

Design goals:
- Camera starts only when the user clicks Start Camera.
- Camera work runs in a QThread so the UI stays responsive.
- Emits readable camera state changes for parent screens.
- Handles camera unavailable / failed reads / retry states.
- Captures a BGR numpy frame for backend upload.
- Keeps quality checks lightweight and advisory; backend remains authoritative.
"""

from __future__ import annotations

import cv2
import numpy as np
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QCloseEvent, QImage, QPainter, QPainterPath, QPen, QColor, QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget

BG          = "#EAECF2"
CARD        = "#FFFFFF"
BORDER      = "#DDE0E8"
T_PRIMARY   = "#111827"
T_SECONDARY = "#6B7280"
NAVY        = "#0F1F3D"
GREEN       = "#16A34A"
AMBER       = "#D97706"
RED         = "#DC2626"
INP_BORDER  = "#D1D5DB"
INP_FOCUS   = "#6B7280"
BG_LEFT = "#F7F8FA"
BG_INPUT = "#FFFFFF"
NAVY_HOVER = "#1c3461"
NAVY_PRESSED = "#091529"

def _calculate_ear(landmarks):
    import math
    def euclidean_distance(p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

    # Right eye indices: 33, 160, 158, 133, 153, 144
    # Left eye indices: 362, 385, 387, 263, 373, 380
    def eye_aspect_ratio(eye_indices):
        p1 = landmarks[eye_indices[0]]
        p2 = landmarks[eye_indices[1]]
        p3 = landmarks[eye_indices[2]]
        p4 = landmarks[eye_indices[3]]
        p5 = landmarks[eye_indices[4]]
        p6 = landmarks[eye_indices[5]]
        val1 = euclidean_distance(p2, p6)
        val2 = euclidean_distance(p3, p5)
        val3 = euclidean_distance(p1, p4)
        if val3 == 0:
            return 0.0
        return (val1 + val2) / (2.0 * val3)

    ear_right = eye_aspect_ratio([33, 160, 158, 133, 153, 144])
    ear_left = eye_aspect_ratio([362, 385, 387, 263, 373, 380])
    return (ear_right + ear_left) / 2.0


class _EmbeddedCameraThread(QThread):
    """Background camera reader with explicit ready/error signals."""

    frame_ready = Signal(QImage)
    camera_ready = Signal()
    camera_error = Signal(str)
    analysis_ready = Signal(bool, bool, list) # blink_detected, multiple_faces, bboxes

    def __init__(self, camera_index: int = 0, width: int = 1280, height: int = 720):
        super().__init__()
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._running = False

    def run(self):
        self._running = True
        cap = None
        emitted_ready = False
        failed_reads = 0
        blink_detected = False

        try:
            import mediapipe as mp
            mp_face_mesh = mp.solutions.face_mesh
            face_mesh = mp_face_mesh.FaceMesh(
                max_num_faces=2,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except ImportError:
            self.camera_error.emit("MediaPipe is not installed. Please run 'pip install mediapipe'")
            return
        except Exception as exc:
            self.camera_error.emit(f"Failed to load MediaPipe: {exc}")
            return

        try:
            import platform
            if platform.system() == "Windows":
                cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(self._camera_index)
            
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)

            if not cap.isOpened():
                self.camera_error.emit(
                    "Camera unavailable. It may be disconnected, blocked, or used by another application."
                )
                return

            while self._running:
                ret, frame = cap.read()

                if not ret or frame is None:
                    failed_reads += 1
                    if failed_reads >= 30:
                        self.camera_error.emit(
                            "Camera feed lost. Close other camera apps and click Retry Camera."
                        )
                        return
                    self.msleep(30)
                    continue

                failed_reads = 0

                if not emitted_ready:
                    emitted_ready = True
                    self.camera_ready.emit()

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # --- MediaPipe processing ---
                results = face_mesh.process(rgb)
                multiple_faces = False
                bboxes = []

                if results.multi_face_landmarks:
                    h, w, ch = rgb.shape
                    for face_landmarks in results.multi_face_landmarks:
                        x_min = int(min(lm.x for lm in face_landmarks.landmark) * w)
                        x_max = int(max(lm.x for lm in face_landmarks.landmark) * w)
                        y_min = int(min(lm.y for lm in face_landmarks.landmark) * h)
                        y_max = int(max(lm.y for lm in face_landmarks.landmark) * h)
                        bboxes.append((x_min, y_min, x_max - x_min, y_max - y_min))

                    if len(results.multi_face_landmarks) > 1:
                        multiple_faces = True
                    else:
                        ear = _calculate_ear(results.multi_face_landmarks[0].landmark)
                        if ear < 0.20: # Typical threshold for a blink
                            blink_detected = True
                
                self.analysis_ready.emit(blink_detected, multiple_faces, bboxes)
                # ----------------------------

                h, w, ch = rgb.shape
                img = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img.copy())

                # Small sleep keeps CPU usage calmer without making preview feel laggy.
                self.msleep(15)

        except Exception as exc:
            self.camera_error.emit(f"Camera error: {exc}")
        finally:
            if cap is not None:
                cap.release()
            if 'face_mesh' in locals() and face_mesh is not None:
                face_mesh.close()
            self._running = False

    def stop(self):
        self._running = False
        self.wait(2000)

class _CameraPreviewLabel(QLabel):
    """
    QLabel subclass that:
    - Clips the camera feed to rounded corners via QPainterPath
    - Adds horizontal padding so the feed doesn't touch the edges
    - Paints face-guide overlays (dashed oval, crosshairs, oval focus dot)
    - Keeps overlays visible on both live feed AND frozen/captured frames
    """

    def paintEvent(self, event):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        radius = 12.0

        path = QPainterPath()
        # Draw exactly at the bounds to avoid tiny margins and brush misalignment
        path.addRoundedRect(0, 0, w, h, radius, radius)

        pix = self.pixmap()
        if pix and not pix.isNull():
            # QBrush perfectly maps the texture and antialiases the rounded corners
            brush = QBrush(pix)
            painter.fillPath(path, brush)
        else:
            # Draw placeholder background
            painter.fillPath(path, QColor("#C8CDD8"))
            # Draw placeholder text
            painter.setPen(QColor("#4A5568"))
            font = painter.font()
            font.setPixelSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

        # Draw the subtle border over the image/background
        pen = QPen(QColor(160, 185, 220, 127))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.end()

class EmbeddedCameraCaptureWidget(QWidget):
    """
    Embedded camera widget for Step 3 signup capture.

    Public signals:
      - frame_captured(frame): emits captured numpy BGR frame
      - frame_cleared(): emitted after retake/reset clears the captured photo
      - status_changed(message, state): state = idle/loading/success/error/warning/captured
    """

    frame_captured = Signal(object)
    frame_cleared = Signal()
    status_changed = Signal(str, str)

    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._camera_index = camera_index
        self._preview_width = 400
        self._preview_height = 225
        self._camera_thread: Optional[_EmbeddedCameraThread] = None
        self._last_frame = None
        self._captured_frame = None
        self._bboxes = []
        self._frozen = False
        self._state = "idle"

        self._build()
        self._apply_state("idle", "Camera not started.")

    # ── Public API ──────────────────────────────────────────────────────

    def set_preview_size(self, width: int, height: int):
        self._preview_width = max(220, width)
        self._preview_height = max(160, height)
        self._preview.setFixedSize(self._preview_width, self._preview_height)

    def get_captured_frame(self):
        return self._captured_frame

    def has_captured_frame(self) -> bool:
        return self._captured_frame is not None

    def start(self):
        """User-triggered camera start."""
        if self._camera_thread and self._camera_thread.isRunning():
            return

        self._frozen = False
        self._captured_frame = None
        self._last_frame = None
        self._preview.setPixmap(QPixmap())
        self._apply_state("loading", "Camera starting...")
        self._show_buttons(start=False, capture=False, retake=False, retry=False)
        self._start_btn.setVisible(True)
        self._start_btn.setEnabled(False)

        self._camera_thread = _EmbeddedCameraThread(self._camera_index)
        self._camera_thread.frame_ready.connect(self._on_frame)
        self._camera_thread.camera_ready.connect(self._on_camera_ready)
        self._camera_thread.camera_error.connect(self._on_camera_error)
        self._camera_thread.analysis_ready.connect(self._on_analysis)
        self._camera_thread.start()

    def retry(self):
        self.stop(clear_preview=True)
        self.start()

    def stop(self, clear_preview: bool = False):
        self._frozen = False
        if self._camera_thread:
            self._camera_thread.stop()
            self._camera_thread = None

        if clear_preview:
            self._preview.setPixmap(QPixmap())
            self._last_frame = None

        self._apply_state("idle", "Camera not started.")
        self._show_buttons(start=True, capture=False, retake=False, retry=False)

    def reset_capture(self):
        """Clear captured frame. Does not necessarily stop the camera."""
        self._captured_frame = None
        self._frozen = False
        self.frame_cleared.emit()

        if self._camera_thread and self._camera_thread.isRunning():
            self._apply_state("success", "Camera connected. Position your face clearly.")
            self._show_buttons(start=False, capture=True, retake=False, retry=False)
        else:
            self._preview.setPixmap(QPixmap())
            self._apply_state("idle", "Camera not started.")
            self._show_buttons(start=True, capture=False, retake=False, retry=False)

    def closeEvent(self, event: QCloseEvent):
        self.stop(clear_preview=True)
        super().closeEvent(event)

    def __del__(self):
        try:
            self.stop(clear_preview=True)
        except Exception:
            pass

    # ── UI build ────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._preview = _CameraPreviewLabel("")
        self._preview.setFixedSize(self._preview_width, self._preview_height)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Note: Background, border, and rounding are drawn manually in paintEvent
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(14)

        self._status = QLabel("Camera not started.")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setContentsMargins(0, 4, 0, 0)
        self._status.setStyleSheet("font-size: 12px; font-weight: 500; color: #8FA8D8; background: transparent; border: none;")
        
        self._start_btn = self._make_button("START CAMERA", "primary")
        self._capture_btn = self._make_button("TAKE PHOTO", "primary")
        self._retake_btn = self._make_button("RETAKE", "secondary")
        self._retry_btn = self._make_button("RETRY CAMERA", "warning")

        self._start_btn.clicked.connect(self.start)
        self._capture_btn.clicked.connect(self._capture)
        self._retake_btn.clicked.connect(self._retake)
        self._retry_btn.clicked.connect(self.retry)
        
        btn_slot = QVBoxLayout()
        btn_slot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for btn in [self._start_btn, self._capture_btn, self._retake_btn, self._retry_btn]:
            btn.setFixedWidth(200)
            btn_slot.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(btn_slot)
        
        layout.addWidget(self._status)

        # Only show the relevant button for the current state — never all at once
        self._show_buttons(start=True, capture=False, retake=False, retry=False)

    def _make_button(self, text: str, variant: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if variant == "secondary":
            style = """
                QPushButton {
                    background-color: transparent; color: #DCE8FF;
                    border: 1px solid rgba(220, 232, 255, 0.65);
                    border-radius: 10px; padding: 0 18px;
                    font-size: 11px; font-weight: 800; letter-spacing: 1px;
                }
                QPushButton:hover { background-color: rgba(255,255,255,0.08); }
                QPushButton:disabled { color: #6F7F9F; border-color: rgba(111,127,159,0.35); }
            """
        elif variant == "warning":
            style = """
                QPushButton {
                    background-color: #F4B942; color: #101828;
                    border: none; border-radius: 10px; padding: 0 18px;
                    font-size: 11px; font-weight: 900; letter-spacing: 1px;
                }
                QPushButton:hover { background-color: #FFD166; }
                QPushButton:disabled { background-color: #56627A; color: #AAB7D4; }
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: NAVY; color: white;
                    border: none; border-radius: 10px; padding: 0 20px;
                    font-size: 11px; font-weight: 900; letter-spacing: 1px;
                }}
                QPushButton:hover {{ background-color: NAVY_HOVER; }}
                QPushButton:pressed {{ background-color: NAVY_PRESSED; }}
                QPushButton:disabled {{ background-color: #56627A; color: #AAB7D4; }}
            """
        btn.setStyleSheet(style)
        return btn

    # ── Camera callbacks ────────────────────────────────────────────────

    def _on_camera_ready(self):
        self._apply_state("warning", "Camera connected. Please blink once to verify liveness.")
        self._show_buttons(start=False, capture=True, retake=False, retry=False)
        self._capture_btn.setEnabled(False)

    def _on_camera_error(self, message: str):
        self._captured_frame = None
        self._last_frame = None
        self._frozen = False
        if self._camera_thread:
            self._camera_thread = None
        self._preview.setPixmap(QPixmap())
        self._preview.setText("Camera unavailable")
        self._apply_state("error", message)
        self._show_buttons(start=False, capture=False, retake=False, retry=True)
        self.frame_cleared.emit()

    def _on_analysis(self, blink_detected: bool, multiple_faces: bool, bboxes: list):
        self._bboxes = bboxes
        
        if self._frozen or self._state == "captured":
            return
            
        if multiple_faces:
            self._apply_state("error", "Multiple faces detected! Ensure only you are in the frame.")
            self._capture_btn.setEnabled(False)
        elif not blink_detected:
            self._apply_state("warning", "Please blink once to verify liveness.")
            self._capture_btn.setEnabled(False)
        else:
            self._apply_state("success", "Liveness verified. Center your face and take a clear photo.")
            self._capture_btn.setEnabled(True)

    def _on_frame(self, img: QImage):
        img_rgb = img.convertToFormat(QImage.Format.Format_RGB888)
        ptr = img_rgb.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img_rgb.height(), img_rgb.width(), 3)
        self._last_frame = cv2.cvtColor(arr.copy(), cv2.COLOR_RGB2BGR)

        if not self._frozen:
            preview_arr = arr.copy()
            if hasattr(self, '_bboxes') and self._bboxes:
                color = (255, 0, 0) if len(self._bboxes) > 1 else (0, 255, 0)
                for (x, y, w, h) in self._bboxes:
                    cv2.rectangle(preview_arr, (x, y), (x+w, y+h), color, 3)

            # High-quality downscale using OpenCV INTER_AREA
            resized_arr = cv2.resize(preview_arr, (self._preview_width, self._preview_height), interpolation=cv2.INTER_AREA)

            h2, w2 = resized_arr.shape[:2]
            ui_img = QImage(resized_arr.data.tobytes(), w2, h2, 3 * w2, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(ui_img)
            self._preview.setPixmap(pix)

    # ── Capture / quality ───────────────────────────────────────────────

    def _capture(self):
        if self._last_frame is None:
            self._apply_state("warning", "Camera is not ready yet. Please wait a moment.")
            return

        self._frozen = True
        captured = self._last_frame.copy()
        self._show_frozen_frame(captured)

        warning = self._quality_warning(captured)
        if warning:
            self._captured_frame = None
            self._apply_state("error", f"Quality check failed: {warning} You must retake.")
            self._show_buttons(start=False, capture=False, retake=True, retry=False)
        else:
            self._captured_frame = captured
            self._apply_state("captured", "Photo captured. You may continue or retake.")
            self._show_buttons(start=False, capture=False, retake=True, retry=False)
            self.frame_captured.emit(self._captured_frame)

    def _retake(self):
        self._captured_frame = None
        self._frozen = False
        self.frame_cleared.emit()
        self._apply_state("success", "Camera connected. Center your face and take a clear photo.")
        self._show_buttons(start=False, capture=True, retake=False, retry=False)

    def _show_frozen_frame(self, frame):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # High-quality downscale using OpenCV INTER_AREA
            resized_arr = cv2.resize(rgb, (self._preview_width, self._preview_height), interpolation=cv2.INTER_AREA)
            
            fh, fw = resized_arr.shape[:2]
            img = QImage(resized_arr.data.tobytes(), fw, fh, 3 * fw, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(img)
            self._preview.setPixmap(pix)

    def _quality_warning(self, frame) -> str:
        """
        Strict client-side quality blocking.
        Requires a face, applies Gaussian blur before evaluating Laplacian variance
        on the face crop to ignore noise from cheap webcams.
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) == 0:
                return "No face clearly detected. Please face the camera directly in good light."
                
            # Use the largest face found
            faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            x, y, w, h = faces[0]
            face_crop = gray[y:y+h, x:x+w]
            
            # Apply slight Gaussian blur to smooth webcam grain
            blurred_face = cv2.GaussianBlur(face_crop, (3, 3), 0)
            
            brightness = float(np.mean(face_crop))
            blur_score = float(cv2.Laplacian(blurred_face, cv2.CV_64F).var())

            warnings = []
            if blur_score < 15:
                warnings.append("image is too blurry.")
            if brightness < 50:
                warnings.append("lighting is too dim.")
            elif brightness > 245:
                warnings.append("lighting is overexposed.")

            return " ".join(warnings)
        except Exception:
            return "Error assessing quality."

    # ── State helpers ───────────────────────────────────────────────────

    def _apply_state(self, state: str, message: str):
        self._state = state
        colors = {
            "idle": "#8FA8D8",
            "loading": "#BDD0F8",
            "success": "#64D2A6",
            "captured": "#64D2A6",
            "warning": "#FFD166",
            "error": "#FF8A8A",
        }
        self._status.setText(message)
        self._status.setStyleSheet(
            f"font-size: 12px; font-weight: 500; color: {colors.get(state, '#BDD0F8')}; background: transparent; border: none;"
        )
        self.status_changed.emit(message, state)

    def _show_buttons(self, *, start: bool, capture: bool, retake: bool, retry: bool):
        self._start_btn.setVisible(start)
        if start:
            self._start_btn.setEnabled(True)
        self._capture_btn.setVisible(capture)
        self._retake_btn.setVisible(retake)
        self._retry_btn.setVisible(retry)


# ---------------------------------------------------------------------------
# Legacy/unused ideas intentionally not implemented here:
# - MediaPipe FaceMesh/liveness challenge checks: not needed for signup yet.
# - Client-side face embedding extraction: backend MTCNN/FaceNet remains source.
# - Multiple-face enforcement: should be added backend-side later for security.
# ---------------------------------------------------------------------------
