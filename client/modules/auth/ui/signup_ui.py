"""
client/modules/auth/ui/signup_ui.py
Multi-step signup UI — fullscreen, white/blue diagonal split.
Back button and progress dots on LEFT panel.
Full-screen spinner overlay covers entire window during loading.
"""

import cv2
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QComboBox,
    QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QPixmap, QImage, QAction, QCloseEvent,
)
from client.modules.common.diagonal_background import DiagonalBackground
from client.modules.common.design_tokens import (
    COLOR_BRAND_DARK,
    COLOR_BRAND_MID,
    COLOR_BG_CARD,
    COLOR_BG_SOFT,
    COLOR_BORDER_SOFT,
    COLOR_DOT_INACTIVE,
    COLOR_ERROR,
    COLOR_INPUT_BORDER,
    COLOR_INPUT_FOCUS,
    COLOR_PRIMARY,
    COLOR_PRIMARY_ALT,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_BTN,
    COLOR_SUCCESS_BTN_HOVER,
    COLOR_SUCCESS_BTN_PRESSED,
    COLOR_TEXT_DARK,
    COLOR_TEXT_HEAD,
    COLOR_TEXT_LIGHT,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SUBTLE,
    FONT_FAMILY,
    FORM_WIDTH,
)
from client.modules.common.loading_spinner import SpinnerOverlay
from client.modules.auth.ui.camera_preview import CameraPreviewWidget

INSTITUTIONS = ["Air University"]
DEPARTMENTS  = ["NCSA"]


class SignupUI(QWidget):

    back_requested  = Signal()
    step1_completed = Signal(dict)
    step2_completed = Signal(dict)
    enroll_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step   = 1
        self._selected_role = "student"

        self._bg    = DiagonalBackground(self)
        self._left  = _LeftPanel(self)
        self._right = _RightPanel(self)

        # Full-screen spinner — sits on top of everything
        self._spinner = SpinnerOverlay(self, color="#FFFFFF")

        self._bg.lower()
        self._left.back_requested.connect(self.back_requested)
        self._right.step1_completed.connect(self._on_step1)
        self._right.step2_completed.connect(self.step2_completed)
        self._right.enroll_requested.connect(self.enroll_requested)
        self._layout_panels()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_panels()
        # Keep spinner covering full widget
        self._spinner.setGeometry(self.rect())

    def _layout_panels(self):
        w      = self.width()
        h      = self.height()
        left_w = int(w * 0.42)
        self._bg.setGeometry(0, 0, w, h)
        self._left.setGeometry(0, 0, left_w, h)
        self._right.setGeometry(left_w, 0, w - left_w, h)

    def _on_step1(self, data: dict):
        self._selected_role = data["role"]
        self.step1_completed.emit(data)

    def go_to_step2(self, role: str):
        self.current_step = 2
        self._left.update_dots(2)
        self._right.show_step2(role)

    def go_to_step3(self):
        self.current_step = 3
        self._left.update_dots(3)
        self._right.show_step3()

    def go_back(self):
        if self.current_step == 2:
            self.current_step = 1
            self._left.update_dots(1)
            self._right.show_step1()
        elif self.current_step == 3:
            self.current_step = 2
            self._left.update_dots(2)
            self._right.show_step2(self._selected_role)

    def set_status(self, text: str, state: str):
        self._right.set_status(text, state)

    def get_captured_frame(self):
        return self._right._step3_widget.get_captured_frame()

    # ── Full-screen spinner ────────────────────────────────────────────────

    def show_spinner(self):
        self._spinner.setGeometry(self.rect())
        self._spinner.show()
        self._spinner.raise_()

    def hide_spinner(self):
        self._spinner.hide()
        
    # ── Full-screen spinner ────────────────────────────────────────────────

    def reset(self):
        self.current_step   = 1
        self._selected_role = "student"
        self._left.update_dots(1)
        self._right._step3_widget.stop_camera()
        self._right._stack.setCurrentIndex(0)
        self._right._status.setText("")
        self._right._step1_widget.reset()   # ← clears all step 1 fields
        self._right._step2_widget.reset()   # ← resets combos
        self.hide_spinner()

    def prewarm_camera(self):
        self._right.prewarm_camera()

    def closeEvent(self, event: QCloseEvent):
        try:
            self._right._step3_widget.stop_camera()
        except Exception:
            pass
        super().closeEvent(event)
    
# ── Left panel ─────────────────────────────────────────────────────────────

class _LeftPanel(QWidget):

    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._dots:     list[QLabel] = []
        self._back_btn = QPushButton()
        self._build()

    def update_dots(self, step: int):
        for i, dot in enumerate(self._dots):
            active = (i == step - 1)
            dot.setStyleSheet(
                f"font-size: 10px; "
                f"color: {COLOR_PRIMARY_ALT if active else COLOR_DOT_INACTIVE}; "
                "background: transparent;"
            )

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        back_row = QHBoxLayout()
        back_row.setContentsMargins(32, 24, 0, 0)
        self._back_btn = QPushButton("← BACK")
        self._back_btn.setFlat(True)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12px; font-weight: 700;
                color: {COLOR_PRIMARY_ALT}; background: transparent;
                border: none; letter-spacing: 1px; padding: 0;
            }}
            QPushButton:hover {{ color: {COLOR_PRIMARY_DARK}; }}
        """)
        self._back_btn.clicked.connect(self.back_requested)
        back_row.addWidget(self._back_btn)
        back_row.addStretch()
        layout.addLayout(back_row)

        dots_row = QHBoxLayout()
        dots_row.setContentsMargins(32, 8, 0, 0)
        dots_row.setSpacing(8)
        for i in range(3):
            dot = QLabel("●")
            dot.setStyleSheet(
                f"font-size: 10px; "
                f"color: {COLOR_PRIMARY_ALT if i == 0 else COLOR_DOT_INACTIVE}; "
                "background: transparent;"
            )
            self._dots.append(dot)
            dots_row.addWidget(dot)
        dots_row.addStretch()
        layout.addLayout(dots_row)

        layout.addStretch(3)

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner = QVBoxLayout(content)
        inner.setContentsMargins(72, 0, 40, 0)
        inner.setSpacing(10)

        logo = QLabel("✦")
        logo.setStyleSheet(
            f"font-size: 52px; color: {COLOR_PRIMARY_ALT}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        inner.addWidget(logo)

        name = QLabel("ExamApp")
        name.setStyleSheet(
            f"font-size: 36px; font-weight: 800; color: {COLOR_BRAND_DARK}; "
            f"font-family: {FONT_FAMILY}; "
            "letter-spacing: 3px; background: transparent;"
        )
        inner.addWidget(name)

        tag = QLabel("Create your account\nand get started.")
        tag.setStyleSheet(
            f"font-size: 14px; color: {COLOR_BRAND_MID}; "
            f"font-family: {FONT_FAMILY}; line-height: 1.7; background: transparent;"
        )
        inner.addWidget(tag)
        layout.addWidget(content)
        layout.addStretch(4)

        footer_w = QWidget()
        footer_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        fl = QHBoxLayout(footer_w)
        fl.setContentsMargins(72, 0, 0, 32)
        footer = QLabel("CS-305 Software Engineering  ·  v1.0.0")
        footer.setStyleSheet(
            f"font-size: 10px; color: {COLOR_TEXT_SUBTLE}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        fl.addWidget(footer)
        fl.addStretch()
        layout.addWidget(footer_w)


# ── Right panel ─────────────────────────────────────────────────────────────

class _RightPanel(QWidget):

    step1_completed  = Signal(dict)
    step2_completed  = Signal(dict)
    enroll_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._stack        = QStackedWidget()
        self._status       = QLabel("")
        self._step1_widget = _Step1Widget()
        self._step2_widget = _Step2Widget()
        self._step3_widget = _Step3Widget()
        self._build()
        self._step_spinner = SpinnerOverlay(parent=self._stack)

    def _fade_to(self, index: int):
        self._step_spinner.show()
        QTimer.singleShot(0, lambda: self._stack.setCurrentIndex(index))
        QTimer.singleShot(80, self._step_spinner.hide)

    def show_step1(self):
        self._fade_to(0)
        self._status.setText("")

    def show_step2(self, role: str):
        self._step2_widget.set_role(role)
        self._fade_to(1)
        self._status.setText("")

    def show_step3(self):
        self._fade_to(2)
        self._status.setText("")
        self._step3_widget.prewarm_camera()

    def prewarm_camera(self):
        self._step3_widget.prewarm_camera()

    def set_status(self, text: str, state: str):
        colors = {
            "error":   COLOR_ERROR,
            "success": COLOR_SUCCESS,
            "loading": COLOR_TEXT_LIGHT,
            "":        "#E0E8FF",
        }
        self._status.setStyleSheet(
            f"font-size: 11px; color: {colors.get(state, COLOR_TEXT_LIGHT)}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        self._status.setText(text)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._stack.addWidget(self._step1_widget)
        self._stack.addWidget(self._step2_widget)
        self._stack.addWidget(self._step3_widget)

        self._step1_widget.completed.connect(self.step1_completed)
        self._step2_widget.completed.connect(self.step2_completed)
        self._step3_widget.enroll_requested.connect(self.enroll_requested)

        layout.addWidget(self._stack, stretch=1)

        self._status.setFixedHeight(22)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"font-size: 11px; color: {COLOR_TEXT_LIGHT}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(self._status)
        layout.addSpacing(12)


# ── Step 1 ─────────────────────────────────────────────────────────────────

class _Step1Widget(QWidget):

    completed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._selected_role = "student"
        self._first         = QLineEdit()
        self._last          = QLineEdit()
        self._email         = QLineEdit()
        self._pwd           = QLineEdit()
        self._pwd2          = QLineEdit()
        self._err           = QLabel("")
        self._next_btn      = QPushButton("NEXT →")
        self._student_card  = _RoleCard("👨‍🎓", "Student",  "student")
        self._examiner_card = _RoleCard("👨‍🏫", "Examiner", "examiner")
        self._build()

    def _make_input(self, placeholder: str, password: bool = False) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(40)
        field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_BG_CARD}; color: {COLOR_TEXT_DARK};
                border: 1.5px solid {COLOR_INPUT_BORDER}; border-radius: 4px;
                padding: 0 12px; font-size: 12px;
                font-family: {FONT_FAMILY};
            }}
            QLineEdit:focus {{ border: 1.5px solid {COLOR_INPUT_FOCUS}; }}
        """)
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            toggle = QAction("👁", field)
            toggle.setCheckable(True)
            toggle.triggered.connect(
                lambda checked, f=field: f.setEchoMode(
                    QLineEdit.EchoMode.Normal if checked
                    else QLineEdit.EchoMode.Password
                )
            )
            field.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)
        return field

    def _select_role(self, role: str):
        self._selected_role = role
        self._student_card.set_selected(role == "student")
        self._examiner_card.set_selected(role == "examiner")

    def _on_next(self):
        first = self._first.text().strip()
        last  = self._last.text().strip()
        email = self._email.text().strip()
        pwd   = self._pwd.text()
        pwd2  = self._pwd2.text()

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
            "last_name":  last,
            "email":      email,
            "password":   pwd,
            "role":       self._selected_role,
        })
    
    def reset(self):
        self._first.clear()
        self._last.clear()
        self._email.clear()
        self._pwd.clear()
        self._pwd2.clear()
        self._err.setText("")
        self._select_role("student")

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        inner_widget = QWidget()
        inner_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner_widget.setFixedWidth(FORM_WIDTH)
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        heading = QLabel("Create Account")
        heading.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: #FFFFFF; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(heading)
        layout.addSpacing(4)

        sub = QLabel("Step 1 of 3 — Personal Information")
        sub.setStyleSheet(
            f"font-size: 11px; color: {COLOR_TEXT_LIGHT}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(sub)
        layout.addSpacing(18)

        self._first = self._make_input("First Name")
        self._last  = self._make_input("Last Name")
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name_row.addWidget(self._first)
        name_row.addWidget(self._last)
        layout.addLayout(name_row)
        layout.addSpacing(10)

        self._email = self._make_input("Email Address")
        layout.addWidget(self._email)
        layout.addSpacing(10)

        self._pwd  = self._make_input("Password",         password=True)
        self._pwd2 = self._make_input("Confirm Password", password=True)
        pwd_row = QHBoxLayout()
        pwd_row.setSpacing(10)
        pwd_row.addWidget(self._pwd)
        pwd_row.addWidget(self._pwd2)
        layout.addLayout(pwd_row)
        layout.addSpacing(16)

        role_lbl = QLabel("Select your role")
        role_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: #D8E8FF; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(role_lbl)
        layout.addSpacing(8)

        self._student_card.set_selected(True)
        self._student_card.clicked.connect(lambda: self._select_role("student"))
        self._examiner_card.clicked.connect(lambda: self._select_role("examiner"))
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.addWidget(self._student_card)
        cards_row.addWidget(self._examiner_card)
        cards_row.addStretch()
        layout.addLayout(cards_row)
        layout.addSpacing(16)

        self._err.setFixedHeight(18)
        self._err.setStyleSheet(
            f"font-size: 11px; color: {COLOR_ERROR}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(self._err)
        layout.addSpacing(6)

        self._next_btn.setFixedHeight(44)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY}; color: white;
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: 700; letter-spacing: 2px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {COLOR_PRIMARY_DARK}; }}
        """)
        self._next_btn.clicked.connect(self._on_next)
        layout.addWidget(self._next_btn)
        layout.addStretch(1)

        outer.addWidget(inner_widget)
        outer.addStretch(1)


# ── Role card ──────────────────────────────────────────────────────────────

class _RoleCard(QFrame):

    clicked = Signal()

    def __init__(self, icon: str, label: str, role: str, parent=None):
        super().__init__(parent)
        self.role      = role
        self._selected = False
        self._text_lbl = QLabel(label)
        self.setFixedSize(120, 76)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(icon)
        self._apply_style()

    def _build(self, icon: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent;")
        self._text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_lbl.setStyleSheet("font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(icon_lbl)
        layout.addWidget(self._text_lbl)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet("QFrame { background-color: #FFFFFF; border: 2px solid #FFFFFF; border-radius: 8px; }")
            self._text_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 700; color: {COLOR_BRAND_DARK}; "
                f"font-family: {FONT_FAMILY}; background: transparent;"
            )
        else:
            self.setStyleSheet("QFrame { background-color: rgba(255,255,255,0.08); border: 2px solid rgba(255,255,255,0.25); border-radius: 8px; }")
            self._text_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {COLOR_TEXT_LIGHT}; "
                f"font-family: {FONT_FAMILY}; background: transparent;"
            )

    def mousePressEvent(self, event):
        self.clicked.emit()


# ── Step 2 ─────────────────────────────────────────────────────────────────
class _Step2Widget(QWidget):

    completed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._role        = "student"
        self._heading     = QLabel("Examiner Details")
        self._institution = QComboBox()
        self._department  = QComboBox()
        self._err         = QLabel("")
        self._build()

    def set_role(self, role: str):
        self._role = role
        self._heading.setText("Examiner Details" if role == "examiner" else "Student Details")

    def reset(self):
        self._institution.setCurrentIndex(0)
        self._department.setCurrentIndex(0)
        self._err.setText("")

    def _on_next(self):
        self._err.setText("")
        self.completed.emit({
            "institution": self._institution.currentText(),
            "department":  self._department.currentText(),
        })

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        inner_widget = QWidget()
        inner_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner_widget.setFixedWidth(FORM_WIDTH)
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        self._heading.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: #FFFFFF; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(self._heading)
        layout.addSpacing(4)

        sub = QLabel("Step 2 of 3 — Role Information")
        sub.setStyleSheet(
            f"font-size: 11px; color: {COLOR_TEXT_LIGHT}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(sub)
        layout.addSpacing(20)

        combo_style = f"""
            QComboBox {{
                background-color: {COLOR_BG_CARD}; color: {COLOR_TEXT_DARK};
                border: 1.5px solid {COLOR_INPUT_BORDER}; border-radius: 4px;
                padding: 0 12px; font-size: 12px;
                font-family: {FONT_FAMILY};
            }}
            QComboBox:focus {{ border: 1.5px solid {COLOR_INPUT_FOCUS}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLOR_BG_CARD}; color: {COLOR_TEXT_DARK};
                selection-background-color: {COLOR_PRIMARY_ALT}; selection-color: white;
            }}
        """

        self._institution.addItems(INSTITUTIONS)
        self._institution.setFixedHeight(40)
        self._institution.setStyleSheet(combo_style)

        self._department.addItems(DEPARTMENTS)
        self._department.setFixedHeight(40)
        self._department.setStyleSheet(combo_style)

        for lbl_text, widget in [
            ("Institution", self._institution),
            ("Department",  self._department),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: #D8E8FF; "
                f"font-family: {FONT_FAMILY}; background: transparent;"
            )
            layout.addWidget(lbl)
            layout.addSpacing(6)
            layout.addWidget(widget)
            layout.addSpacing(12)

        self._err.setFixedHeight(18)
        self._err.setStyleSheet(
            f"font-size: 11px; color: {COLOR_ERROR}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(self._err)
        layout.addSpacing(6)

        next_btn = QPushButton("NEXT →")
        next_btn.setFixedHeight(44)
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY}; color: white;
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: 700; letter-spacing: 2px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {COLOR_PRIMARY_DARK}; }}
        """)
        next_btn.clicked.connect(self._on_next)
        layout.addWidget(next_btn)
        layout.addStretch(1)

        outer.addWidget(inner_widget)
        outer.addStretch(1)

# ── Step 3 ─────────────────────────────────────────────────────────────────

class _Step3Widget(QWidget):
    """
    Face enrollment — camera starts automatically on show.
    Complete Registration button only appears after photo is taken.
    Registration + enrollment happen together on button click.
    """

    enroll_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._camera_overlay = _CameraCaptureOverlay(self)
        self._captured_frame = None
        self._preview_thumb = QLabel("No photo captured yet")
        self._open_camera_btn = QPushButton("OPEN CAMERA")
        self._enroll_btn    = QPushButton("COMPLETE REGISTRATION →")
        self._camera_overlay.frame_captured.connect(self._on_frame_captured)
        self._build()
        
    def get_captured_frame(self):
        return self._captured_frame

    def prewarm_camera(self):
        self._camera_overlay.prewarm()

    def stop_camera(self):
        self._camera_overlay.stop_camera()
        self._captured_frame = None
        self._preview_thumb.setPixmap(QPixmap())
        self._preview_thumb.setText("No photo captured yet")
        self._enroll_btn.hide()

    def _on_frame_captured(self, frame):
        self._captured_frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            360, 230,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_thumb.setPixmap(pix)
        self._preview_thumb.setText("")
        self._enroll_btn.show()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        inner_widget = QWidget()
        inner_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner_widget.setFixedWidth(FORM_WIDTH)
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)

        heading = QLabel("Face Enrollment")
        heading.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: #FFFFFF; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        layout.addWidget(heading)
        layout.addSpacing(4)

        sub = QLabel("Step 3 of 3 — Take a photo to complete registration")
        sub.setStyleSheet(
            f"font-size: 11px; color: {COLOR_TEXT_LIGHT}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(16)

        self._preview_thumb.setFixedSize(360, 230)
        self._preview_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_thumb.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(0,0,0,0.35);
                border: 2px solid rgba(255,255,255,0.25);
                border-radius: 8px;
                color: {COLOR_TEXT_LIGHT};
                font-size: 12px;
                font-family: {FONT_FAMILY};
            }}
        """)
        layout.addWidget(self._preview_thumb, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(12)

        self._open_camera_btn.setFixedHeight(42)
        self._open_camera_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_camera_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY}; color: white;
                border: none; border-radius: 4px;
                font-size: 12px; font-weight: 700; letter-spacing: 1px;
                padding: 0 20px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {COLOR_PRIMARY_DARK}; }}
        """)
        self._open_camera_btn.clicked.connect(self._camera_overlay.open_capture)
        layout.addWidget(self._open_camera_btn)
        layout.addSpacing(8)

        self._enroll_btn.setFixedHeight(44)
        self._enroll_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enroll_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SUCCESS_BTN}; color: white;
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: 700; letter-spacing: 1px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: {COLOR_SUCCESS_BTN_HOVER}; }}
            QPushButton:pressed {{ background-color: {COLOR_SUCCESS_BTN_PRESSED}; }}
        """)
        self._enroll_btn.clicked.connect(self.enroll_requested)
        self._enroll_btn.hide()
        layout.addWidget(self._enroll_btn)
        layout.addStretch(1)

        outer.addWidget(inner_widget)
        outer.addStretch(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._camera_overlay.setGeometry(self.rect())


class _CameraCaptureOverlay(QWidget):
    frame_captured = Signal(object)  # numpy BGR frame

    def __init__(self, parent=None):
        super().__init__(parent)
        from client.config import CAMERA_INDEX
        self.setGeometry(parent.rect())
        self.hide()
        self.setStyleSheet("background-color: rgba(10, 18, 40, 150);")

        self._camera_widget = CameraPreviewWidget(camera_index=CAMERA_INDEX)
        self._camera_widget.set_preview_size(560, 400)
        self._camera_widget.frame_captured.connect(self._on_frame_captured)

        self._card = QFrame(self)
        self._card.setFixedSize(780, 620)
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: #F9FBFF;
                border: 1px solid #D9E6FF;
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self._card)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        title = QLabel("Capture Enrollment Photo")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {COLOR_TEXT_HEAD}; "
            f"font-family: {FONT_FAMILY};"
        )
        subtitle = QLabel("Center your face and click Take Photo")
        subtitle.setStyleSheet(
            f"font-size: 12px; color: {COLOR_TEXT_MUTED}; font-family: {FONT_FAMILY};"
        )
        close_btn = QPushButton("CLOSE")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_BG_SOFT};
                color: {COLOR_PRIMARY_ALT};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 11px;
                font-weight: 700;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: #E5EEFF; }}
        """)
        close_btn.clicked.connect(self.hide)
        heading_col = QVBoxLayout()
        heading_col.setContentsMargins(0, 0, 0, 0)
        heading_col.setSpacing(2)
        heading_col.addWidget(title)
        heading_col.addWidget(subtitle)
        top_row.addLayout(heading_col)
        top_row.addStretch(1)
        top_row.addWidget(close_btn)
        layout.addLayout(top_row)

        camera_shell = QFrame()
        camera_shell.setStyleSheet("""
            QFrame {
                background-color: #EEF4FF;
                border: 1px solid #D9E6FF;
                border-radius: 14px;
            }
        """)
        camera_shell_layout = QVBoxLayout(camera_shell)
        camera_shell_layout.setContentsMargins(16, 14, 16, 14)
        camera_shell_layout.addWidget(self._camera_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(camera_shell, alignment=Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent() is not None:
            self.setGeometry(self.parent().rect())
        self._card.move(
            (self.width() - self._card.width()) // 2,
            (self.height() - self._card.height()) // 2,
        )

    def prewarm(self):
        self._camera_widget.ensure_running()

    def stop_camera(self):
        self._camera_widget.stop()
        self.hide()

    def open_capture(self):
        self.prewarm()
        self._camera_widget.start()
        if self.parent() is not None:
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def _on_frame_captured(self, frame):
        self.frame_captured.emit(frame)
        self.hide()
