#!/usr/bin/env python3
"""
SEPP – Secure Entrance Portal
Pure UI  •  PySide6  •  No backend logic

Dependencies:
    pip install PySide6
"""

import sys
import socket
import time

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QFrame, QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
#from PySide6.QtCore import QDateTime, QTimer   
# Uncomment the line above to add the date and time on the right side of the bar
from PySide6.QtGui import QFont, QCursor

try:
    from  client.modules.common.loading_spinner import SpinnerOverlay
except ImportError:  # Allows this UI file to still run standalone during local testing.
    from client.modules.common.loading_spinner import SpinnerOverlay

# ─────────────────────────────────────────────────────────────────────────────
#  Colour tokens
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
#  Latency thread  (TCP round-trip to 8.8.8.8:53, every 3 s)
# ─────────────────────────────────────────────────────────────────────────────
class LatencyThread(QThread):
    result = Signal(int)   # ms, or -1 on timeout

    def __init__(self):
        super().__init__()
        self._active = True
        

    def _measure(self) -> int:
        try:
            t0 = time.perf_counter()
            s  = socket.create_connection(("8.8.8.8", 53), timeout=3)
            s.close()
            return max(1, int((time.perf_counter() - t0) * 1000))
        except Exception:
            return -1

    def run(self):
        while self._active:
            self.result.emit(self._measure())
            self.msleep(3000)

    def stop(self):
        self._active = False
        self.wait()


# ─────────────────────────────────────────────────────────────────────────────
#  Info dialog  (Forgot-password + footer links)
# ─────────────────────────────────────────────────────────────────────────────
class InfoDialog(QDialog):
    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(400)
        self.setStyleSheet(f"background:{CARD};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(20)

        lbl = QLabel(body)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size:14px; color:{T_PRIMARY}; line-height:1.6;")
        lay.addWidget(lbl)

        btn = QPushButton("OK")
        btn.setFixedHeight(40)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{NAVY}; color:white;
                border:none; border-radius:7px;
                font-size:14px; font-weight:600;
            }}
            QPushButton:hover  {{ background:#1c3461; }}
            QPushButton:pressed{{ background:#091529; }}
        """)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# ─────────────────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────────────────
class LoginUI(QWidget):
    login_requested = Signal(str, str)
    register_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setWindowTitle("SEPP – Secure Entrance Portal")
        # self.setMinimumSize(560, 620)
        # self.resize(620, 680)
        # The Above Mentioned Lines Are Commented Out To Allow The Login UI To Be Resizable By The main_window.py FIle
        self.setStyleSheet(f"background:{BG};")
        self._spinner = None
        self._build_ui()
        # self._start_clock()
        # Uncomment the line above to add the date and time on the right side of the bar
        self._spinner = SpinnerOverlay(self, color=NAVY)
        self._start_threads()
        
    # __________________________________________________________________________
    # Clock Functionality
    # __________________________________________________________________________
    # def _start_clock(self):def _start_clock(self):
    #     self._clock_timer = QTimer(self)
    #     self._clock_timer.timeout.connect(self._update_clock)
    #     self._clock_timer.start(1000)
    #     self._update_clock()

    # def _update_clock(self):
    #     now = QDateTime.currentDateTime()
    #     self.datetime_lbl.setText(now.toString("ddd, dd MMM yyyy  |  hh:mm AP"))
        
    # ─────────────────────────────────────────────────────────────────────
    #  UI assembly
    # ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet(f"background:{BG};")

        vlay = QVBoxLayout(self)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        vlay.addWidget(self._header())
        vlay.addWidget(self._body(), stretch=1)
        vlay.addWidget(self._footer())

    # ── header ────────────────────────────────────────────────────────────
    def _header(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"background:{CARD}; border-bottom:1px solid {BORDER};")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(36, 0, 36, 0)
        lay.setSpacing(0)

        self.back_btn = QPushButton("← Back")
        self.back_btn.setFlat(True)
        self.back_btn.setAutoDefault(False)
        self.back_btn.setDefault(False)
        self.back_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                color:{T_SECONDARY};
                background:transparent;
                border:none;
                font-size:13px;
                font-weight:600;
                padding-right:18px;
                outline:none;
            }}
            QPushButton:hover {{
                color:{NAVY};
                background:transparent;
                border:none;
            }}
            QPushButton:pressed {{
                color:{T_SECONDARY};
                background:transparent;
                border:none;
            }}
            QPushButton:focus {{
                color:{T_SECONDARY};
                background:transparent;
                border:none;
                outline:none;
            }}
        """)
        self.back_btn.clicked.connect(self.back_requested.emit)

        brand = QLabel("SEPP")
        brand.setStyleSheet(
            f"font-size:17px; font-weight:800; color:{T_PRIMARY}; letter-spacing:1px;")

        sep = QLabel("  |  ")
        sep.setStyleSheet(f"color:{BORDER}; font-size:17px;")

        tagline = QLabel("SECURE ENTRANCE PORTAL")
        tagline.setStyleSheet(
            f"font-size:11px; font-weight:500; color:{T_SECONDARY}; letter-spacing:2.5px;")

        lay.addWidget(self.back_btn)
        lay.addStretch() # Remove This Line TO Make The Branding Appear Next To The Back Button
        lay.addWidget(brand)
        lay.addWidget(sep)
        lay.addWidget(tagline)
        # lay.addStretch() # Remove This Line To Make The TAGLINE AND BRANDING APPEAR ON THE RIGHT SIDE OF THE BAR
        
        # To Add The Date and Time on the Right Side of the BAR, Uncomment the following code and remove the stretch line above
        # lay.addSpacing(28)        
        # self.datetime_lbl = QLabel()
        # self.datetime_lbl.setStyleSheet(
        #     f"font-size:12px; font-weight:500; color:{T_SECONDARY};"
        # )
        # lay.addWidget(self.datetime_lbl)
        
        return bar

    # ── body  (centred card) ──────────────────────────────────────────────
    def _body(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet(f"background:{BG};")

        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 36, 0, 36)

        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(self._sign_in_card())
        h.addStretch()

        outer.addStretch()
        outer.addLayout(h)
        outer.addStretch()

        return body

    # ── sign-in card ──────────────────────────────────────────────────────
    def _sign_in_card(self) -> QFrame:
        card = QFrame()
        card.setFixedWidth(480)
        card.setStyleSheet(f"""
            QFrame {{
                background:{CARD};
                border:1px solid {BORDER};
                border-radius:14px;
            }}
        """)
        card.setMinimumHeight(650)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(44, 34, 44, 32)
        lay.setSpacing(0)

        # title
        t = QLabel("Sign In")
        t.setStyleSheet(f"font-size:24px; font-weight:700; color:{T_PRIMARY}; border:none;")
        lay.addWidget(t)
        lay.addSpacing(4)

        sub = QLabel("Enter your examination credentials to proceed.")
        sub.setStyleSheet(f"font-size:13px; color:{T_SECONDARY}; border:none;")
        lay.addWidget(sub)
        lay.addSpacing(24)

        # username
        lay.addWidget(self._field_lbl("Username"))
        lay.addSpacing(6)
        username_container = QFrame()
        username_container.setFixedHeight(46)
        username_container.setStyleSheet(f"""
            QFrame {{
                border:1.5px solid {INP_BORDER};
                border-radius:8px;
                background:white;
            }}
        """)
        u_row = QHBoxLayout(username_container)
        u_row.setContentsMargins(14, 0, 8, 0)
        u_row.setSpacing(6)

        u_icon = QLabel("👤")
        u_icon.setStyleSheet("font-size:14px; background:transparent; border:none;")
        u_row.addWidget(u_icon)

        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter student ID or email")
        self.username.setStyleSheet("border:none; background:transparent; font-size:14px; font-color:{T_PRIMARY};")
        self.username.setStyleSheet(f"""
            QLineEdit {{
                border:none; background:transparent;
                font-size:14px; color:{T_PRIMARY};
            }}
        """)
        
        u_row.addWidget(self.username, stretch=1)

        lay.addWidget(username_container)
        self.username.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        lay.addSpacing(16)

        # password label
        lay.addWidget(self._field_lbl("Password"))
        lay.addSpacing(6)

        # password input
        self.pw_container, self.pw_field = self._password_input()
        lay.addWidget(self.pw_container)
        self.pw_field.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        lay.addSpacing(8)

        # forgot password link below password input
        forgot_row = QHBoxLayout()
        forgot_row.addStretch()

        forgot = self._link("Forgot password?")
        forgot.setStyleSheet(
            f"font-size:13px; color:{T_SECONDARY}; "
            "border:none; background:transparent;"
        )
        forgot.linkActivated.connect(lambda _: self._dialog(
            "Forgot Password",
            "Please contact your institution's IT administrator "
            "to reset your examination portal password."
        ))

        forgot_row.addWidget(forgot)
        lay.addLayout(forgot_row)
        lay.addSpacing(14)

        # checkbox
        self.policy_checkbox = QCheckBox("Acknowledge monitoring policies")
        self.policy_checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.policy_checkbox.setStyleSheet(f"""
            QCheckBox {{
                font-size:13px;
                color:{T_PRIMARY};
                spacing:8px;
                border:none;
                background:transparent;
                outline:none;
            }}
            QCheckBox:focus {{
                color:{T_PRIMARY};
                border:none;
                background:transparent;
                outline:none;
            }}
            QCheckBox::indicator {{
                width:16px;
                height:16px;
                border:1.5px solid {INP_BORDER};
                border-radius:4px;
                background:white;
            }}
            QCheckBox::indicator:hover {{
                border:1.5px solid {INP_BORDER};
                background:white;
            }}
            QCheckBox::indicator:unchecked {{
                border:1.5px solid {INP_BORDER};
                background:white;
            }}
            QCheckBox::indicator:checked {{
                background:{NAVY};
                border-color:{NAVY};
            }}
            QCheckBox::indicator:focus {{
                border:1.5px solid {INP_BORDER};
                background:white;
            }}
        """)
        lay.addWidget(self.policy_checkbox)
        lay.addSpacing(8)

        self.status_lbl = QLabel("")
        self.status_lbl.setFixedHeight(28)
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet(
            f"font-size:12px; color:{T_SECONDARY}; border:none; background:transparent;"
        )
        lay.addWidget(self.status_lbl)
        lay.addSpacing(10)

        # verify button
        self.login_btn = QPushButton("🛡 Login")
        self.login_btn.setFixedHeight(52)
        self.login_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.login_btn.setAutoDefault(False)
        self.login_btn.setDefault(False)
        self.login_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.login_btn.setStyleSheet(f"""
            QPushButton:focus {{
                background:{NAVY};
                color:white;
                border:none;
                border-radius:8px;
                font-size:16px;
                font-weight:600;
                letter-spacing:0.4px;
                outline:none;
            }}
            QPushButton:hover  {{
                background:#1c3461; 
                }}
            QPushButton:pressed {{
                background:#091529; 
                }}
            QPushButton:disabled {{ 
            background:#9CA3AF;
            color:#EEF2F7; 
                }}
        """)
        self.login_btn.clicked.connect(self._on_login_clicked)
        lay.addWidget(self.login_btn)
        lay.addSpacing(12)
        
        reg_row = QHBoxLayout()
        reg_row.setSpacing(4)
        reg_row.addStretch()
        no_acc = QLabel("Don't have an account?")
        no_acc.setStyleSheet(
            f"font-size:12px; color:{T_SECONDARY}; border:none; background:transparent;"
        )
        reg_btn = QPushButton("Sign Up")
        reg_btn.setFlat(True)
        reg_btn.setAutoDefault(False)
        reg_btn.setDefault(False)
        reg_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reg_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reg_btn.setStyleSheet(f"""
            QPushButton {{
                font-size:12px;
                font-weight:700;
                color:{NAVY};
                background:transparent;
                border:none;
                padding:0;
                outline:none;
            }}
            QPushButton:hover {{
                color:{NAVY};
                background:transparent;
                border:none;
            }}
            QPushButton:pressed {{
                color:{NAVY};
                background:transparent;
                border:none;
            }}
            QPushButton:focus {{
                color:{NAVY};
                background:transparent;
                border:none;
                outline:none;
            }}
            QPushButton:checked {{
                color:{NAVY};
                background:transparent;
                border:none;
            }}
        """)
        reg_btn.clicked.connect(self.register_requested.emit)
        reg_row.addWidget(no_acc)
        reg_row.addWidget(reg_btn)
        reg_row.addStretch()
        lay.addLayout(reg_row)
        lay.addSpacing(18)

        # divider
        lay.addWidget(self._hline())
        lay.addSpacing(18)

        # latency row
        lat_row = QHBoxLayout()
        lat_row.addWidget(self._info_lbl("System Latency"))
        lat_row.addStretch()
        self.latency_lbl = QLabel("Measuring…")
        self.latency_lbl.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{GREEN};")
        lat_row.addWidget(self.latency_lbl)
        lay.addLayout(lat_row)
        lay.addSpacing(10)

        # security protocol row
        sec_row = QHBoxLayout()
        sec_row.addWidget(self._info_lbl("Security Protocol"))
        sec_row.addStretch()
        sec_val = QLabel("AES-256 Encrypted")
        sec_val.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{AMBER}; border:none; background:transparent;")
        sec_row.addWidget(sec_val)
        lay.addLayout(sec_row)

        self.username.returnPressed.connect(self._on_login_clicked)
        self.pw_field.returnPressed.connect(self._on_login_clicked)

        return card

    # ── footer ────────────────────────────────────────────────────────────
    def _footer(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(46)
        bar.setStyleSheet(f"background:{BG}; border-top:1px solid {BORDER};")

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(44, 0, 44, 0)
        lay.setSpacing(0)

        links = [
            ("Privacy Policy",
             "This portal collects and processes data strictly for examination integrity purposes. "
             "All data is handled in accordance with applicable privacy regulations."),
            ("Terms of Use",
             "By accessing this portal you agree to comply with your institution's examination "
             "rules and the monitoring policies in effect during your session."),
            ("Help Center",
             "For technical assistance please contact your institution's IT support team "
             "or email support@sepp.edu."),
        ]
        for i, (label, msg) in enumerate(links):
            lnk = self._link(label)
            lnk.linkActivated.connect(
                lambda _, t=label, m=msg: self._dialog(t, m))
            lay.addWidget(lnk)
            if i < len(links) - 1:
                dot = QLabel("   ·   ")
                dot.setStyleSheet(f"color:{T_SECONDARY}; font-size:12px;")
                lay.addWidget(dot)

        lay.addStretch()

        copy = QLabel("© 2024 SEPP Secure Examination Platform. v2.4.0 Active")
        copy.setStyleSheet(f"font-size:11px; color:{T_SECONDARY};")
        lay.addWidget(copy)
        return bar

    # ─────────────────────────────────────────────────────────────────────
    #  Small helpers
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _field_lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"font-size:13px; font-weight:600; color:{T_PRIMARY}; border:none;")
        return l

    @staticmethod
    def _info_lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"font-size:13px; color:{T_SECONDARY}; border:none; background:transparent;")
        return l

    @staticmethod
    def _link(text: str) -> QLabel:
        l = QLabel(
            f'<a href="#" style="color:{T_SECONDARY}; text-decoration:none; border:none;">{text}</a>')
        l.setTextFormat(Qt.TextFormat.RichText)
        l.setStyleSheet("font-size:12px;")
        l.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        return l

    @staticmethod
    def _plain_input(placeholder: str, prefix_icon: str = "") -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(
            f"{prefix_icon}  {placeholder}" if prefix_icon else placeholder)
        inp.setFixedHeight(46)
        inp.setStyleSheet(f"""
            QLineEdit {{
                border:1.5px solid {INP_BORDER};
                border-radius:8px;
                padding:0 14px;
                font-size:14px;
                color:{T_PRIMARY};
                background:white;
            }}
            QLineEdit:focus {{ border-color:{INP_FOCUS}; }}
        """)
        return inp

    @staticmethod
    def _password_input():
        """Returns (container QFrame, inner QLineEdit)."""
        container = QFrame()
        container.setFixedHeight(46)
        container.setStyleSheet(f"""
            QFrame {{
                border:1.5px solid {INP_BORDER};
                border-radius:8px;
                background:white;
            }}
        """)

        row = QHBoxLayout(container)
        row.setContentsMargins(14, 0, 8, 0)
        row.setSpacing(4)

        lock = QLabel("🔒")
        lock.setStyleSheet("font-size:14px; background:transparent; border:none;")
        row.addWidget(lock)

        pw = QLineEdit()
        pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw.setPlaceholderText("••••••••")
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

        eye = QPushButton("👁")
        eye.setFixedSize(34, 34)
        eye.setCheckable(True)
        eye.setAutoDefault(False)
        eye.setDefault(False)
        eye.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        eye.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        eye.setStyleSheet("""
            QPushButton {
                border:none;
                background:transparent;
                font-size:16px;
                outline:none;
            }
            QPushButton:hover {
                background:#F3F4F6;
                border-radius:5px;
            }
            QPushButton:pressed {
                background:transparent;
                border:none;
            }
            QPushButton:focus {
                background:transparent;
                border:none;
                outline:none;
            }
            QPushButton:checked {
                background:transparent;
                border:none;
            }
        """)
        eye.toggled.connect(lambda on: pw.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
        ))
        row.addWidget(eye)

        return container, pw

    @staticmethod
    def _hline() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"color:{BORDER};")
        return f

    def _dialog(self, title: str, msg: str):
        InfoDialog(title, msg, parent=self).exec()

    def _on_login_clicked(self):
        username = self.username.text().strip()
        password = self.pw_field.text()

        if not username or not password:
            self.set_status("Please enter your username/email and password.", "error")
            return

        if not self.policy_checkbox.isChecked():
            self.set_status("Please acknowledge the monitoring policies before signing in.", "error")
            return

        self.login_requested.emit(username, password)

    @Slot(str, str)
    def set_status(self, text: str, state: str):
        colors = {
            "error": RED,
            "success": GREEN,
            "loading": T_SECONDARY,
            "": T_SECONDARY,
        }
        self.status_lbl.setStyleSheet(
            f"font-size:12px; color:{colors.get(state, T_SECONDARY)}; "
            "border:none; background:transparent;"
        )
        self.status_lbl.setText(text)

    @Slot(bool)
    def set_loading(self, loading: bool):
        self.login_btn.setEnabled(not loading)
        self.login_btn.setText("Signing in..." if loading else "🛡 Login")

        if self._spinner is None:
            return

        if loading:
            self._spinner.setGeometry(self.rect())
            self._spinner.show()
            self._spinner.raise_()
        else:
            self._spinner.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._spinner is not None:
            self._spinner.setGeometry(self.rect())

    # ─────────────────────────────────────────────────────────────────────
    #  Thread management
    # ─────────────────────────────────────────────────────────────────────
    def _start_threads(self):
        self._lat_thread = LatencyThread()
        self._lat_thread.result.connect(self._on_latency)
        self._lat_thread.start()

    def _on_latency(self, ms: int):
        if ms < 0:
            self.latency_lbl.setText("Timeout")
            self.latency_lbl.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{RED}; border:none; background:transparent;")
        elif ms <= 50:
            self.latency_lbl.setText(f"{ms}ms (Optimal)")
            self.latency_lbl.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{GREEN}; border:none; background:transparent;")
        elif ms <= 150:
            self.latency_lbl.setText(f"{ms}ms (Good)")
            self.latency_lbl.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{AMBER}; border:none; background:transparent;")
        else:
            self.latency_lbl.setText(f"{ms}ms (Poor)")
            self.latency_lbl.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{RED}; border:none; background:transparent;")

    def closeEvent(self, event):
        self._lat_thread.stop()
        event.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    win = LoginUI()
    win.resize(620, 680)
    win.show()
    sys.exit(app.exec())
