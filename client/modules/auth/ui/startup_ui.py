"""
client/modules/auth/ui/startup_ui.py

Startup screen UI — fullscreen, single gradient background, centered content.
Animation deferred via QTimer so layout resolves before opacity starts.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QSequentialAnimationGroup,
    QParallelAnimationGroup, QPauseAnimation, QEasingCurve, QTimer,
)
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush


class StartupUI(QWidget):

    login_requested  = Signal()
    signup_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._seq = None  # Keep animation alive
        self._build_ui()
        # Defer animation until after layout resolves — fixes wrong-position bug
        QTimer.singleShot(50, self._start_animation)

    def paintEvent(self, event):
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor("#EEF3FF"))
        grad.setColorAt(1.0, QColor("#D8E4FF"))
        painter.fillRect(self.rect(), QBrush(grad))
        painter.end()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(2)

        # Center content
        center = QWidget()
        center.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._logo = QLabel("✦")
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo.setStyleSheet(
            "font-size: 52px; color: #2557C7; background: transparent;"
        )
        center_layout.addWidget(self._logo)
        center_layout.addSpacing(10)

        self._app_name = QLabel("ExamApp")
        self._app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._app_name.setStyleSheet(
            "font-size: 52px; font-weight: 800; color: #1A3A8A; "
            "letter-spacing: 6px; background: transparent;"
        )
        center_layout.addWidget(self._app_name)
        center_layout.addSpacing(12)

        self._tagline = QLabel("Secure Examination & Proctoring Platform")
        self._tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tagline.setStyleSheet(
            "font-size: 14px; color: #4466AA; letter-spacing: 1px; background: transparent;"
        )
        center_layout.addWidget(self._tagline)
        center_layout.addSpacing(48)

        # Buttons
        self._btn_container = QWidget()
        self._btn_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_layout = QHBoxLayout(self._btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(20)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._login_btn = QPushButton("LOG IN")
        self._login_btn.setFixedSize(180, 48)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2557C7; color: white;
                border: none; border-radius: 4px;
                font-size: 13px; font-weight: 700; letter-spacing: 2px;
            }
            QPushButton:hover { background-color: #3B76E8; }
            QPushButton:pressed { background-color: #1A4DB5; }
        """)

        self._signup_btn = QPushButton("SIGN UP")
        self._signup_btn.setFixedSize(180, 48)
        self._signup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._signup_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #2557C7;
                border: 2px solid #2557C7; border-radius: 4px;
                font-size: 13px; font-weight: 700; letter-spacing: 2px;
            }
            QPushButton:hover { background-color: #2557C7; color: white; }
            QPushButton:pressed { background-color: #1A4DB5; color: white; }
        """)

        self._login_btn.clicked.connect(self.login_requested)
        self._signup_btn.clicked.connect(self.signup_requested)
        btn_layout.addWidget(self._login_btn)
        btn_layout.addWidget(self._signup_btn)
        center_layout.addWidget(self._btn_container)

        layout.addWidget(center)
        layout.addStretch(2)

        # Footer
        footer_w = QWidget()
        footer_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        fl = QHBoxLayout(footer_w)
        fl.setContentsMargins(0, 0, 0, 24)
        fl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        footer = QLabel("CS-305 Software Engineering  ·  v1.0.0")
        footer.setStyleSheet("font-size: 10px; color: #99AACC; background: transparent;")
        fl.addWidget(footer)
        layout.addWidget(footer_w)

        # Set opacity effects — start invisible
        self._logo_fx    = QGraphicsOpacityEffect(self._logo)
        self._name_fx    = QGraphicsOpacityEffect(self._app_name)
        self._tagline_fx = QGraphicsOpacityEffect(self._tagline)
        self._btn_fx     = QGraphicsOpacityEffect(self._btn_container)

        self._logo.setGraphicsEffect(self._logo_fx)
        self._app_name.setGraphicsEffect(self._name_fx)
        self._tagline.setGraphicsEffect(self._tagline_fx)
        self._btn_container.setGraphicsEffect(self._btn_fx)

        self._logo_fx.setOpacity(0)
        self._name_fx.setOpacity(0)
        self._tagline_fx.setOpacity(0)
        self._btn_fx.setOpacity(0)

    def _start_animation(self):
        """
        Start animation after 50ms delay so Qt layout engine
        has fully resolved widget positions first.
        Without this delay, opacity effects cause widgets to
        render at (0,0) before snapping to their correct position.
        """
        def make_fade(effect, duration: int) -> QPropertyAnimation:
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            return anim

        self._seq = QSequentialAnimationGroup()

        step1 = QParallelAnimationGroup()
        step1.addAnimation(make_fade(self._logo_fx,  1000))
        step1.addAnimation(make_fade(self._name_fx,  1000))
        self._seq.addAnimation(step1)

        self._seq.addAnimation(make_fade(self._tagline_fx, 700))
        self._seq.addAnimation(QPauseAnimation(500))
        self._seq.addAnimation(make_fade(self._btn_fx, 600))

        self._seq.start()
