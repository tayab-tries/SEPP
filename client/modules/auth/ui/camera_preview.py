"""
client/modules/auth/ui/camera_preview.py

Live camera preview — camera runs continuously, never stops until widget is hidden.
Retake just unfreezes the display — no cold restart delay.
"""

import cv2
import numpy as np
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtGui import QCloseEvent


class _CameraThread(QThread):
    frame_ready = Signal(QImage)

    def __init__(self, camera_index: int = 0):
        super().__init__()
        self._camera_index = camera_index
        self._running      = False

    def run(self):
        self._running = True
        cap = cv2.VideoCapture(self._camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self._running:
            ret, frame = cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
            self.frame_ready.emit(img.copy())

        cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)


class CameraPreviewWidget(QWidget):
    """
    Live camera preview.
    Camera starts once and runs continuously.
    Retake unfreezes display without restarting camera — no delay.
    """

    frame_captured = Signal(object)  # numpy BGR array

    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._camera_index   = camera_index
        self._preview_width = 320
        self._preview_height = 240
        self._camera_thread: Optional[_CameraThread] = None
        self._last_frame     = None
        self._captured_frame = None
        self._frozen         = False   # True = showing frozen frame
        self._build()

    def set_preview_size(self, width: int, height: int):
        self._preview_width = max(160, width)
        self._preview_height = max(120, height)
        self._preview.setFixedSize(self._preview_width, self._preview_height)

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self):
        """Start camera — called explicitly when step 3 becomes visible."""
        self._frozen = False
        self._captured_frame = None
        self._capture_btn.show()
        self._retake_btn.hide()
        self._preview.setText("Camera starting...")
        self._status.setText("Position your face clearly in the frame")
        self.ensure_running()

    def ensure_running(self):
        """Start camera thread if needed without resetting UI state."""
        if self._camera_thread and self._camera_thread.isRunning():
            return
        self._camera_thread = _CameraThread(self._camera_index)
        self._camera_thread.frame_ready.connect(self._on_frame)
        self._camera_thread.start()

    def stop(self):
        """Stop camera — called when leaving step 3."""
        self._frozen = False
        if self._camera_thread:
            self._camera_thread.stop()
            self._camera_thread = None
        self._preview.setText("Camera starting...")
        self._last_frame     = None
        self._captured_frame = None

    def closeEvent(self, event: QCloseEvent):
        self.stop()
        super().closeEvent(event)

    def __del__(self):
        # Best-effort thread cleanup for interpreter/window teardown.
        try:
            self.stop()
        except Exception:
            pass

    def get_captured_frame(self):
        return self._captured_frame

    # ── Build ──────────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._preview = QLabel()
        self._preview.setFixedSize(self._preview_width, self._preview_height)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet("""
            QLabel {
                background-color: rgba(0,0,0,0.5);
                border: 2px solid rgba(255,255,255,0.2);
                border-radius: 8px;
                color: #BDD0F8; font-size: 12px;
            }
        """)
        self._preview.setText("Camera starting...")
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._status = QLabel("Position your face clearly in the frame")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            "font-size: 11px; color: #BDD0F8; background: transparent;"
        )
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._capture_btn = QPushButton("✓  Take Photo")
        self._capture_btn.setFixedHeight(40)
        self._capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._capture_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B76E8; color: white;
                border: none; border-radius: 4px;
                outline: none;
                font-size: 12px; font-weight: 700; padding: 0 20px;
            }
            QPushButton:hover { background-color: #5590FF; }
            QPushButton:pressed { background-color: #1A4DB5; }
            QPushButton:focus { border: none; outline: none; }
        """)
        self._capture_btn.clicked.connect(self._capture)

        self._retake_btn = QPushButton("↺  Retake")
        self._retake_btn.setFixedHeight(40)
        self._retake_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retake_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #FFFFFF;
                border: 2px solid #FFFFFF; border-radius: 4px;
                font-size: 12px; font-weight: 700; padding: 0 20px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.1); }
        """)
        self._retake_btn.clicked.connect(self._retake)
        self._retake_btn.hide()

        btn_row.addWidget(self._capture_btn)
        btn_row.addWidget(self._retake_btn)
        layout.addLayout(btn_row)

    # ── Frame handling ─────────────────────────────────────────────────────

    def _on_frame(self, img: QImage):
        """Always store latest frame. Only update display if not frozen."""
        # Store raw frame regardless
        img_rgb = img.convertToFormat(QImage.Format.Format_RGB888)
        ptr     = img_rgb.bits()
        arr     = np.frombuffer(ptr, dtype=np.uint8).reshape(
            img_rgb.height(), img_rgb.width(), 3
        )
        self._last_frame = cv2.cvtColor(arr.copy(), cv2.COLOR_RGB2BGR)

        # Only update preview display when not showing frozen capture
        if not self._frozen:
            pix = QPixmap.fromImage(img).scaled(
                self._preview_width, self._preview_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(pix)
            self._preview.setText("")

    def _capture(self):
        if self._last_frame is None:
            self._status.setText("Camera not ready. Please wait.")
            return

        # Freeze display on current frame — camera thread keeps running
        self._frozen         = True
        self._captured_frame = self._last_frame.copy()

        # Show frozen frame
        rgb = cv2.cvtColor(self._captured_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self._preview_width, self._preview_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pix)
        self._status.setText("✓ Photo captured — click Retake to try again")

        self._capture_btn.hide()
        self._retake_btn.show()

        self.frame_captured.emit(self._captured_frame)

    def _retake(self):
        """Unfreeze display — camera already running, zero delay."""
        self._frozen         = False
        self._captured_frame = None
        self._status.setText("Position your face clearly in the frame")
        self._retake_btn.hide()
        self._capture_btn.show()
        # No camera restart — just resume showing live frames
