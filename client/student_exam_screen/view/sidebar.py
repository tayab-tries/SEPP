from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QWidget, QStackedWidget
from PySide6.QtGui import QPixmap

from .styles import TEXT_PRIMARY, TEXT_MUTED


class SidebarWidget(QFrame):
    """Right-side proctoring sidebar with a live camera feed during the exam."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("examSidebar")
        self.setFixedWidth(320)
        self.setStyleSheet("""
            QFrame#examSidebar {
                background: #EEF3F8;
                border-left: 1px solid #DDE5EF;
            }
            QLabel { background: transparent; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        heading = QLabel("Camera Feed")
        heading.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:15px; font-weight:800;")
        root.addWidget(heading)

        # ── Camera card ────────────────────────────────────────────────────
        self.camera_box = QWidget()
        self.camera_box.setObjectName("cameraBox")
        self.camera_box.setFixedSize(276, 188)
        self.camera_box.setStyleSheet("""
            QWidget#cameraBox {
                background: #111827;
                border-radius: 12px;
                border: 1px solid #1E293B;
            }
        """)

        # Stack: page 0 = live feed label, page 1 = status-only label
        box_layout = QVBoxLayout(self.camera_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)

        self._stack = QStackedWidget()
        box_layout.addWidget(self._stack)

        # Page 0 — live camera QLabel (fills card edge-to-edge)
        self._camera_label = QLabel()
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setStyleSheet("background: #111827; border-radius: 12px;")
        self._stack.addWidget(self._camera_label)

        # Page 1 — status text shown when camera is disabled / initialising
        status_page = QWidget()
        status_page.setStyleSheet("background: transparent;")
        sp_lay = QVBoxLayout(status_page)
        sp_lay.setContentsMargins(16, 16, 16, 16)
        sp_lay.setSpacing(8)
        sp_lay.addStretch()

        self._status_icon = QLabel("●")
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_icon.setStyleSheet("color: rgba(148,163,184,0.55); font-size: 28px;")
        sp_lay.addWidget(self._status_icon)

        self._status_label = QLabel("Camera initialising…")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "color: rgba(148,163,184,0.80); font-size: 12px; font-weight: 600;"
        )
        sp_lay.addWidget(self._status_label)
        sp_lay.addStretch()
        self._stack.addWidget(status_page)

        # Start on the status page until the first frame arrives
        self._stack.setCurrentIndex(1)

        root.addWidget(self.camera_box, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── Footer note ────────────────────────────────────────────────────
        self._note = QLabel("Camera active — you are being monitored.")
        self._note.setWordWrap(True)
        self._note.setStyleSheet(f"color:{TEXT_MUTED}; font-size:12px;")
        root.addWidget(self._note)
        root.addStretch()

    # ── Public API ─────────────────────────────────────────────────────────

    @Slot(bytes)
    def set_preview_frame(self, image_bytes: bytes) -> None:
        """Receive a JPEG-encoded frame and paint it into the camera label."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_bytes):
            return
        self._camera_label.setPixmap(
            pixmap.scaled(
                self._camera_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        # Switch to the live feed page on first successful frame
        if self._stack.currentIndex() != 0:
            self._stack.setCurrentIndex(0)

    def set_camera_status(self, text: str) -> None:
        """Show a status-text page instead of the live feed (e.g. camera disabled)."""
        self._status_label.setText(text)
        self._stack.setCurrentIndex(1)
        self._note.setText(text)
