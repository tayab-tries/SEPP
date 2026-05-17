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

class _EmbeddedCameraThread(QThread):
    """Background camera reader with explicit ready/error signals."""

    frame_ready = Signal(QImage)
    camera_ready = Signal()
    camera_error = Signal(str)

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 480):
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

        try:
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
                h, w, ch = rgb.shape
                img = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(img.copy())

                # Small sleep keeps CPU usage calmer without making preview feel laggy.
                self.msleep(15)

        except Exception as exc:
            self.camera_error.emit(f"Camera error: {exc}")
        finally:
            self._running = False
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = 0

        # Clip everything to rounded rect — fixes corner overpainting
        clip_path = QPainterPath()
        clip_path.addRoundedRect(0, 0, w, h, radius, radius)
        painter.setClipPath(clip_path)

        # Fill background
        painter.fillRect(self.rect(), QColor("#C8CDD8"))

        pix = self.pixmap()
        if pix and not pix.isNull():
            # Re-scale with horizontal padding so feed doesn't hug the edges
            pad_x = 24
            available_w = w - 2 * pad_x
            scaled = pix.scaled(
                available_w, h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (w - scaled.width()) // 2
            y = (h - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        else:
            # Placeholder text when camera not started
            painter.setPen(QColor("#4A5568"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

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
        self._preview_width = 430
        self._preview_height = 220
        self._camera_thread: Optional[_EmbeddedCameraThread] = None
        self._last_frame = None
        self._captured_frame = None
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
        self._preview.setStyleSheet("""
            QLabel {
                background-color: #C8CDD8;
                border: 1px solid rgba(160, 185, 220, 0.5);
                border-radius: 0px;
                color: #4A5568;
                font-size: 13px;
                font-weight: 600;
            }
        """)
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
        self._apply_state("success", "Camera connected. Center your face in good lighting.")
        self._show_buttons(start=False, capture=True, retake=False, retry=False)

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

    def _on_frame(self, img: QImage):
        img_rgb = img.convertToFormat(QImage.Format.Format_RGB888)
        ptr = img_rgb.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img_rgb.height(), img_rgb.width(), 3)
        self._last_frame = cv2.cvtColor(arr.copy(), cv2.COLOR_RGB2BGR)

        if not self._frozen:
            h2, w2 = arr.shape[:2]
            gray_img = QImage(arr.data.tobytes(), w2, h2, 3 * w2, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(gray_img).scaled(
                self._preview_width,
                self._preview_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(pix)

    # ── Capture / quality ───────────────────────────────────────────────

    def _capture(self):
        if self._last_frame is None:
            self._apply_state("warning", "Camera is not ready yet. Please wait a moment.")
            return

        self._frozen = True
        self._captured_frame = self._last_frame.copy()
        self._show_frozen_frame(self._captured_frame)

        warning = self._quality_warning(self._captured_frame)
        if warning:
            self._apply_state("warning", f"Photo captured, but {warning} Retake is recommended.")
            self._show_buttons(start=False, capture=False, retake=True, retry=False)
        else:
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
            fh, fw = rgb.shape[:2]
            img = QImage(rgb.data.tobytes(), fw, fh, 3 * fw, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(img).scaled(
                self._preview_width,
                self._preview_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(pix)

    def _quality_warning(self, frame) -> str:
        """
        Lightweight client-side guidance only.
        Backend MTCNN/FaceNet remains authoritative.
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            warnings = []
            if brightness < 100 or blur_score < 50:
                warnings.append("lighting looks dim or the image may be blurry.")
            elif brightness > 220:
                warnings.append("lighting looks overexposed.")

            return " ".join(warnings)
        except Exception:
            return ""

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
        self._capture_btn.setVisible(capture)
        self._retake_btn.setVisible(retake)
        self._retry_btn.setVisible(retry)


# ---------------------------------------------------------------------------
# Legacy/unused ideas intentionally not implemented here:
# - MediaPipe FaceMesh/liveness challenge checks: not needed for signup yet.
# - Client-side face embedding extraction: backend MTCNN/FaceNet remains source.
# - Multiple-face enforcement: should be added backend-side later for security.
# ---------------------------------------------------------------------------
