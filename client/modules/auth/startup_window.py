"""
client/modules/auth/startup_window.py

Startup screen controller — logic only.
Shows app name with fade-in animation, then Login/Sign Up buttons.

Signals emitted:
    login_requested()
    signup_requested()
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMainWindow
import os

from client.modules.auth.ui.startup_ui import StartupUI


class StartupWindow(QMainWindow):
    """
    Startup screen — fullscreen, no split design.
    App name fades in center, then Login/Sign Up buttons appear.
    """

    login_requested  = Signal()
    signup_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ExamApp")
        self.showFullScreen()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint,
        )

        self.ui = StartupUI()
        self.setCentralWidget(self.ui)

        self.ui.login_requested.connect(self.login_requested)
        self.ui.signup_requested.connect(self.signup_requested)

    def keyPressEvent(self, event: QKeyEvent):
        import os
        if os.getenv("DEBUG", "false").lower() == "true":
            if event.key() == Qt.Key.Key_F12:
                self.close()
                return
        super().keyPressEvent(event)
