"""
client/modules/exam_engine/ui/exam_ui.py

Main exam area UI — redesigned for the current exam engine contract.

Signals emitted to ExamWindow:
    prev_requested()
    next_requested()
    submit_requested()

Additional signal for future integration:
    chat_message_requested(str)

Slots received from ExamWindow:
    update_timer(str)
    set_timer_warning(bool)
    update_progress(int, int)
    set_navigation_enabled(bool, bool, bool)

Additional optional slots:
    append_chat_message(str, str, str)
    set_guard_status(str, bool)
    set_student_name(str)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


_BG_PAGE = "#F0F2F5"
_BG_WHITE = "#FFFFFF"
_BORDER = "#E5E7EB"
_NAVY = "#0F2454"
_NAVY_HOVER = "#1A3A7A"
_TXT = "#111827"
_TXT_MUTED = "#6B7280"
_GREEN = "#22C55E"
_RED_WARN = "#DC2626"

_PANEL_W = 300
_TOPBAR_H = 56


def _divider() -> QFrame:
    divider = QFrame()
    divider.setFixedHeight(1)
    divider.setStyleSheet(f"background: {_BORDER};")
    return divider


def _section_title(text: str) -> QWidget:
    widget = QWidget()
    widget.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(16, 12, 16, 8)

    icon = QLabel("▣")
    icon.setStyleSheet(f"color: {_TXT_MUTED}; font-size: 13px; background: transparent;")
    label = QLabel(text)
    label.setStyleSheet(
        f"font-size: 14px; font-weight: 800; color: {_TXT}; background: transparent;"
    )
    layout.addWidget(icon)
    layout.addWidget(label)
    layout.addStretch(1)
    return widget


class _TopBar(QWidget):
    submit_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_TOPBAR_H)
        self.setStyleSheet(
            f"background-color: {_BG_WHITE};"
            f"border-bottom: 1px solid {_BORDER};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        brand = QLabel("SEPP")
        brand.setStyleSheet(
            f"font-size: 18px; font-weight: 900; color: {_NAVY}; background: transparent;"
        )
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet(f"color: {_BORDER};")
        separator.setFixedWidth(1)

        self.timer_pill = QWidget()
        self.timer_pill.setStyleSheet("background-color: #F3F4F6; border-radius: 20px;")
        timer_layout = QHBoxLayout(self.timer_pill)
        timer_layout.setContentsMargins(14, 6, 14, 6)
        timer_layout.setSpacing(8)
        timer_layout.addWidget(QLabel("⏱"))
        self.timer_lbl = QLabel("--:--:--")
        self.timer_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {_TXT}; background: transparent;"
        )
        timer_layout.addWidget(self.timer_lbl)

        layout.addWidget(brand)
        layout.addWidget(separator)
        layout.addWidget(self.timer_pill)
        layout.addStretch(1)

        monitoring_badge = QWidget()
        monitoring_badge.setStyleSheet(
            "background-color: white; border: 1px solid #E5E7EB; border-radius: 20px;"
        )
        badge_layout = QHBoxLayout(monitoring_badge)
        badge_layout.setContentsMargins(12, 6, 12, 6)
        badge_layout.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet("color: #F59E0B; font-size: 10px; background: transparent;")
        label = QLabel("MONITORING ACTIVE")
        label.setStyleSheet(
            f"font-size: 12px; font-weight: 800; color: {_TXT}; background: transparent;"
        )
        badge_layout.addWidget(dot)
        badge_layout.addWidget(label)
        layout.addWidget(monitoring_badge)

        self.submit_btn = QPushButton("Submit Exam")
        self.submit_btn.setFixedHeight(38)
        self.submit_btn.setEnabled(False)
        self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {_NAVY};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 0 20px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: {_NAVY_HOVER};
            }}
            QPushButton:disabled {{
                background-color: #9CA3AF;
            }}
            """
        )
        self.submit_btn.clicked.connect(self.submit_clicked)
        layout.addWidget(self.submit_btn)


class _LiveFeedWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 12)
        layout.setSpacing(0)

        self._container = QFrame()
        self._container.setStyleSheet("background: #1a1a2e; border-radius: 10px;")
        self._container.setFixedHeight(175)
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self._video_widget = QVideoWidget()
        self._video_widget.setStyleSheet("background: #1a1a2e; border-radius: 10px;")
        container_layout.addWidget(self._video_widget)

        self._placeholder = QLabel("Camera preview available during live exam")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(
            "background: transparent; color: rgba(255,255,255,180); font-size: 13px;"
        )
        self._placeholder.setParent(self._container)

        self._live_badge = QLabel("● LIVE")
        self._live_badge.setStyleSheet(
            "background-color: rgba(0,0,0,180); color: #4ADE80;"
            "font-size: 11px; font-weight: 800; border-radius: 8px;"
            "padding: 3px 8px;"
        )
        self._live_badge.setParent(self._container)

        self._name_lbl = QLabel("Student Preview")
        self._name_lbl.setStyleSheet(
            "background-color: rgba(0,0,0,160); color: white;"
            "font-size: 12px; font-weight: 700; padding: 4px 10px;"
        )
        self._name_lbl.setParent(self._container)

        layout.addWidget(self._container)

        self._camera: QCamera | None = None
        self._session: QMediaCaptureSession | None = None
        self._camera_started = False

    def set_student_name(self, name: str) -> None:
        self._name_lbl.setText(name or "Student Preview")
        self._reposition_overlays()

    def start_camera(self) -> None:
        if self._camera_started:
            return
        devices = QMediaDevices.videoInputs()
        if not devices:
            return
        self._camera = QCamera(devices[0])
        self._session = QMediaCaptureSession()
        self._session.setCamera(self._camera)
        self._session.setVideoOutput(self._video_widget)
        self._camera.start()
        self._camera_started = True
        self._placeholder.hide()

    def stop_camera(self) -> None:
        if self._camera is not None:
            self._camera.stop()
        self._camera_started = False
        self._placeholder.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        width = self._container.width()
        height = self._container.height()
        self._placeholder.setGeometry(0, 0, width, height)

        self._live_badge.adjustSize()
        self._live_badge.move(width - self._live_badge.width() - 10, 10)

        self._name_lbl.adjustSize()
        self._name_lbl.move(0, height - self._name_lbl.height())
        self._name_lbl.setFixedWidth(width)


class _GuardRow(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: #F7F9FC; border-radius: 8px;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        text = QLabel(label)
        text.setStyleSheet(f"font-size: 13px; color: {_TXT}; background: transparent;")
        self._icon = QLabel("✓")
        self._icon.setStyleSheet(
            f"color: {_GREEN}; font-size: 16px; font-weight: 900; background: transparent;"
        )
        layout.addWidget(text)
        layout.addStretch(1)
        layout.addWidget(self._icon)

    def set_ok(self, ok: bool) -> None:
        if ok:
            self._icon.setText("✓")
            self._icon.setStyleSheet(
                f"color: {_GREEN}; font-size: 16px; font-weight: 900; background: transparent;"
            )
            return
        self._icon.setText("✗")
        self._icon.setStyleSheet(
            f"color: {_RED_WARN}; font-size: 16px; font-weight: 900; background: transparent;"
        )


class _SystemGuardWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 12)
        layout.setSpacing(6)

        self._rows: dict[str, _GuardRow] = {}
        for label in ("Clipboard Locked", "External Display", "Window Focus"):
            row = _GuardRow(label)
            self._rows[label] = row
            layout.addWidget(row)

    def set_status(self, label: str, ok: bool) -> None:
        row = self._rows.get(label)
        if row is not None:
            row.set_ok(ok)


class _ChatBubble(QFrame):
    def __init__(
        self,
        text: str,
        sender: str,
        time_str: str,
        is_student: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        bubble = QFrame()
        bubble.setStyleSheet(
            f"background-color: {_NAVY if is_student else '#EAECF2'}; border-radius: 12px;"
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 10)
        bubble_layout.setSpacing(4)

        message = QLabel(text)
        message.setWordWrap(True)
        message.setStyleSheet(
            f"font-size: 13px; color: {'white' if is_student else _TXT}; background: transparent;"
        )
        bubble_layout.addWidget(message)

        meta = QLabel(f"{time_str}  •  {sender}" if not is_student else time_str)
        meta.setStyleSheet(
            f"font-size: 11px; color: {'rgba(255,255,255,160)' if is_student else _TXT_MUTED}; background: transparent;"
        )
        meta.setAlignment(
            Qt.AlignmentFlag.AlignRight if is_student else Qt.AlignmentFlag.AlignLeft
        )
        bubble_layout.addWidget(meta)

        bubble.setMaximumWidth(230)

        if is_student:
            outer.addStretch(1)
            outer.addWidget(bubble)
        else:
            outer.addWidget(bubble)
            outer.addStretch(1)


class _SupportChatWidget(QWidget):
    message_send_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 8, 12, 8)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch(1)

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(_divider())

        input_row = QWidget()
        input_row.setStyleSheet(f"background-color: {_BG_WHITE};")
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message Proctor...")
        self._input.setStyleSheet(
            f"border: none; background: transparent; font-size: 14px; color: {_TXT};"
        )
        self._input.returnPressed.connect(self._send)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(32, 32)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(
            f"background-color: {_NAVY}; color: white; border: none; border-radius: 16px; font-size: 14px;"
        )
        send_btn.clicked.connect(self._send)

        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(send_btn)
        layout.addWidget(input_row)

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self.message_send_requested.emit(text)
        self._input.clear()

    def append_message(self, text: str, sender: str, time_str: str, is_student: bool) -> None:
        bubble = _ChatBubble(text, sender, time_str, is_student)
        self._content_layout.insertWidget(self._content_layout.count() - 1, bubble)
        scrollbar = self._scroll.verticalScrollBar()
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, lambda: scrollbar.setValue(scrollbar.maximum()))


class _RightPanel(QWidget):
    message_send_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(_PANEL_W)
        self.setStyleSheet(
            f"background-color: {_BG_WHITE};"
            f"border-left: 1px solid {_BORDER};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_section_title("Live Feed"))
        self.live_feed = _LiveFeedWidget()
        layout.addWidget(self.live_feed)

        layout.addWidget(_divider())
        layout.addWidget(_section_title("System Guard"))
        self.system_guard = _SystemGuardWidget()
        layout.addWidget(self.system_guard)

        layout.addWidget(_divider())
        layout.addWidget(_section_title("Support Chat"))
        self.chat = _SupportChatWidget()
        layout.addWidget(self.chat, 1)

        self.chat.message_send_requested.connect(self.message_send_requested)
        self.chat.append_message(
            "Hello, I'm your proctor today. Please ensure your face remains visible in the frame at all times.",
            "Proctor Sarah",
            "10:02 AM",
            is_student=False,
        )


class _QuestionHeader(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 16)
        layout.setSpacing(8)

        self._progress_lbl = QLabel("Question 1 of 1")
        self._progress_lbl.setStyleSheet(
            f"font-size: 13px; color: {_TXT_MUTED}; background: transparent;"
        )
        layout.addWidget(self._progress_lbl)

    def set_progress(self, current: int, total: int) -> None:
        self._progress_lbl.setText(f"Question {current} of {total}")


class _NavBar(QWidget):
    prev_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 40)

        self.prev_btn = QPushButton("← Previous Question")
        self.prev_btn.setEnabled(False)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {_TXT};
                border: none;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ color: {_NAVY}; }}
            QPushButton:disabled {{ color: {_TXT_MUTED}; }}
            """
        )
        self.prev_btn.clicked.connect(self.prev_clicked)

        self.next_btn = QPushButton("Next Question →")
        self.next_btn.setEnabled(False)
        self.next_btn.setFixedHeight(46)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {_NAVY};
                color: white;
                border: none;
                border-radius: 14px;
                padding: 0 28px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton:hover {{ background-color: {_NAVY_HOVER}; }}
            QPushButton:disabled {{ background-color: #9CA3AF; }}
            """
        )
        self.next_btn.clicked.connect(self.next_clicked)

        layout.addWidget(self.prev_btn)
        layout.addStretch(1)
        layout.addWidget(self.next_btn)

    def set_enabled(self, prev: bool, next_: bool) -> None:
        self.prev_btn.setEnabled(prev)
        self.next_btn.setEnabled(next_)


class ExamUI(QWidget):
    prev_requested = Signal()
    next_requested = Signal()
    submit_requested = Signal()
    chat_message_requested = Signal(str)

    def __init__(self, questions: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.questions = questions
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(f"background-color: {_BG_PAGE};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._top_bar = _TopBar()
        self._top_bar.submit_clicked.connect(self.submit_requested)
        root.addWidget(self._top_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet(f"background-color: {_BG_PAGE};")

        left = QWidget()
        left.setStyleSheet(f"background-color: {_BG_PAGE};")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._question_header = _QuestionHeader()
        left_layout.addWidget(self._question_header)

        self.question_stack = QStackedWidget()
        self.question_stack.setStyleSheet("background: transparent;")
        left_layout.addWidget(self.question_stack, 1)

        self._nav_bar = _NavBar()
        self._nav_bar.prev_clicked.connect(self.prev_requested)
        self._nav_bar.next_clicked.connect(self.next_requested)
        left_layout.addWidget(self._nav_bar)

        left_scroll.setWidget(left)

        self._right_panel = _RightPanel()
        self._right_panel.message_send_requested.connect(self._on_student_send)

        body.addWidget(left_scroll, 1)
        body.addWidget(self._right_panel)

        body_host = QWidget()
        body_host.setLayout(body)
        root.addWidget(body_host, 1)

    @Slot(str)
    def update_timer(self, text: str) -> None:
        raw = text.replace("Time remaining:", "").strip()
        self._top_bar.timer_lbl.setText(raw or text)

    @Slot(bool)
    def set_timer_warning(self, warning: bool) -> None:
        color = _RED_WARN if warning else _TXT
        self._top_bar.timer_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {color}; background: transparent;"
        )

    @Slot(int, int)
    def update_progress(self, current: int, total: int) -> None:
        self._question_header.set_progress(current, total)

    @Slot(bool, bool, bool)
    def set_navigation_enabled(self, prev: bool, next_: bool, submit: bool) -> None:
        self._nav_bar.set_enabled(prev, next_)
        self._top_bar.submit_btn.setEnabled(submit)

    @Slot(str, str, str)
    def append_chat_message(self, text: str, sender: str, time_str: str) -> None:
        self._right_panel.chat.append_message(text, sender, time_str, is_student=False)

    @Slot(str, bool)
    def set_guard_status(self, label: str, ok: bool) -> None:
        self._right_panel.system_guard.set_status(label, ok)

    @Slot(str)
    def set_student_name(self, name: str) -> None:
        self._right_panel.live_feed.set_student_name(name)

    def start_camera(self) -> None:
        self._right_panel.live_feed.start_camera()

    def stop_camera(self) -> None:
        self._right_panel.live_feed.stop_camera()

    def _on_student_send(self, text: str) -> None:
        from datetime import datetime

        timestamp = datetime.now().strftime("%I:%M %p")
        self._right_panel.chat.append_message(text, "You", timestamp, is_student=True)
        self.chat_message_requested.emit(text)
