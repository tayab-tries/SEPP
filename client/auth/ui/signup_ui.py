"""
client/modules/auth/ui/signup_sepp_light_ui.py

Merged SEPP signup UI.

Uses:
- temp.py for the visual language: light page, header/footer, split card,
  soft borders, shadow, input styling, animated face scan, hardware status.
- signup_ui.py for the functional contract and flow: SignupUI class, signals,
  three-step switching, camera binding on Step 3, spinner, reset/busy/status API.

Public contract expected by the controller:
- signals: back_requested, step1_completed, step2_completed, enroll_requested
- methods: go_to_step2, go_to_step3, go_back, set_status,
           get_captured_frame, show_spinner, hide_spinner, reset,
           prewarm_camera, set_busy
"""

from __future__ import annotations

import socket
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QPointF, QSize, QPropertyAnimation, QEasingCurve, QThread, Slot
#from PySide6.QtCore import QDateTime
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCloseEvent,
    QCursor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QDialog
)

from client.modules.common.loading_spinner import SpinnerOverlay
from client.auth.ui.camera_preview import EmbeddedCameraCaptureWidget


INSTITUTIONS = ["Air University"]
DEPARTMENTS = ["NCSA"]


# ─────────────────────────────────────────────────────────────────────────────
#  Light SEPP visual system
# ─────────────────────────────────────────────────────────────────────────────

FONT = "Segoe UI, SF Pro Text, Arial"

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

#──────────────────────────────────────────────────────────────────────────────
#  Latency settings Constants
#──────────────────────────────────────────────────────────────────────────────

LATENCY_HOST = "127.0.0.1"
LATENCY_PORT = 8000
LATENCY_TIMEOUT = 3
LATENCY_INTERVAL_MS = 3000


# ─────────────────────────────────────────────────────────────────────────────
#  Latency thread (TCP round-trip to LATENCY_HOST:LATENCY_PORT, every LATENCY_INTERVAL_MS)
# ─────────────────────────────────────────────────────────────────────────────
class LatencyThread(QThread):
    result = Signal(int)  # ms, or -1 on timeout

    def __init__(self):
        super().__init__()
        self._active = True

    def _measure(self) -> int:
        try:
            t0 = time.perf_counter()
            s = socket.create_connection(
                (LATENCY_HOST, LATENCY_PORT), timeout=LATENCY_TIMEOUT)
            s.close()
            return max(1, int((time.perf_counter() - t0) * 1000))
        except Exception:
            return -1

    def run(self):
        while self._active:
            self.result.emit(self._measure())
            self.msleep(LATENCY_INTERVAL_MS)

    def stop(self):
        self._active = False
        self.wait()
        
        
# ─────────────────────────────────────────────────────────────────────────────
#  Info dialog 
# ─────────────────────────────────────────────────────────────────────────────

class InfoDialog(QDialog):
    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(400)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Single card container — everything lives inside this
        card = QWidget()
        card.setObjectName("dialogCard")
        card.setStyleSheet(f"""
            QWidget#dialogCard {{
                background: {CARD};
                border-radius: 10px;
                border: 1px solid {BORDER};
            }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        # ── Title bar ────────────────────────────────────────────────
        tb = QWidget()
        tb.setStyleSheet("background: transparent;")
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(20, 8, 16, 6)
        tb_lay.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{T_PRIMARY}; background:transparent;"
        )
        tb_lay.addWidget(title_lbl)
        tb_lay.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T_SECONDARY};
                border: none; font-size: 13px; font-weight: 600;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: #F3F4F6; color: {T_PRIMARY}; }}
        """)
        close_btn.clicked.connect(self.accept)
        tb_lay.addWidget(close_btn)
        card_lay.addWidget(tb)

        # ── Divider ──────────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER};")
        card_lay.addWidget(divider)

        # ── Body ─────────────────────────────────────────────────────
        lbl = QLabel(body)
        lbl.setWordWrap(True)
        lbl.setContentsMargins(24, 16, 24, 20)
        lbl.setStyleSheet(
            f"font-size:13px; color:{T_PRIMARY}; background:transparent;"
        )
        card_lay.addWidget(lbl)

        outer.addWidget(card)
                

# ─────────────────────────────────────────────────────────────────────────────
#  Painter icons from temp.py
# ─────────────────────────────────────────────────────────────────────────────

def _icon_pixmap(kind: str, size=16, color="#A0A8B8") -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    s = size

    if kind == "institution":
        p.drawRect(2, s // 2 - 1, s - 4, s // 2 - 2)
        p.drawLine(2, s // 2 - 4, s - 2, s // 2 - 4)
        p.drawLine(2, 3, s - 2, 3)
        p.drawLine(s // 2, 3, s // 2, s // 2 - 4)
        for x in [4, s // 2, s - 6]:
            p.drawLine(x, s // 2 - 4, x, s // 2 - 1)
    elif kind == "user":
        p.drawEllipse(s // 2 - 3, 2, 6, 6)
        path = QPainterPath()
        path.moveTo(1, s - 2)
        path.cubicTo(1, s // 2 + 2, s - 1, s // 2 + 2, s - 1, s - 2)
        p.drawPath(path)
    elif kind == "mail":
        p.drawRect(2, 4, s - 4, s - 7)
        p.drawLine(2, 5, s // 2, s // 2 + 2)
        p.drawLine(s - 2, 5, s // 2, s // 2 + 2)
    elif kind == "lock":
        p.drawRect(3, s // 2 - 1, s - 6, s // 2 - 1)
        p.drawArc(QRectF(4, 2, s - 8, s // 2 - 1), 0, 180 * 16)
        p.drawEllipse(s // 2 - 1, s // 2 + 2, 3, 3)
    elif kind == "eye":
        path = QPainterPath()
        path.moveTo(2, s // 2)
        path.cubicTo(s // 4, 3, 3 * s // 4, 3, s - 2, s // 2)
        path.cubicTo(3 * s // 4, s - 3, s // 4, s - 3, 2, s // 2)
        p.drawPath(path)
        p.drawEllipse(s // 2 - 2, s // 2 - 2, 4, 4)
    elif kind == "shield":
        path = QPainterPath()
        path.moveTo(s // 2, 2)
        path.lineTo(s - 3, 5)
        path.lineTo(s - 3, s // 2 + 1)
        path.cubicTo(s - 3, s - 2, s // 2, s - 1, s // 2, s - 1)
        path.cubicTo(s // 2, s - 1, 3, s - 2, 3, s // 2 + 1)
        path.lineTo(3, 5)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(s // 2 - 2, s // 2, s // 2, s // 2 + 3)
        p.drawLine(s // 2, s // 2 + 3, s // 2 + 3, s // 2 - 2)
    p.end()
    return px


# ─────────────────────────────────────────────────────────────────────────────
#  Main SignupUI contract from signup_ui.py, restyled with temp.py
# ─────────────────────────────────────────────────────────────────────────────

class SignupUI(QWidget):
    """SEPP light signup UI. Named SignupUI so the controller can import it directly."""

    back_requested = Signal()
    step1_completed = Signal(dict)
    step2_completed = Signal(dict)
    enroll_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step = 1
        self._selected_role = "student"
        self._busy = False
        
        self._step1_data = {}
        self._step2_data = {}

        self._topbar = _TopBar()
        self._card = _SignupCard()
        self._footer = _Footer()
        self._status = QLabel("")
        self._spinner = SpinnerOverlay(self, color="#FFFFFF")

        self._build()
        self._wire()
        self._spinner.hide()
        self._start_threads()

    # ── Public controller contract ──────────────────────────────────────

    def go_to_step2(self, role: str):
        self.current_step = 2
        self._selected_role = role
        self._card.set_step(2)
        self._card.step2.set_role(role)
        self.set_status("", "")

    def go_to_step3(self, summary_data: Optional[dict] = None):
        self.current_step = 3
        self._card.step3.set_summary(summary_data or {})
        self._card.set_step(3)
        self.set_status("", "")

    def go_back(self):
        if self._busy:
            return

        if self.current_step == 3:
            if self._card.step3.has_captured_frame() and not self._confirm_clear_face_photo():
                return
            self._card.step3.reset_camera(stop_camera=True)
            self.current_step = 2
            self._card.set_step(2)
            self.set_status("", "")
            return

        if self.current_step == 2:
            self.current_step = 1
            self._card.set_step(1)
            self.set_status("", "")
            return

        self.back_requested.emit()

    def set_status(self, text: str, state: str):
        colors = {
            "error": RED,
            "success": GREEN,
            "loading": NAVY,
            "warning": AMBER,
            "": T_SECONDARY,
        }
        self._status.setStyleSheet(
            f"font-size: 12px; font-weight: 700; color: {colors.get(state, T_SECONDARY)}; background: transparent;"
        )
        self._status.setText(text)

    def get_captured_frame(self):
        return self._card.step3.get_captured_frame()

    def show_spinner(self):
        self._spinner.setGeometry(self.rect())
        self._spinner.show()
        self._spinner.raise_()
        self.set_busy(True)

    def hide_spinner(self):
        self._spinner.hide()
        self.set_busy(False)

    def set_busy(self, busy: bool):
        self._busy = busy
        self._topbar.setEnabled(not busy)
        self._card.setEnabled(not busy)
        self._footer.setEnabled(not busy)

    def reset(self):
        self.current_step = 1
        self._selected_role = "student"
        self._busy = False
        self._card.reset()
        self._card.set_step(1)
        self.set_status("", "")
        self.hide_spinner()
        self.set_busy(False)

    def prewarm_camera(self):
        # Camera starts only when the user reaches Step 3 and clicks START CAMERA.
        pass

    def shutdown(self) -> None:
        try:
            self._card.step3.reset_camera(stop_camera=True)
        except Exception:
            pass

        lat_thread = getattr(self, "_lat_thread", None)
        if lat_thread is None:
            return
        try:
            lat_thread.stop()
        except Exception:
            pass

    def closeEvent(self, event: QCloseEvent):
        self.shutdown()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._spinner.setGeometry(self.rect())
        
    def _start_threads(self):
        self._lat_thread = LatencyThread()
        self._lat_thread.result.connect(self._on_latency)
        self._lat_thread.start()

    @Slot(int)
    def _on_latency(self, ms: int):
        labels = [
            self._card.step1.latency_lbl,
            self._card.step2.latency_lbl,
            self._card.step3.latency_lbl,
        ]

        if ms < 0:
            text = "Timeout"
            color = RED
        elif ms <= 50:
            text = f"{ms}ms (Optimal)"
            color = GREEN
        elif ms <= 150:
            text = f"{ms}ms (Good)"
            color = AMBER
        else:
            text = f"{ms}ms (Poor)"
            color = RED

        for label in labels:
            label.setText(text)
            label.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{color}; border:none; background:transparent;"
            )

    # ── Internal ────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(f"""
            QWidget#page, SignupUI {{ background: {BG}; font-family: {FONT}; }}
            QLabel {{ background: transparent; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._topbar)

        body = QWidget()
        body.setObjectName("page")

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(40, 24, 40, 18)
        body_layout.setSpacing(0)

        body_layout.addStretch(1)
        body_layout.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)

        self._status.setFixedHeight(28)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_layout.addSpacing(10)
        body_layout.addWidget(self._status)

        body_layout.addStretch(1)

        root.addWidget(body, 1)
        root.addWidget(self._footer)

    def _wire(self):
        self._topbar.back_clicked.connect(self.go_back)
        self._card.step1.completed.connect(self._on_step1_completed)
        self._card.step2.completed.connect(self._on_step2_completed)
        self._card.step2.back_clicked.connect(self.go_back)
        self._card.step3.back_clicked.connect(self.go_back)
        self._card.step3.enroll_requested.connect(self.enroll_requested)

    def _on_step1_completed(self, data: dict):
        self._selected_role = data["role"]

        # Store Step 1 data so it can be used later in Step 3 summary
        self._step1_data = data

        # Move directly to Step 2
        self.go_to_step2(data["role"])

        # Still emit signal for backend/controller compatibility
        self.step1_completed.emit(data)
        
    def _on_step2_completed(self, data: dict):
        # Store Step 2 data
        self._step2_data = data

        # Merge Step 1 + Step 2 data for Step 3 summary
        summary_data = {
            **self._step1_data,
            **self._step2_data,
        }

        # Move directly to Step 3
        self.go_to_step3(summary_data)

        # Still emit signal for backend/controller compatibility
        self.step2_completed.emit(data)
        
    def _confirm_clear_face_photo(self) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("Clear captured photo?")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Going back will clear your captured face photo.")
        box.setInformativeText("You will need to capture your face again before completing registration.")
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        go_back = box.addButton("Go Back", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() == go_back


# ─────────────────────────────────────────────────────────────────────────────
#  Page chrome
# ─────────────────────────────────────────────────────────────────────────────

class _TopBar(QFrame):
    back_clicked = Signal()

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        self.setObjectName("topBar")
        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QFrame#topBar {{
                background: {CARD};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(36, 0, 36, 0)
        row.setSpacing(0)

        self.back_btn = QPushButton("← Back")
        self.back_btn.setFlat(True)
        self.back_btn.setAutoDefault(False)
        self.back_btn.setDefault(False)
        self.back_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                color: {T_SECONDARY};
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
                padding-right: 18px;
                outline: none;
            }}
            QPushButton:hover {{
                color: {NAVY};
                background: transparent;
                border: none;
            }}
            QPushButton:pressed {{
                color: {T_SECONDARY};
                background: transparent;
                border: none;
            }}
            QPushButton:focus {{
                color: {T_SECONDARY};
                background: transparent;
                border: none;
                outline: none;
            }}
        """)
        self.back_btn.clicked.connect(self.back_clicked)

        brand = QLabel("SEPP")
        brand.setStyleSheet(
            f"font-size:17px; font-weight:800; color:{T_PRIMARY}; letter-spacing:1px;"
        )

        sep = QLabel("  |  ")
        sep.setStyleSheet(
            f"color:{BORDER}; font-size:17px;"
        )

        tagline = QLabel("SECURE ENTRANCE PORTAL")
        tagline.setStyleSheet(
            f"font-size:11px; font-weight:500; color:{T_SECONDARY}; letter-spacing:2.5px;"
        )

        row.addWidget(self.back_btn)

        # This pushes SEPP branding to the right side, like login_ui
        row.addStretch()

        row.addWidget(brand)
        row.addWidget(sep)
        row.addWidget(tagline)
        
        row.addSpacing(28)

        # self.datetime_lbl = QLabel()
        # self.datetime_lbl.setStyleSheet(
        #     f"font-size:12px; font-weight:500; color:{T_SECONDARY}; background:transparent; border:none;"
        # )
        # row.addWidget(self.datetime_lbl)

        # self._start_clock()
        
    # def _start_clock(self):
    #     self._clock_timer = QTimer(self)
    #     self._clock_timer.timeout.connect(self._update_clock)
    #     self._clock_timer.start(1000)
    #     self._update_clock()

    # def _update_clock(self):
    #     now = QDateTime.currentDateTime()
    #     self.datetime_lbl.setText(now.toString("ddd, dd MMM yyyy  |  hh:mm AP"))
    # Uncomment the above code to add date and time to the top bar on the right side

# ── Footer  ───────────────────────────────────────────────────────
class _Footer(QFrame):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        
        self.setFixedHeight(46)
        self.setObjectName("footerBar")
        self.setStyleSheet(f"""
            QFrame#footerBar {{
                background: {CARD};
                border-top: 1px solid {BORDER};
            }}
        """)
        
        bar_layout = QHBoxLayout(self)
        bar_layout.setContentsMargins(44, 0, 44, 0)
        bar_layout.setSpacing(0)

        links = [
            (
                "Privacy Policy",
                "This portal collects and processes data strictly for examination integrity purposes. "
                "All data is handled in accordance with applicable privacy regulations."
            ),
            (
                "Terms of Use",
                "By accessing this portal you agree to comply with your institution's examination "
                "rules and the monitoring policies in effect during your session."
            ),
            (
                "Help Center",
                "For technical assistance please contact your institution's IT support team "
                "or email support@sepp.edu."
            ),
        ]

        for i, (label, msg) in enumerate(links):
            lnk = self._link(label)
            lnk.linkActivated.connect(
                lambda _, t=label, m=msg: self._dialog(t, m)
            )
            bar_layout.addWidget(lnk)

            if i < len(links) - 1:
                dot = QLabel("   ·   ")
                dot.setStyleSheet(f"color:{T_SECONDARY}; font-size:12px; background: transparent;")
                bar_layout.addWidget(dot)

        bar_layout.addStretch()

        copy = QLabel("© 2024 SEPP Secure Examination Platform. v2.4.0 Active")
        copy.setStyleSheet(f"font-size:11px; color:{T_SECONDARY}; background: transparent;")
        bar_layout.addWidget(copy)

    def _link(self, text: str) -> QLabel:
        lbl = QLabel(
            f'<a href="#" style="color:{T_SECONDARY}; text-decoration:none; border:none;">{text}</a>'
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        lbl.setOpenExternalLinks(False)
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl.setStyleSheet("""
            QLabel {
                font-size: 12px;
                background: transparent;
                border: none;
            }
        """)
        return lbl
    
    def _dialog(self, title: str, message: str):
        InfoDialog(title, message, parent=self).exec()


# ─────────────────────────────────────────────────────────────────────────────
#  Card container
# ─────────────────────────────────────────────────────────────────────────────

class _SignupCard(QFrame):
    def __init__(self):
        super().__init__()
        self._compact_size = QSize(460, 560)
        self._expanded_size = QSize(940, 650)
        self._size_anim = None
        self.left = _IdentityPanel()
        self.stack = QStackedWidget()
        self.step1 = _Step1Form()
        self.step2 = _Step2Form()
        self.step3 = _Step3ReviewForm()
        self._build()
        self.step3.bind_camera(self.left.camera)

    def _build(self):
        self.setObjectName("signupCard")
        self.setFixedSize(self._compact_size)
        self.setStyleSheet(f"""
            QFrame#signupCard {{
                background: {CARD};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.stack.addWidget(self.step1)
        self.stack.addWidget(self.step2)
        self.stack.addWidget(self.step3)

        layout.addWidget(self.left, 1)
        self.divider = QFrame()
        self.divider.setFixedWidth(1)
        self.divider.setStyleSheet(f"background: {BORDER};")
        layout.addWidget(self.divider)
        layout.addWidget(self.stack, 1)
        
        self.left.hide()
        self.divider.hide()

    def set_step(self, step: int):
        is_step3 = step == 3

        self.left.setVisible(is_step3)
        self.divider.setVisible(is_step3)

        if is_step3:
            self.left.set_step(step)

        self.stack.setCurrentIndex(step - 1)

        target_size = self._expanded_size if is_step3 else self._compact_size
        self._animate_to_size(target_size)

    def _animate_to_size(self, target_size: QSize):
        current = self.size()

        # Pin both constraints to current size RIGHT NOW before Qt processes
        # the layout change from setVisible(), preventing the instant jump
        self.setMinimumSize(current)
        self.setMaximumSize(current)

        if current == target_size:
            return

        self._size_anim = QPropertyAnimation(self, b"minimumSize")
        self._size_anim.setDuration(420)
        self._size_anim.setStartValue(current)
        self._size_anim.setEndValue(target_size)
        self._size_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._max_anim = QPropertyAnimation(self, b"maximumSize")
        self._max_anim.setDuration(420)
        self._max_anim.setStartValue(current)
        self._max_anim.setEndValue(target_size)
        self._max_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._size_anim.start()
        self._max_anim.start()

    def reset(self):
        self.step1.reset()
        self.step2.reset()
        self.step3.reset_all()


class _IdentityPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._step = 1
        self._title = QLabel()
        self._subtitle = QLabel()
        self._visual_stack = QStackedWidget()
        self._dots: list[QLabel] = []
        self.camera = EmbeddedCameraCaptureWidget()
        self._build()
        self.set_step(1)

    def _build(self):
        self.setObjectName("leftPanel")
        self.setStyleSheet(f"""
            QWidget#leftPanel {{
                background: {BG_LEFT};
                border-radius: 14px 0 0 14px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 30)
        layout.setSpacing(14)

        small = QLabel("IDENTITY VERIFICATION")
        small.setStyleSheet(f"color: {T_SECONDARY}; font-size: 10px; font-weight: 700; letter-spacing: 1.8px;")
        layout.addWidget(small)

        self._title.setWordWrap(True)
        self._title.setStyleSheet(f"color: {T_PRIMARY}; font-size: 20px; font-weight: 650;")
        layout.addWidget(self._title)

        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet(f"color: {T_SECONDARY}; font-size: 13px; line-height: 1.5;")
        layout.addWidget(self._subtitle)

        dots_row = QHBoxLayout()
        dots_row.setSpacing(7)
        for _ in range(3):
            dot = QLabel("●")
            dot.setStyleSheet("background: transparent;")
            self._dots.append(dot)
            dots_row.addWidget(dot)
        dots_row.addStretch(1)
        layout.addLayout(dots_row)
        layout.addSpacing(4)

        self._visual_stack.addWidget(QWidget())
        self._visual_stack.addWidget(QWidget())
        self._visual_stack.addWidget(self._camera_visual())
        layout.addWidget(self._visual_stack, stretch=1)
   
    def _camera_visual(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        cam_title = QLabel("Face Capture")
        cam_title.setStyleSheet(f"color:{T_PRIMARY}; font-size:16px; font-weight:700;")
        cam_sub = QLabel("Use a well-lit front-facing photo. Only you should be visible in the frame.")
        cam_sub.setWordWrap(True)
        cam_sub.setStyleSheet(f"color:{T_SECONDARY}; font-size:12px;")
        lay.addWidget(cam_title)
        lay.addWidget(cam_sub)
        lay.addWidget(self.camera, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addStretch(1)
        return wrap

    def set_step(self, step: int):
        self._step = step
        data = {
            1: ("Create your secure account", "Enter your personal details and select the role that applies to you."),
            2: ("Connect your academic profile", "Select your institution and department before face enrollment."),
            3: ("Capture your enrollment photo", "Start the camera, capture a clear photo, and review your details before submitting."),
        }
        title, subtitle = data.get(step, data[1])
        self._title.setText(title)
        self._subtitle.setText(subtitle)
        self._visual_stack.setCurrentIndex(step - 1)
        for i, dot in enumerate(self._dots):
            dot.setStyleSheet(
                f"font-size: 13px; color: {NAVY if i == step - 1 else '#CBD2DE'}; background: transparent;"
            )


# class HardwareStatus(QFrame):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setObjectName("hwStatus")
#         self.setFixedHeight(64)
#         self.setStyleSheet(f"""
#             QFrame#hwStatus {{
#                 background: #FFFFFF;
#                 border: 1px solid {BORDER};
#                 border-radius: 8px;
#             }}
#         """)
#         lay = QHBoxLayout(self)
#         lay.setContentsMargins(14, 0, 14, 0)
#         lay.setSpacing(0)

#         left_lay = QVBoxLayout()
#         left_lay.setSpacing(2)
#         hw_lbl = QLabel("HARDWARE STATUS")
#         hw_lbl.setStyleSheet(f"color:{T_SECONDARY}; font-size:10px; font-weight:600; letter-spacing:1px;")
#         left_lay.addWidget(hw_lbl)
#         left_lay.addStretch()
#         lay.addLayout(left_lay)
#         lay.addStretch()

#         ready_lay = QHBoxLayout()
#         ready_lay.setSpacing(5)
#         dot = QLabel("●")
#         dot.setStyleSheet(f"color:{GREEN}; font-size:10px;")
#         ready_lay.addWidget(dot)
#         ready_txt = QLabel("SYSTEM READY")
#         ready_txt.setStyleSheet(f"color:{GREEN}; font-size:10px; font-weight:600; letter-spacing:0.8px;")
#         ready_lay.addWidget(ready_txt)

#         top_right = QHBoxLayout()
#         top_right.addStretch()
#         top_right.addLayout(ready_lay)

#         devices = QHBoxLayout()
#         devices.setSpacing(22)
#         devices.addLayout(self._device_widget("□", "Camera", "Ready", GREEN))
#         devices.addLayout(self._device_widget("🎙", "Microphone", "Active", GREEN))

#         right_col = QVBoxLayout()
#         right_col.setSpacing(4)
#         right_col.addLayout(top_right)
#         right_col.addLayout(devices)
#         lay.addLayout(right_col)

#     def _device_widget(self, icon_ch, name, status, col):
#         lay = QHBoxLayout()
#         lay.setSpacing(6)
#         icon_lbl = QLabel(icon_ch)
#         icon_lbl.setStyleSheet(f"color:{T_SECONDARY}; font-size:14px;")
#         lay.addWidget(icon_lbl)
#         info = QVBoxLayout()
#         info.setSpacing(0)
#         n = QLabel(name)
#         n.setStyleSheet(f"color:{T_PRIMARY}; font-size:12px; font-weight:500;")
#         s = QLabel(status)
#         s.setStyleSheet(f"color:{col}; font-size:11px;")
#         info.addWidget(n)
#         info.addWidget(s)
#         lay.addLayout(info)
#         return lay


# ─────────────────────────────────────────────────────────────────────────────
#  Form widgets
# ─────────────────────────────────────────────────────────────────────────────

class _Step1Form(QWidget):
    completed = Signal(dict)

    def __init__(self):
        super().__init__()
        self._selected_role = "student"
        self._first = QLineEdit()
        self._last = QLineEdit()
        self._email = QLineEdit()
        self._pwd_container = QFrame()
        self._pwd2_container = QFrame()
        self._pwd = QLineEdit()
        self._pwd2 = QLineEdit()
        self._err = QLabel("")
        self._student = _RolePill("Student", "student")
        self._examiner = _RolePill("Examiner", "examiner")
        self.latency_lbl = QLabel("Measuring…")
        self._build()

    def _build(self):
        layout = _form_layout(self)
        _add_heading(layout, "Sign Up", "Step 1 of 3 — Personal information")

        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        self._first = _input("First name", "user")
        self._last = _input("Last name", "user")
        name_row.addWidget(self._first)
        name_row.addWidget(self._last)
        layout.addLayout(name_row)
        layout.addSpacing(12)

        self._email = _input("Email address", "mail")
        layout.addWidget(self._email)
        layout.addSpacing(12)

        self._pwd_container, self._pwd = _password_input("Password")
        self._pwd2_container, self._pwd2 = _password_input("Confirm password")

        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(12)
        pwd_row.addWidget(self._pwd_container)
        pwd_row.addWidget(self._pwd2_container)

        layout.addLayout(pwd_row)
        layout.addSpacing(18)

        layout.addWidget(_label("Select your role"))
        layout.addSpacing(8)

        self._student.set_selected(True)
        self._student.clicked.connect(lambda: self._select_role("student"))
        self._examiner.clicked.connect(lambda: self._select_role("examiner"))
        role_row = QHBoxLayout()
        role_row.setSpacing(12)
        role_row.addWidget(self._student)
        role_row.addWidget(self._examiner)
        role_row.addStretch(1)
        layout.addLayout(role_row)
        layout.addSpacing(10)

        self._err = _error_label()
        layout.addWidget(self._err)
        layout.addSpacing(8)

        next_btn = _primary_button("NEXT →")
        next_btn.clicked.connect(self._on_next)
        layout.addWidget(next_btn)
        layout.addStretch(1)

        info_block, self.latency_lbl = _security_info_block()
        layout.addWidget(info_block)

    def _select_role(self, role: str):
        self._selected_role = role
        self._student.set_selected(role == "student")
        self._examiner.set_selected(role == "examiner")

    def _on_next(self):
        first = self._first.text().strip()
        last = self._last.text().strip()
        email = self._email.text().strip()
        pwd = self._pwd.text()
        pwd2 = self._pwd2.text()

        if not first or not last:
            self._err.setText("Please enter your first and last name.")
            return
        if not email or "@" not in email:
            self._err.setText("Please enter a valid email address.")
            return
        if len(pwd) < 6:
            self._err.setText("Password must be at least 6 characters.")
            return
        if pwd != pwd2:
            self._err.setText("Passwords do not match.")
            return

        self._err.setText("")
        self.completed.emit({
            "first_name": first,
            "last_name": last,
            "email": email,
            "password": pwd,
            "role": self._selected_role,
        })

    def reset(self):
        self._first.clear()
        self._last.clear()
        self._email.clear()
        self._pwd.clear()
        self._pwd2.clear()
        self._err.setText("")
        self._select_role("student")


class _Step2Form(QWidget):
    completed = Signal(dict)
    back_clicked = Signal()

    def __init__(self):
        super().__init__()
        self._role = "student"
        self._heading = QLabel("Student Details")
        self._institution = QComboBox()
        self._department = QComboBox()
        self._err = QLabel("")
        self.latency_lbl = QLabel("Measuring…")
        self._build()

    def set_role(self, role: str):
        self._role = role
        self._heading.setText("Examiner Details" if role == "examiner" else "Student Details")

    def _build(self):
        layout = _form_layout(self)
        self._heading.setStyleSheet(f"color: {T_PRIMARY}; font-size: 26px; font-weight: 700;")
        layout.addWidget(self._heading)
        sub = QLabel("Step 2 of 3 — Role information")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {T_SECONDARY}; font-size: 13px;")
        layout.addWidget(sub)
        layout.addSpacing(28)

        self._institution = _combo(INSTITUTIONS)
        self._department = _combo(DEPARTMENTS)

        layout.addWidget(_label("Institution"))
        layout.addSpacing(7)
        layout.addWidget(self._institution)
        layout.addSpacing(18)
        layout.addWidget(_label("Department"))
        layout.addSpacing(7)
        layout.addWidget(self._department)
        layout.addSpacing(18)

        self._err = _error_label()
        layout.addWidget(self._err)
        layout.addSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(12)
        back = _secondary_button("← BACK")
        next_btn = _primary_button("NEXT →")
        back.clicked.connect(self.back_clicked)
        next_btn.clicked.connect(self._on_next)
        row.addWidget(back)
        row.addWidget(next_btn)
        layout.addLayout(row)
        layout.addStretch(1)

        info_block, self.latency_lbl = _security_info_block()
        layout.addWidget(info_block)

    def _on_next(self):
        self._err.setText("")
        self.completed.emit({
            "institution": self._institution.currentText(),
            "department": self._department.currentText(),
        })

    def reset(self):
        self._institution.setCurrentIndex(0)
        self._department.setCurrentIndex(0)
        self._err.setText("")
        self.set_role("student")


class _Step3ReviewForm(QWidget):
    enroll_requested = Signal()
    back_clicked = Signal()

    def __init__(self):
        super().__init__()
        self._summary: dict = {}
        self._complete_btn = QPushButton()
        self._err = QLabel("")
        self._camera: Optional[EmbeddedCameraCaptureWidget] = None
        self.latency_lbl = QLabel("Measuring…")
        # Fields assigned in _build():
        # self._first, self._last, self._email,
        # self._role_student, self._role_examiner,
        # self._institution, self._department, self._agreement
        self._build()

    def bind_camera(self, camera: EmbeddedCameraCaptureWidget):
        self._camera = camera
        self._camera.frame_captured.connect(self._on_frame_captured)
        self._camera.frame_cleared.connect(self._on_frame_cleared)

    def get_captured_frame(self):
        return self._camera.get_captured_frame() if self._camera else None

    def has_captured_frame(self) -> bool:
        return bool(self._camera and self._camera.has_captured_frame())

    def reset_camera(self, stop_camera: bool = True):
        if self._camera:
            if stop_camera:
                self._camera.stop(clear_preview=True)
            else:
                self._camera.reset_capture()
        self._agreement.setChecked(False)
        self._update_complete_state()

    def reset_all(self):
        self._summary = {}
        self.reset_camera(stop_camera=True)
        self._err.setText("")

    def set_summary(self, data: dict):
        self._summary = data or {}

        self._first.setText(data.get("first_name", ""))
        self._last.setText(data.get("last_name", ""))
        self._email.setText(data.get("email", ""))

        self._role_display.setText(data.get("role", "").title())

        inst_idx = self._institution.findText(data.get("institution", ""))
        if inst_idx >= 0:
            self._institution.setCurrentIndex(inst_idx)

        dept_idx = self._department.findText(data.get("department", ""))
        if dept_idx >= 0:
            self._department.setCurrentIndex(dept_idx)

        self._agreement.setChecked(False)
        self._err.setText("")
        self._update_complete_state()

    def     _build(self):
        layout = _form_layout(self)
        layout.setContentsMargins(36, 22, 36, 18)
        _add_heading(layout, "Review & Enroll", "Step 3 of 3 — Confirm details and complete face enrollment")
        layout.addSpacing(-16)
        
        # ── Greyed-out field stylesheets ────────────────────────────────
        grey_input_ss = f"""
            QLineEdit {{
                border: 1.5px solid {BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
                color: {T_SECONDARY};
                background: #F3F4F6;
            }}
            QLineEdit:disabled {{
                color: {T_SECONDARY};
                background: #F3F4F6;
                border-color: {BORDER};
            }}
        """
        grey_combo_ss = f"""
            QComboBox {{
                background: #F3F4F6;
                color: {T_SECONDARY};
                border: 1.5px solid {BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 14px;
            }}
            QComboBox:disabled {{
                color: {T_SECONDARY};
                background: #F3F4F6;
                border-color: {BORDER};
            }}
            QComboBox::drop-down {{ border: none; width: 30px; }}
            QComboBox QAbstractItemView {{
                background: white;
                color: {T_PRIMARY};
                border: 1px solid {BORDER};
            }}
        """

        # ── Full Name ────────────────────────────────────────────────────
        layout.addWidget(_label("Full Name"))
        layout.addSpacing(6)
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        self._first = _input("First name", "user")
        self._last = _input("Last name", "user")
        self._first.setEnabled(False)
        self._last.setEnabled(False)
        self._first.setStyleSheet(grey_input_ss)
        self._last.setStyleSheet(grey_input_ss)
        name_row.addWidget(self._first)
        name_row.addWidget(self._last)
        layout.addLayout(name_row)
        layout.addSpacing(10)

        # ── Email ────────────────────────────────────────────────────────
        layout.addWidget(_label("Email"))
        layout.addSpacing(6)
        self._email = _input("Email address", "mail")
        self._email.setEnabled(False)
        self._email.setStyleSheet(grey_input_ss)
        layout.addWidget(self._email)
        layout.addSpacing(10)

        # ── Role ─────────────────────────────────────────────────────────
        layout.addWidget(_label("Role"))
        layout.addSpacing(7)
        self._role_display = QLineEdit()
        self._role_display.setFixedHeight(46)
        self._role_display.setReadOnly(True)
        self._role_display.setStyleSheet(grey_input_ss)
        layout.addWidget(self._role_display)
        layout.addSpacing(10)

        # ── Institution ──────────────────────────────────────────────────
        layout.addWidget(_label("Institution"))
        layout.addSpacing(6)
        self._institution = _combo(INSTITUTIONS)
        self._institution.setEnabled(False)
        self._institution.setStyleSheet(grey_combo_ss)
        layout.addWidget(self._institution)
        layout.addSpacing(10)

        # ── Department ───────────────────────────────────────────────────
        layout.addWidget(_label("Department"))
        layout.addSpacing(6)
        self._department = _combo(DEPARTMENTS)
        self._department.setEnabled(False)
        self._department.setStyleSheet(grey_combo_ss)
        layout.addWidget(self._department)
        layout.addSpacing(10)

        # ── Agreement ────────────────────────────────────────────────────
        agreement_row = QWidget()
        agreement_layout = QHBoxLayout(agreement_row)
        agreement_layout.setContentsMargins(0, 0, 0, 0)
        agreement_layout.setSpacing(8)
        self._agreement = QCheckBox()
        self._agreement.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._agreement.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 1.5px solid {BORDER};
                border-radius: 4px;
                background: {BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                background: {NAVY};
                border-color: {NAVY};
            }}
        """)
        agreement_text = QLabel("I agree to biometric verification and examination monitoring policies.")
        agreement_text.setWordWrap(True)
        agreement_text.setStyleSheet(f"color:{T_SECONDARY}; font-size:13px;")
        agreement_layout.addWidget(self._agreement, 0, Qt.AlignmentFlag.AlignTop)
        agreement_layout.addWidget(agreement_text, 1)
        self._agreement.stateChanged.connect(self._update_complete_state)
        layout.addWidget(agreement_row)
        layout.addSpacing(10)

        # ── Error / buttons ──────────────────────────────────────────────
        self._err = _error_label()
        layout.addWidget(self._err)
        layout.addSpacing(8)

        self._complete_btn = _primary_button("COMPLETE REGISTRATION →")
        self._complete_btn.clicked.connect(self._on_complete)
        layout.addWidget(self._complete_btn)
        layout.addSpacing(14)

        # ── Security info (latency label used by latency thread) ─────────
        self.latency_lbl = QLabel()   # satisfies the latency thread reference, not shown
        self.latency_lbl.hide()

        self._update_complete_state()

    def _on_frame_captured(self, frame):
        self._err.setText("")
        self._update_complete_state()

    def _on_frame_cleared(self):
        self._update_complete_state()

    def _on_complete(self):
        if not self.has_captured_frame():
            self._err.setText("Please capture your face photo first.")
            return
        if not self._agreement.isChecked():
            self._err.setText("Please accept the biometric verification agreement.")
            return
        self._err.setText("")
        self.enroll_requested.emit()

    def _update_complete_state(self):
        ready = self.has_captured_frame() and self._agreement.isChecked()
        self._complete_btn.setEnabled(ready)


# ─────────────────────────────────────────────────────────────────────────────
#  Shared controls / Helper
# ─────────────────────────────────────────────────────────────────────────────

def _form_layout(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(36, 36, 36, 30)
    layout.setSpacing(0)
    return layout


def _add_heading(layout: QVBoxLayout, title: str, subtitle: str):
    heading = QLabel(title)
    heading.setStyleSheet(f"color: {T_PRIMARY}; font-size: 26px; font-weight: 700;")
    layout.addWidget(heading)
    sub = QLabel(subtitle)
    sub.setWordWrap(True)
    sub.setStyleSheet(f"color: {T_SECONDARY}; font-size: 13px;")
    layout.addSpacing(4)
    layout.addWidget(sub)
    layout.addSpacing(26)


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size:13px; font-weight:600; color:{T_PRIMARY}; border:none; background:transparent;"
    )
    return lbl


def _input(placeholder: str, icon_kind: str = "user", password: bool = False) -> QLineEdit:
    field = QLineEdit()
    field.setPlaceholderText(placeholder)
    field.setFixedHeight(46)
    field.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    field.setStyleSheet(f"""
        QLineEdit {{
            border: 1.5px solid {INP_BORDER};
            border-radius: 8px;
            padding: 0 14px;
            font-size: 14px;
            color: {T_PRIMARY};
            background: white;
        }}
        QLineEdit:focus {{
            border-color: {INP_FOCUS};
        }}
        QLineEdit::placeholder {{
            color: {T_SECONDARY};
        }}
    """)

    field.addAction(
        QIcon(_icon_pixmap(icon_kind, 17, T_SECONDARY)),
        QLineEdit.ActionPosition.LeadingPosition
    )

    if password:
        field.setEchoMode(QLineEdit.EchoMode.Password)

        toggle = QAction(QIcon(_icon_pixmap("eye", 17, T_SECONDARY)), "", field)
        toggle.setCheckable(True)
        toggle.triggered.connect(
            lambda checked, f=field: f.setEchoMode(
                QLineEdit.EchoMode.Normal
                if checked
                else QLineEdit.EchoMode.Password
            )
        )
        field.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)

    return field

# ─────────────────────────────────────────────────────────────────────────────
#  Dropdown Menu
# ─────────────────────────────────────────────────────────────────────────────
def _combo(items: list[str]) -> QComboBox:
    combo = QComboBox()
    combo.addItems(items)
    combo.setFixedHeight(46)

    combo.setStyleSheet(f"""
        QComboBox {{
            background: white;
            color: {T_PRIMARY};
            border: 1.5px solid {INP_BORDER};
            border-radius: 8px;
            padding: 0 14px;
            font-size: 14px;
        }}
        QComboBox:focus {{
            border-color: {INP_FOCUS};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 30px;
        }}
        QComboBox QAbstractItemView {{
            background: white;
            color: {T_PRIMARY};
            border: 1px solid {BORDER};
            selection-background-color: {NAVY};
            selection-color: white;
        }}
    """)

    return combo


def _error_label() -> QLabel:
    lbl = QLabel("")
    lbl.setFixedHeight(28)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"font-size:12px; color:{RED}; border:none; background:transparent;"
    )
    return lbl


def _primary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(50)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setAutoDefault(False)
    btn.setDefault(False)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    btn.setStyleSheet(f"""
        QPushButton {{
            background: {NAVY};
            color: #FFFFFF;
            border: none;
            border-radius: 9px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.6px;
            outline: none;
        }}
        QPushButton:hover {{
            background: #1c3461;
        }}
        QPushButton:pressed {{
            background: #091529;
        }}
        QPushButton:focus {{
            background: {NAVY};
            color: #FFFFFF;
            border: none;
            outline: none;
        }}
        QPushButton:disabled {{
            background: #9CA3AF;
            color: #EEF2F7;
        }}
    """)

    return btn


def _secondary_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(50)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setAutoDefault(False)
    btn.setDefault(False)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    btn.setStyleSheet(f"""
        QPushButton {{
            background: white;
            color: {T_SECONDARY};
            border: 1.5px solid {INP_BORDER};
            border-radius: 9px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.6px;
            outline: none;
        }}
        QPushButton:hover {{
            color: {NAVY};
            border-color: {NAVY};
            background: white;
        }}
        QPushButton:pressed {{
            color: {T_SECONDARY};
            border-color: {INP_BORDER};
            background: white;
        }}
        QPushButton:focus {{
            color: {T_SECONDARY};
            border-color: {INP_BORDER};
            background: white;
            outline: none;
        }}
        QPushButton:disabled {{
            color: #AEB6C4;
            border-color: {BORDER};
            background: white;
        }}
    """)

    return btn


def _info_row(label: str, value: str, value_color: str) -> QWidget:
    row = QWidget()
    rlay = QHBoxLayout(row)
    rlay.setContentsMargins(0, 0, 0, 0)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color:{T_SECONDARY}; font-size:13px;")
    val = QLabel(value)
    val.setStyleSheet(f"color:{value_color}; font-size:13px; font-weight:600;")
    rlay.addWidget(lbl)
    rlay.addStretch()
    rlay.addWidget(val)
    return row

def _security_info_block() -> tuple[QWidget, QLabel]:
    block = QWidget()
    lay = QVBoxLayout(block)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)

    latency_row = QWidget()
    lat_lay = QHBoxLayout(latency_row)
    lat_lay.setContentsMargins(0, 0, 0, 0)

    lat_label = QLabel("System Latency")
    lat_label.setStyleSheet(
        f"font-size:13px; color:{T_SECONDARY}; border:none; background:transparent;"
    )

    latency_value = QLabel("Measuring…")
    latency_value.setStyleSheet(
        f"font-size:13px; font-weight:600; color:{GREEN}; border:none; background:transparent;"
    )

    lat_lay.addWidget(lat_label)
    lat_lay.addStretch()
    lat_lay.addWidget(latency_value)

    lay.addWidget(latency_row)
    lay.addWidget(_info_row("Security Protocol", "AES-256 Encrypted", AMBER))

    return block, latency_value


class _RolePill(QFrame):
    clicked = Signal()

    def __init__(self, label: str, role: str):
        super().__init__()
        self.role = role
        self._selected = False
        self._label = QLabel(label)
        self._build()

    def _build(self):
        self.setObjectName("rolePill")
        self.setFixedHeight(52)
        self.setMinimumWidth(130)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        layout.addWidget(self._label)
        self._apply_style()

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(f"""
                QFrame#rolePill {{
                    background: {NAVY};
                    border: 1px solid {NAVY};
                    border-radius: 9px;
                }}
            """)
            self._label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 13px;
                    font-weight: 700;
                    background: transparent;
                    border: none;
                }
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#rolePill {{
                    background: white;
                    border: 1.5px solid {INP_BORDER};
                    border-radius: 9px;
                }}
            """)
            self._label.setStyleSheet(f"""
                QLabel {{
                    color: {T_SECONDARY};
                    font-size: 13px;
                    font-weight: 600;
                    background: transparent;
                    border: none;
                }}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

def _password_input(placeholder: str = "••••••••") -> tuple[QFrame, QLineEdit]:
    container = QFrame()
    container.setFixedHeight(46)
    container.setStyleSheet(f"""
        QFrame {{
            border: 1.5px solid {INP_BORDER};
            border-radius: 8px;
            background: white;
        }}
    """)

    row = QHBoxLayout(container)
    row.setContentsMargins(14, 0, 8, 0)
    row.setSpacing(4)

    lock = QLabel()
    lock.setPixmap(_icon_pixmap("lock", 17, T_SECONDARY))
    lock.setFixedSize(20, 20)
    lock.setStyleSheet("background: transparent; border: none;")
    row.addWidget(lock)

    pw = QLineEdit()
    pw.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    pw.setEchoMode(QLineEdit.EchoMode.Password)
    pw.setPlaceholderText(placeholder)
    pw.setStyleSheet(f"""
        QLineEdit {{
            border: none;
            background: transparent;
            font-size: 14px;
            color: {T_PRIMARY};
        }}
        QLineEdit::placeholder {{
            color: {T_SECONDARY};
        }}
    """)
    row.addWidget(pw, stretch=1)

    eye = QPushButton()
    eye.setIcon(QIcon(_icon_pixmap("eye", 17, T_SECONDARY)))
    eye.setIconSize(QSize(17, 17))
    eye.setFixedSize(34, 34)
    eye.setCheckable(True)
    eye.setAutoDefault(False)
    eye.setDefault(False)
    eye.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    eye.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    eye.setStyleSheet("""
        QPushButton {
            border: none;
            background: transparent;
            font-size: 16px;
            outline: none;
        }
        QPushButton:hover {
            background: #F3F4F6;
            border-radius: 5px;
        }
        QPushButton:pressed {
            background: transparent;
            border: none;
        }
        QPushButton:focus {
            background: transparent;
            border: none;
            outline: none;
        }
        QPushButton:checked {
            background: transparent;
            border: none;
        }
    """)

    eye.toggled.connect(
        lambda on: pw.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
        )
    )

    row.addWidget(eye)

    return container, pw


# ─────────────────────────────────────────────────────────────────────────────
#  Standalone preview entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    win = SignupUI()
    win.resize(1120, 900)
    win.show()
    sys.exit(app.exec())
