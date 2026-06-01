from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from client.modules.examiner_dashboard.views.dashboard_shell import DashboardCard
from client.modules.examiner_dashboard.scripts.examiner_overview_models import ExamRowSpec
from client.modules.examiner_dashboard.scripts.examiner_overview_theme import (
    BORDER,
    NAVY,
    NAVY_HOVER,
    STATUS_ACTIVE_BG,
    STATUS_ACTIVE_FG,
    STATUS_OTHER_BG,
    STATUS_OTHER_FG,
    STATUS_SCHED_BG,
    STATUS_SCHED_FG,
    TXT_MUTED,
    TXT_PRIMARY,
    TXT_SECONDARY,
)


_COL_WIDTHS = {
    "name": None,
    "status": 120,
    "duration": 120,
    "students": 130,
    "action": 170,
}
_H_PAD = 24
_COL_GAP = 0


class _StatusBadge(QLabel):
    def __init__(self, status: str, parent: QWidget | None = None) -> None:
        super().__init__(status, parent)
        normalized = status.lower().strip()
        if normalized in {"active", "live"}:
            bg, fg = STATUS_ACTIVE_BG, STATUS_ACTIVE_FG
        elif normalized == "scheduled":
            bg, fg = STATUS_SCHED_BG, STATUS_SCHED_FG
        else:
            bg, fg = STATUS_OTHER_BG, STATUS_OTHER_FG
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg};"
            f"border-radius: 8px; padding: 5px 14px;"
            f"font-size: 13px; font-weight: 700;"
        )
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _AvatarStack(QWidget):
    def __init__(self, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        size = 28
        offset = -8
        colors = ["#4A6FA5", "#5A8270"]

        shown = min(count, 2)
        for index in range(shown):
            circle = QLabel()
            circle.setFixedSize(size, size)
            circle.setStyleSheet(
                f"background-color: {colors[index % len(colors)]};"
                f"border-radius: {size // 2}px;"
                f"border: 2px solid white;"
            )
            if index > 0:
                layout.addSpacing(offset)
            layout.addWidget(circle)

        if count > 2:
            overflow = QLabel(f"+{count - 2}")
            overflow.setFixedSize(size, size)
            overflow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            overflow.setStyleSheet(
                "background-color: #E8EEF7;"
                "color: #3F5070;"
                f"border-radius: {size // 2}px;"
                "border: 2px solid white;"
                "font-size: 11px; font-weight: 800;"
            )
            layout.addSpacing(offset)
            layout.addWidget(overflow)

        layout.addStretch(1)


class _ExamRow(QFrame):
    delete_requested = Signal(str)
    status_change_requested = Signal(str, str)

    def __init__(self, spec: ExamRowSpec, last: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: transparent;")

        root = QHBoxLayout(self)
        root.setContentsMargins(_H_PAD, 18, _H_PAD, 18)
        root.setSpacing(_COL_GAP)

        name_w = QWidget()
        name_w.setStyleSheet("background: transparent;")
        name_lay = QVBoxLayout(name_w)
        name_lay.setContentsMargins(0, 0, 0, 0)
        name_lay.setSpacing(3)

        name_lbl = QLabel(spec.exam_name)
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {TXT_PRIMARY}; background: transparent;"
        )
        id_lbl = QLabel(f"Join Code: {spec.join_code}")
        id_lbl.setStyleSheet(
            f"font-size: 12px; color: {TXT_MUTED}; background: transparent;"
        )
        name_lay.addWidget(name_lbl)
        name_lay.addWidget(id_lbl)
        root.addWidget(name_w, 1)

        status_w = QWidget()
        status_w.setFixedWidth(_COL_WIDTHS["status"])
        status_w.setStyleSheet("background: transparent;")
        sl = QHBoxLayout(status_w)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(
            _StatusBadge(spec.status),
            0,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        root.addWidget(status_w)

        dur_w = QWidget()
        dur_w.setFixedWidth(_COL_WIDTHS["duration"])
        dur_w.setStyleSheet("background: transparent;")
        dl = QHBoxLayout(dur_w)
        dl.setContentsMargins(0, 0, 0, 0)
        dur_lbl = QLabel(spec.duration)
        dur_lbl.setStyleSheet(
            f"font-size: 14px; color: {TXT_PRIMARY}; background: transparent;"
        )
        dl.addWidget(dur_lbl, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        root.addWidget(dur_w)

        stu_w = QWidget()
        stu_w.setFixedWidth(_COL_WIDTHS["students"])
        stu_w.setStyleSheet("background: transparent;")
        stl = QHBoxLayout(stu_w)
        stl.setContentsMargins(0, 0, 0, 0)

        if spec.status.lower() == "live" and spec.avatar_count > 0:
            stl.addWidget(
                _AvatarStack(spec.avatar_count),
                0,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            )
        else:
            stu_lbl = QLabel(spec.students)
            stu_lbl.setStyleSheet(
                f"font-size: 14px; color: {TXT_PRIMARY}; background: transparent;"
            )
            stl.addWidget(
                stu_lbl,
                0,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            )

        root.addWidget(stu_w)

        act_w = QWidget()
        act_w.setFixedWidth(_COL_WIDTHS["action"])
        act_w.setStyleSheet("background: transparent;")
        act_layout = QHBoxLayout(act_w)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(8)
        act_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        normalized_status = spec.status.lower().strip()
        if normalized_status in {"draft", "scheduled"} and spec.exam_id:
            live_btn = QPushButton("Go Live")
            live_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            live_btn.setFixedHeight(30)
            live_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {NAVY};
                    color: white;
                    border: none;
                    border-radius: 9px;
                    padding: 0 10px;
                    font-size: 12px;
                    font-weight: 800;
                }}
                QPushButton:hover {{
                    background-color: {NAVY_HOVER};
                }}
                """
            )
            live_btn.clicked.connect(
                lambda: self.status_change_requested.emit(spec.exam_id, "live")
            )
            act_layout.addWidget(live_btn)

        if normalized_status == "draft" and spec.exam_id:
            delete_btn = QPushButton("Delete")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setFixedHeight(30)
            delete_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #FFF1F2;
                    color: #BE123C;
                    border: 1px solid #FDA4AF;
                    border-radius: 9px;
                    padding: 0 10px;
                    font-size: 12px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background-color: #FFE4E6;
                }
                """
            )
            delete_btn.clicked.connect(lambda: self.delete_requested.emit(spec.exam_id))
            act_layout.addWidget(delete_btn)

        if normalized_status == "live" and spec.exam_id:
            close_btn = QPushButton("Close")
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.setFixedHeight(30)
            close_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #FFF1F2;
                    color: #BE123C;
                    border: 1px solid #FDA4AF;
                    border-radius: 9px;
                    padding: 0 10px;
                    font-size: 12px;
                    font-weight: 800;
                }
                QPushButton:hover {
                    background-color: #FFE4E6;
                }
                """
            )
            close_btn.clicked.connect(
                lambda: self.status_change_requested.emit(spec.exam_id, "closed")
            )
            act_layout.addWidget(close_btn)
            
        root.addWidget(act_w)


class ExamManagementCard(DashboardCard):
    new_schedule_clicked = Signal()
    delete_draft_requested = Signal(str)
    status_change_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        root = self.content_layout
        root.setSpacing(0)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(_H_PAD, 10, _H_PAD, 14)

        title = QLabel("Exam Management")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {TXT_PRIMARY}; background: transparent;"
        )
        header_row.addWidget(title)
        header_row.addStretch(1)

        filter_lbl = QLabel("Filter")
        filter_lbl.setStyleSheet(
            f"font-size: 14px; color: {TXT_SECONDARY}; background: transparent; margin-right: 12px;"
        )
        header_row.addWidget(filter_lbl)

        new_btn = QPushButton("New Schedule")
        new_btn.setFixedHeight(38)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {NAVY};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 0 18px;
                font-size: 14px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: {NAVY_HOVER};
            }}
            """
        )
        new_btn.clicked.connect(self.new_schedule_clicked)
        header_row.addWidget(new_btn)
        root.addLayout(header_row)

        col_header = QFrame()
        col_header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        col_header.setStyleSheet(
            f"background-color: #F7FAFD;"
        )
        ch_lay = QHBoxLayout(col_header)
        ch_lay.setContentsMargins(_H_PAD, 10, _H_PAD, 10)
        ch_lay.setSpacing(0)

        def _hdr(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "font-size: 11px; font-weight: 800; color: #3F4E63;"
                "letter-spacing: 1px; background: transparent;"
            )
            return label

        ch_lay.addWidget(_hdr("EXAM NAME"), 1)
        for key, label_text in (
            ("status", "STATUS"),
            ("duration", "DURATION"),
            ("students", "STUDENTS"),
            ("action", "ACTION"),
        ):
            col = QWidget()
            col.setFixedWidth(_COL_WIDTHS[key])
            col.setStyleSheet("background: transparent;")
            col_layout = QHBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.addWidget(_hdr(label_text))
            ch_lay.addWidget(col)

        root.addWidget(col_header)

        self._rows_host = QWidget()
        self._rows_host.setStyleSheet("background: transparent;")
        self._rows_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_scroll = QScrollArea()
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._rows_scroll.setStyleSheet("background: transparent;")
        self._rows_scroll.setWidget(self._rows_host)
        root.addWidget(self._rows_scroll, 1)
        self.set_rows([])

    def set_rows(self, rows: list[ExamRowSpec]) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not rows:
            empty = QLabel("No exams created yet.")
            empty.setStyleSheet(
                f"padding: 18px {_H_PAD}px; font-size: 13px; color: {TXT_SECONDARY}; background: transparent;"
            )
            self._rows_layout.addWidget(empty)
            self._rows_layout.addStretch(1)
            return
        for index, row_spec in enumerate(rows):
            row = _ExamRow(row_spec, last=(index == len(rows) - 1))
            row.delete_requested.connect(self.delete_draft_requested)
            row.status_change_requested.connect(self.status_change_requested)
            self._rows_layout.addWidget(row)
        self._rows_layout.addStretch(1)
