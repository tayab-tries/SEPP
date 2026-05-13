"""
client/modules/auth/ui/login_ui.py
Login screen UI — fullscreen, white/blue diagonal split.
Back button on LEFT (white) panel — always visible as dark blue text.
"""

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import (
    QAction,
)
from client.modules.common.diagonal_background import DiagonalBackground
from client.modules.common.design_tokens import (
    COLOR_BG_CARD,
    COLOR_ERROR,
    COLOR_INPUT_BORDER,
    COLOR_INPUT_FOCUS,
    COLOR_PRIMARY,
    COLOR_PRIMARY_ALT,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_TEXT_DARK,
    COLOR_TEXT_LIGHT,
    FONT_FAMILY,
)


class LoginUI(QWidget):
    login_requested    = Signal(str, str)
    register_requested = Signal()
    back_requested     = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg    = DiagonalBackground(self)
        self._left  = _LeftPanel(self)
        self._right = _RightPanel(self)
        self._bg.lower()
        self._right.login_requested.connect(self.login_requested)
        self._right.register_requested.connect(self.register_requested)
        self._left.back_requested.connect(self.back_requested)
        from client.modules.common.loading_spinner import SpinnerOverlay
        self._spinner = SpinnerOverlay(self, color="#FFFFFF")
        self._layout_panels()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_panels()
        self._spinner.setGeometry(self.rect())

    def _layout_panels(self):
        w      = self.width()
        h      = self.height()
        left_w = int(w * 0.42)
        self._bg.setGeometry(0, 0, w, h)
        self._left.setGeometry(0, 0, left_w, h)
        self._right.setGeometry(left_w, 0, w - left_w, h)

    @Slot(str, str)
    def set_status(self, text: str, state: str):
        self._right.set_status(text, state)

    @Slot(bool)
    def set_loading(self, loading: bool):
        self._right.set_loading(loading)
        if loading:
            self._spinner.setGeometry(self.rect())
            self._spinner.show()
            self._spinner.raise_()
        else:
            self._spinner.hide()

# ── Left panel — contains back button + branding ───────────────────────────

class _LeftPanel(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Back button — TOP LEFT of white panel, always visible ──────────
        back_row = QHBoxLayout()
        back_row.setContentsMargins(32, 24, 0, 0)
        back_btn = QPushButton("← BACK")
        back_btn.setFlat(True)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 12px; font-weight: 700;
                color: {COLOR_PRIMARY_ALT}; background: transparent;
                border: none; letter-spacing: 1px; padding: 0;
            }}
            QPushButton:hover {{ color: {COLOR_PRIMARY_DARK}; }}
        """)
        back_btn.clicked.connect(self.back_requested)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        layout.addLayout(back_row)

        layout.addStretch(3)

        # ── Branding ───────────────────────────────────────────────────────
        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner = QVBoxLayout(content)
        inner.setContentsMargins(72, 0, 40, 0)
        inner.setSpacing(10)

        logo = QLabel("✦")
        logo.setStyleSheet("font-size: 52px; color: #2557C7; background: transparent;")
        inner.addWidget(logo)

        name = QLabel("ExamApp")
        name.setStyleSheet(
            "font-size: 36px; font-weight: 800; color: #1A3A8A; "
            "letter-spacing: 3px; background: transparent;"
        )
        inner.addWidget(name)

        tag = QLabel("Secure Examination\n& Proctoring Platform")
        tag.setStyleSheet(
            "font-size: 14px; color: #4466AA; line-height: 1.7; background: transparent;"
        )
        inner.addWidget(tag)

        layout.addWidget(content)
        layout.addStretch(4)

        footer_w = QWidget()
        footer_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        fl = QHBoxLayout(footer_w)
        fl.setContentsMargins(72, 0, 0, 32)
        footer = QLabel("CS-305 Software Engineering  ·  v1.0.0")
        footer.setStyleSheet("font-size: 10px; color: #99AACC; background: transparent;")
        fl.addWidget(footer)
        fl.addStretch()
        layout.addWidget(footer_w)


# ── Right panel — form only ────────────────────────────────────────────────

class _RightPanel(QWidget):
    login_requested    = Signal(str, str)
    register_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._status    = QLabel("")
        self._login_btn = QPushButton("SIGN IN")
        self.email_input    = QLineEdit()
        self.password_input = QLineEdit()
        from client.modules.common.loading_spinner import SpinnerOverlay
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(2)

        card_wrapper = QHBoxLayout()
        card_wrapper.addStretch(1)

        card = QWidget()
        card.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        card.setFixedWidth(340)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        heading = QLabel("Welcome Back")
        heading.setStyleSheet(
            f"font-size: 26px; font-weight: 700; color: #FFFFFF; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        card_layout.addWidget(heading)
        card_layout.addSpacing(4)

        sub = QLabel("Sign in to your account")
        sub.setStyleSheet(
            f"font-size: 12px; color: {COLOR_TEXT_LIGHT}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        card_layout.addWidget(sub)
        card_layout.addSpacing(28)

        email_lbl = QLabel("Your email")
        email_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #D8E8FF; background: transparent;"
        )
        card_layout.addWidget(email_lbl)
        card_layout.addSpacing(6)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter your email")
        self.email_input.setFixedHeight(44)
        self._style_input(self.email_input)
        card_layout.addWidget(self.email_input)
        card_layout.addSpacing(16)

        pwd_lbl = QLabel("Password")
        pwd_lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #D8E8FF; background: transparent;"
        )
        card_layout.addWidget(pwd_lbl)
        card_layout.addSpacing(6)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(44)
        self._style_input(self.password_input)

        toggle = QAction("👁", self.password_input)
        toggle.setCheckable(True)
        toggle.triggered.connect(
            lambda checked: self.password_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked
                else QLineEdit.EchoMode.Password
            )
        )
        self.password_input.addAction(toggle, QLineEdit.ActionPosition.TrailingPosition)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(10)

        self._status.setFixedHeight(20)
        self._status.setStyleSheet(
            f"font-size: 11px; color: {COLOR_ERROR}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        card_layout.addWidget(self._status)
        card_layout.addSpacing(14)

        self._login_btn.setFixedHeight(46)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PRIMARY}; color: white;
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: 700; letter-spacing: 2px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }}
            QPushButton:pressed {{ background-color: {COLOR_PRIMARY_DARK}; }}
            QPushButton:disabled {{ background-color: #2A4A80; color: #6688AA; }}
        """)
        self._login_btn.clicked.connect(self._on_login_clicked)
        card_layout.addWidget(self._login_btn)
        card_layout.addSpacing(18)

        reg_row = QHBoxLayout()
        reg_row.setSpacing(4)
        no_acc = QLabel("Don't have an account?")
        no_acc.setStyleSheet("font-size: 11px; color: #BDD0F8; background: transparent;")
        reg_btn = QPushButton("Sign Up")
        reg_btn.setFlat(True)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 11px; font-weight: 700;
                color: {COLOR_TEXT_LIGHT}; background: transparent;
                border: none; padding: 0;
            }}
            QPushButton:hover {{ color: #FFFFFF; }}
        """)
        reg_btn.clicked.connect(self.register_requested)
        reg_row.addWidget(no_acc)
        reg_row.addWidget(reg_btn)
        reg_row.addStretch()
        card_layout.addLayout(reg_row)

        card_wrapper.addWidget(card)
        card_wrapper.addStretch(1)
        layout.addLayout(card_wrapper)
        layout.addStretch(2)

        self.email_input.returnPressed.connect(self._on_login_clicked)
        self.password_input.returnPressed.connect(self._on_login_clicked)

    def _style_input(self, field: QLineEdit):
        field.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_BG_CARD}; color: {COLOR_TEXT_DARK};
                border: 1.5px solid {COLOR_INPUT_BORDER}; border-radius: 4px;
                padding: 0 14px; font-size: 13px;
                font-family: {FONT_FAMILY};
            }}
            QLineEdit:focus {{ border: 1.5px solid {COLOR_INPUT_FOCUS}; }}
        """)

    def _on_login_clicked(self):
        email    = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            self.set_status("Please enter your email and password.", "error")
            return
        self.login_requested.emit(email, password)

    def set_status(self, text: str, state: str):
        colors = {
            "error":   COLOR_ERROR,
            "success": COLOR_SUCCESS,
            "loading": COLOR_TEXT_LIGHT,
            "":        COLOR_TEXT_LIGHT,
        }
        self._status.setStyleSheet(
            f"font-size: 11px; color: {colors.get(state, '#BDD0F8')}; "
            f"font-family: {FONT_FAMILY}; background: transparent;"
        )
        self._status.setText(text)

    def set_loading(self, loading: bool):
        self._login_btn.setEnabled(not loading)
        self._login_btn.setText("SIGNING IN..." if loading else "SIGN IN")