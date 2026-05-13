"""
client/modules/dashboard/student_dashboard.py
Student dashboard UI + logic for classes/exams/schedule/analysis.
"""

import logging
import os
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import requests
import websockets
from PySide6.QtCore import Qt, Signal, Slot, QSize, QThread, QTimer
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QButtonGroup,
    QGridLayout,
    QStackedWidget,
    QComboBox,
)
from PySide6.QtSvg import QSvgRenderer

from client.config import BASE_URL, CAMERA_INDEX, WS_URL
from client.core.api_worker import ApiWorker
from client.core.contracts import (
    normalize_class_payload,
    normalize_exam_payload,
    normalize_question_list,
    normalize_session_payload,
    resolve_optional_id,
)
from client.modules.dashboard.class_view import ClassView
from client.modules.dashboard.student_exam_view import StudentExamView
from client.modules.common.loading_spinner import SpinnerOverlay
from client.modules.common.design_tokens import (
    COLOR_BG_APP,
    COLOR_BG_CARD,
    COLOR_BG_SOFT,
    COLOR_BORDER_SOFT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_TEXT_DARK,
    COLOR_TEXT_HEAD,
    COLOR_TEXT_MUTED,
    FONT_FAMILY,
)

logger = logging.getLogger(__name__)


def _load_svg_icon(icon_name: str, color: str = "") -> Optional[QIcon]:
    """Load an SVG icon from assets/Icon folder and render to QIcon. Returns None if file not found."""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        icon_path = project_root / "assets" / "Icon" / f"{icon_name}.svg"
        if icon_path.exists():
            renderer = QSvgRenderer(str(icon_path))
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
    except Exception:
        pass
    return None
class ClassRowWidget(QWidget):
    def __init__(self, name: str, status: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        frame = QFrame()
        frame.setObjectName("rowFrame")
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 7, 10, 7)
        frame_layout.setSpacing(12)

        # Circular initial
        circle_label = QLabel(name[:1].upper())
        circle_label.setFixedSize(24, 24)
        circle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle_label.setStyleSheet(
            f"background-color: {COLOR_BG_SOFT}; color: {COLOR_PRIMARY}; border-radius: 12px; font-size: 14px; font-weight: 700;"
        )
        frame_layout.addWidget(circle_label)

        # Name/Status block
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        name_label = QLabel(name)
        name_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_HEAD};"
        )
        status_label = QLabel(str(status))
        status_label.setStyleSheet(
            f"font-size: 12px; color: {COLOR_TEXT_MUTED};"
        )
        info_layout.addWidget(name_label)
        info_layout.addWidget(status_label)
        frame_layout.addLayout(info_layout)

        frame_layout.addStretch(1)

        # Play icon/button
        play_btn = QPushButton()
        play_btn.setFixedSize(28, 28)
        play_btn.setObjectName("playIconBtn")
        play_icon = _load_svg_icon("play")
        if play_icon is not None:
            play_btn.setIcon(play_icon)
            play_btn.setIconSize(QSize(18, 18))
        else:
            play_btn.setText("▶")
        play_btn.setStyleSheet(
            f"border: none; background: transparent; color: {COLOR_PRIMARY};"
        )
        frame_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignRight)

        frame.setStyleSheet("""
            #rowFrame {
                background-color: %s;
                border: 1px solid %s;
                border-radius: 12px;
            }
            #rowFrame:hover {
                border-color: %s;
            }
        """ % (COLOR_BG_SOFT, COLOR_BORDER_SOFT, COLOR_PRIMARY))
        layout.addWidget(frame)


class ExamRowWidget(QWidget):
    def __init__(self, title: str, class_name: str, status: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        frame = QFrame()
        frame.setObjectName("rowFrame")
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 7, 10, 7)
        frame_layout.setSpacing(12)

        # Circular initial (from exam title)
        circle_label = QLabel(title[:1].upper())
        circle_label.setFixedSize(24, 24)
        circle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        circle_label.setStyleSheet(
            f"background-color: {COLOR_BG_SOFT}; color: {COLOR_PRIMARY}; border-radius: 12px; font-size: 14px; font-weight: 700;"
        )
        frame_layout.addWidget(circle_label)

        # Title/Class/Status block
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {COLOR_TEXT_HEAD};"
        )
        class_status = QLabel(f"{class_name} · {status}")
        class_status.setStyleSheet(
            f"font-size: 12px; color: {COLOR_TEXT_MUTED};"
        )
        info_layout.addWidget(title_label)
        info_layout.addWidget(class_status)
        frame_layout.addLayout(info_layout)

        frame_layout.addStretch(1)

        # Play icon/button
        play_btn = QPushButton()
        play_btn.setFixedSize(28, 28)
        play_btn.setObjectName("playIconBtn")
        play_icon = _load_svg_icon("play")
        if play_icon is not None:
            play_btn.setIcon(play_icon)
            play_btn.setIconSize(QSize(18, 18))
        else:
            play_btn.setText("▶")
        play_btn.setStyleSheet(
            f"border: none; background: transparent; color: {COLOR_PRIMARY};"
        )
        frame_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignRight)

        frame.setStyleSheet("""
            #rowFrame {
                background-color: %s;
                border: 1px solid %s;
                border-radius: 12px;
            }
            #rowFrame:hover {
                border-color: %s;
            }
        """ % (COLOR_BG_CARD, COLOR_BORDER_SOFT, COLOR_PRIMARY))
        layout.addWidget(frame)


# ── HTTP fetch helpers (module-level — safe to call from any QThread) ────────

def _http_fetch_dashboard(headers: dict) -> dict:
    """All 4 refresh GETs in one go. Returns raw JSON bundles."""
    result: dict = {}
    try:
        r = requests.get(f"{BASE_URL}/sessions/my-performance", headers=headers, timeout=10)
        result["performance"] = r.json() if r.status_code == 200 else None
    except requests.RequestException:
        result["performance"] = None
    try:
        r = requests.get(f"{BASE_URL}/classes/enrolled", headers=headers, timeout=10)
        result["classes"] = (r.status_code, r.json() if r.status_code == 200 else r.text)
    except requests.RequestException as exc:
        result["classes"] = (-1, str(exc))
    try:
        r = requests.get(f"{BASE_URL}/exams", headers=headers, timeout=10)
        result["schedule"] = r.json() if r.status_code == 200 else None
    except requests.RequestException:
        result["schedule"] = None
    try:
        r = requests.get(f"{BASE_URL}/sessions/my-history", headers=headers, timeout=10)
        result["history"] = r.json() if r.status_code == 200 else []
    except requests.RequestException:
        result["history"] = []
    return result


def _http_fetch_exams(headers: dict, class_id: str) -> dict:
    try:
        r = requests.get(
            f"{BASE_URL}/exams",
            headers=headers,
            params={"class_id": class_id},
            timeout=10,
        )
        return {"status": r.status_code, "data": r.json() if r.status_code == 200 else r.text}
    except requests.RequestException as exc:
        return {"status": -1, "data": str(exc)}


def _http_join_class(headers: dict, code: str) -> dict:
    try:
        r = requests.post(
            f"{BASE_URL}/classes/join-by-code/{code}",
            headers=headers,
            timeout=10,
        )
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text}
        return {"status": r.status_code, "data": body}
    except requests.RequestException as exc:
        return {"status": -1, "data": {"detail": str(exc)}}


def _http_fetch_attempt(headers: dict, exam_id: str, session_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/exams/{exam_id}", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"error": f"Failed loading exam: {r.text[:300]}"}
        exam = r.json()
        r = requests.get(f"{BASE_URL}/exams/{exam_id}/questions", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"error": f"Failed loading questions: {r.text[:300]}"}
        questions = r.json()
        r = requests.get(f"{BASE_URL}/sessions/{session_id}/answers", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"error": f"Failed loading answers: {r.text[:300]}"}
        return {"exam": exam, "questions": questions, "answers": r.json()}
    except requests.RequestException as exc:
        return {"error": str(exc)}


def _http_start_exam(headers: dict, exam_id: str) -> dict:
    try:
        r = requests.get(f"{BASE_URL}/exams/{exam_id}", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"error": f"Failed to load exam: {r.text[:300]}"}
        exam = r.json()

        r = requests.post(
            f"{BASE_URL}/sessions/start",
            headers=headers,
            json={"exam_id": exam_id},
            timeout=12,
        )
        if r.status_code not in (200, 201):
            return {"error": f"Cannot start exam: {r.text[:300]}"}
        session = r.json()

        r = requests.get(f"{BASE_URL}/exams/{exam_id}/questions", headers=headers, timeout=10)
        if r.status_code != 200:
            return {"error": f"Failed to load questions: {r.text[:300]}"}
        return {"exam": exam, "session": session, "questions": r.json()}
    except requests.RequestException as exc:
        return {"error": str(exc)}


def _http_submit_exam(
    headers: dict,
    session_id: str,
    exam_id: str,
    answers: list,
    token: str,
    ws_url: str,
) -> dict:
    """Answer-sync via WebSocket then POST /submit. Safe to call from a QThread."""
    async def _sync() -> tuple[bool, str]:
        ws_uri = f"{ws_url}/ws/student/{session_id}/{exam_id}"
        try:
            async with websockets.connect(ws_uri, ping_interval=None, open_timeout=8) as ws:
                await ws.send(json.dumps({"type": "auth", "token": token}))
                auth_raw = await asyncio.wait_for(ws.recv(), timeout=8)
                auth_msg = json.loads(auth_raw)
                if auth_msg.get("type") != "auth_ok":
                    return False, "websocket auth rejected"
                await ws.send(json.dumps({"type": "answer_sync", "answers": answers}))
                await ws.send(json.dumps({
                    "type": "session_state",
                    "state": "active",
                    "client_time": datetime.utcnow().isoformat(),
                }))
            return True, ""
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    sync_ok, sync_error = asyncio.run(_sync())
    if not sync_ok:
        return {"ok": False, "error": f"Answer sync failed: {sync_error}"}

    try:
        r = requests.post(
            f"{BASE_URL}/sessions/{session_id}/submit",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return {"ok": True}
        try:
            detail = str((r.json() or {}).get("detail", f"Server error ({r.status_code})"))
        except Exception:
            detail = f"Server error ({r.status_code})"
        return {"ok": False, "error": f"Submission failed: {detail}"}
    except requests.RequestException:
        return {"ok": False, "error": "Network error during submission."}


# ─────────────────────────────────────────────────────────────────────────────

class StudentDashboard(QWidget):
    start_exam_requested = Signal(dict, dict, list, str)  # session, exam, questions, token
    path_changed = Signal(str)  # classes | schedule | analysis

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("studentDashboardRoot")
        self._token: str = ""
        self._user_id: str = ""
        self._full_name: str = ""

        self._welcome = QLabel("Student Dashboard")
        self._subtitle = QLabel("")
        self._status = QLabel("")

        self._join_input = QLineEdit()
        self._join_btn = QPushButton("Join Class")
        self._refresh_btn = QPushButton("Refresh")
        self._start_exam_btn = QPushButton("Start Selected Exam")
        self._classes_list = QListWidget()
        self._upcoming_exams_home_list = QListWidget()
        self._attempted_exams_home_list = QListWidget()
        self._schedule_list = QListWidget()
        self._analysis_list = QListWidget()
        self._analysis_filter = QComboBox()
        self._analysis_rows: list[dict] = []
        self._selected_class: dict = {}

        # Workers — stored as instance vars to prevent GC mid-run
        self._refresh_worker:  Optional[ApiWorker] = None
        self._exams_worker:    Optional[ApiWorker] = None
        self._join_worker:     Optional[ApiWorker] = None
        self._attempt_worker:  Optional[ApiWorker] = None
        self._start_worker:    Optional[ApiWorker] = None
        self._submit_worker:   Optional[ApiWorker] = None


        self._metric_marks = QLabel("--")
        self._metric_completed = QLabel("--")
        self._metric_active = QLabel("--")
        self._metric_integrity = QLabel("--")
        self._metric_total = QLabel("--")
        self._profile_name = QLabel("Student")
        self._profile_role = QLabel("Student")
        self._avatar = QLabel("ST")

        self._schedule_label = QLabel("Schedule view will show upcoming classes and exams.")
        self._class_name_by_id: dict[str, str] = {}

        self._nav_group = QButtonGroup(self)
        self._nav_classes_btn = QPushButton("Home")
        self._nav_schedule_btn = QPushButton("Schedule")
        self._nav_analysis_btn = QPushButton("Analysis")
        self._nav_icons = {
            "classes": "graduation-cap",
            "schedule": "calendar-fold",
            "analysis": "file-chart-line",
        }
        self._content_stack = QStackedWidget()
        self._classes_page = QWidget()
        self._class_view = ClassView(self._apply_shadow)
        self._exam_view = StudentExamView(self._apply_shadow)
        self._class_detail_page = self._class_view
        self._exam_page = self._exam_view
        self._schedule_page = QWidget()
        self._analysis_page = QWidget()

        self._build()
        self._wire()
        # Single overlay reused for every internal page switch
        self._content_spinner = SpinnerOverlay(parent=self._content_stack)

    def _apply_shadow(self, widget: QWidget):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor

        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(20)
        effect.setOffset(0, 2)
        color = QColor(0, 0, 0, int(255 * 0.03))  # 3% opacity black
        effect.setColor(color)
        widget.setGraphicsEffect(effect)

    def _build(self):
        self.setStyleSheet(f"""
            #studentDashboardRoot {{
                background-color: {COLOR_BG_APP};
                font-family: {FONT_FAMILY};
            }}

            /* All Cards */
            #sidebarCard, #mainCard, #rightRailCard, #classesCard, #examsCard, #profileCard, #metricsCard {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 16px;
            }}

            /* Fix join card background and text in dark mode */
            #joinCard {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 16px;
            }}
            #joinCard QLabel {{
                color: {COLOR_TEXT_DARK};
            }}

            /* Prevent dark mode bleed-through for central content */
            QStackedWidget, QStackedWidget > QWidget {{
                background-color: transparent;
            }}

            #titleLabel {{
                font-size: 42px;
                font-weight: 700;
                color: {COLOR_TEXT_HEAD};
            }}
            #subtitleLabel {{
                font-size: 13px;
                color: {COLOR_TEXT_MUTED};
            }}
            #sectionHeading {{
                font-size: 20px;
                font-weight: 700;
                color: {COLOR_TEXT_HEAD};
            }}
            #miniHeading {{
                font-size: 14px;
                font-weight: 600;
                color: {COLOR_TEXT_HEAD};
            }}
            #statusLabel {{
                font-size: 13px;
                color: {COLOR_TEXT_MUTED};
                padding-left: 4px;
            }}

            /* List panels: classes + exams match card surfaces and separate from page bg */
            #classesList, #examsList {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 12px;
                color: {COLOR_TEXT_DARK};
                font-size: 13px;
                padding: 8px;
            }}
            #scheduleList, #analysisList {{
                background-color: {COLOR_BG_CARD};
                border: none;
                border-radius: 12px;
                color: {COLOR_TEXT_DARK};
                font-size: 13px;
                padding: 8px;
            }}
            #classesList::item, #examsList::item, #scheduleList::item, #analysisList::item {{
                padding: 4px;
                border: none;
                background-color: transparent;
                color: inherit;
                border-radius: 0;
                margin: 0;
            }}
            #classesList::item:selected, #examsList::item:selected, #scheduleList::item:selected, #analysisList::item:selected {{
                background-color: {COLOR_BG_SOFT};
                color: {COLOR_PRIMARY};
            }}
     

            #analysisFilter {{
                background-color: {COLOR_BG_SOFT};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 9px;
                color: {COLOR_TEXT_DARK};
                min-width: 140px;
                padding: 6px 8px;
            }}
            #analysisFilter QAbstractItemView {{
                background-color: {COLOR_BG_CARD};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 4px;
                color: {COLOR_TEXT_DARK};
                selection-background-color: {COLOR_BG_SOFT};
                selection-color: {COLOR_PRIMARY};
                outline: none;
            }}

            /* Buttons */
            #primaryBtn {{
                background-color: {COLOR_PRIMARY};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                padding: 10px 18px;
            }}
            #primaryBtn:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }}

            #secondaryBtn {{
                background-color: transparent;
                color: {COLOR_TEXT_MUTED};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 10px 18px;
            }}
            #secondaryBtn:hover {{
                background-color: {COLOR_BG_SOFT};
                color: {COLOR_PRIMARY};
                border-color: {COLOR_PRIMARY};
            }}

            /* Nav Buttons */
            #navBtn {{
                background-color: transparent;
                color: {COLOR_TEXT_HEAD};
                border: none;
                border-left: 4px solid transparent;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                text-align: left;
                padding: 12px 16px;
            }}
            #navBtn:checked {{
                background-color: {COLOR_BG_SOFT};
                color: {COLOR_PRIMARY};
                border-left: 4px solid {COLOR_PRIMARY};
            }}
            #navBtn:hover:!checked {{
                background-color: {COLOR_BG_SOFT};
                color: {COLOR_TEXT_HEAD};
            }}

            #joinInput {{
                background-color: {COLOR_BG_SOFT};
                color: {COLOR_TEXT_DARK};
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 12px;
            }}
            #joinInput:focus {{ border: 1px solid {COLOR_PRIMARY}; }}

            #metricValue {{
                font-size: 22px;
                font-weight: 800;
                color: {COLOR_TEXT_HEAD};
            }}
            #metricLabel {{
                font-size: 11px;
                color: {COLOR_TEXT_MUTED};
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(18)

        sidebar_card = QFrame()
        sidebar_card.setObjectName("sidebarCard")
        sidebar_card.setFixedWidth(230)
        self._apply_shadow(sidebar_card)
        sidebar = QVBoxLayout(sidebar_card)
        sidebar.setContentsMargins(16, 14, 16, 14)
        sidebar.setSpacing(10)
        brand = QLabel("ExamApp")
        brand.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {COLOR_PRIMARY};")
        sidebar.addWidget(brand)
        sidebar.addSpacing(12)

        icon_size = QSize(20, 20)
        nav_buttons = [
            (self._nav_classes_btn, self._nav_icons["classes"]),
            (self._nav_schedule_btn, self._nav_icons["schedule"]),
            (self._nav_analysis_btn, self._nav_icons["analysis"]),
        ]
        for button, icon_name in nav_buttons:
            button.setCheckable(True)
            button.setObjectName("navBtn")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            icon = _load_svg_icon(icon_name)
            if icon:
                button.setIcon(icon)
                button.setIconSize(icon_size)
            self._nav_group.addButton(button)
            sidebar.addWidget(button)
        self._nav_classes_btn.setChecked(True)

        sidebar.addStretch(1)

        join_card = QFrame()
        join_card.setObjectName("joinCard")
   
        join_layout = QVBoxLayout(join_card)
        join_layout.setContentsMargins(12, 12, 12, 12)
        join_layout.setSpacing(8)
        join_title = QLabel("Join with code")
        join_title.setObjectName("miniHeading")
        join_layout.addWidget(join_title)
        self._join_input.setObjectName("joinInput")
        self._join_input.setPlaceholderText("Enter code (e.g. A1B2C3)")
        self._join_input.setMaxLength(12)
        join_layout.addWidget(self._join_input)
        join_btn_row = QHBoxLayout()
        join_btn_row.setSpacing(10)

        # Setup join button (text style)
        self._join_btn.setText("Join")
        self._join_btn.setObjectName("primaryBtn")

        # Setup refresh button (text style)
        self._refresh_btn.setText("Refresh")
        self._refresh_btn.setObjectName("secondaryBtn")

        join_btn_row.addWidget(self._join_btn, 1)
        join_btn_row.addWidget(self._refresh_btn, 1)
        join_layout.addLayout(join_btn_row)
        sidebar.addWidget(join_card)
        root.addWidget(sidebar_card)

        center_area = QVBoxLayout()
        center_area.setSpacing(12)
        header_card = QFrame()
        header_card.setObjectName("mainCard")
        self._apply_shadow(header_card)
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 18, 20, 18)
        self._welcome.setObjectName("titleLabel")
        self._subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(self._welcome)
        header_layout.addWidget(self._subtitle)
        center_area.addWidget(header_card)

        # Ensure background paints as intended in all themes
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Build the card pages before adding to the stack
        self._build_classes_page()
        self._build_schedule_page()
        self._build_analysis_page()

        # Prevent QWidget stacking inheriting dark backgrounds
        self._classes_page.setStyleSheet("background-color: transparent;")
        self._class_detail_page.setStyleSheet("background-color: transparent;")
        self._schedule_page.setStyleSheet("background-color: transparent;")
        self._analysis_page.setStyleSheet("background-color: transparent;")
        self._exam_page.setStyleSheet("background-color: transparent;")

        self._content_stack.addWidget(self._classes_page)
        self._content_stack.addWidget(self._class_detail_page)
        self._content_stack.addWidget(self._schedule_page)
        self._content_stack.addWidget(self._analysis_page)
        self._content_stack.addWidget(self._exam_page)
        center_area.addWidget(self._content_stack, 1)

        self._status.setObjectName("statusLabel")
        center_area.addWidget(self._status)
        root.addLayout(center_area, 1)

        right_rail_card = QFrame()
        right_rail_card.setObjectName("rightRailCard")
        right_rail_card.setFixedWidth(300)
        self._apply_shadow(right_rail_card)
        right_rail = QVBoxLayout(right_rail_card)
        right_rail.setContentsMargins(14, 14, 14, 14)
        right_rail.setSpacing(10)

        profile = QFrame()
        profile.setObjectName("profileCard")
        profile_col = QVBoxLayout(profile)
        profile_col.setContentsMargins(14, 12, 14, 12)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setFixedSize(66, 66)
        self._avatar.setStyleSheet(
            f"background-color: {COLOR_BG_SOFT}; color: {COLOR_PRIMARY}; border-radius: 33px; font-size: 24px; font-weight: 700;"
        )
   
        self._profile_name.setObjectName("miniHeading")
        self._profile_role.setObjectName("subtitleLabel")
        profile_col.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignHCenter)
        profile_col.addSpacing(2)
        profile_col.addWidget(self._profile_name, alignment=Qt.AlignmentFlag.AlignHCenter)
        profile_col.addWidget(self._profile_role, alignment=Qt.AlignmentFlag.AlignHCenter)
        right_rail.addWidget(profile)

        metrics = QFrame()
        metrics.setObjectName("metricsCard")
        metrics_grid = QGridLayout(metrics)
        metrics_grid.setContentsMargins(12, 10, 12, 10)
        metrics_grid.setHorizontalSpacing(18)
        metrics_grid.setVerticalSpacing(8)
        self._metric_marks.setObjectName("metricValue")
        self._metric_completed.setObjectName("metricValue")
        self._metric_active.setObjectName("metricValue")
        self._metric_integrity.setObjectName("metricValue")
        self._metric_total.setObjectName("metricValue")
        metrics_grid.addWidget(self._metric_marks, 0, 0)
        metrics_grid.addWidget(self._metric_completed, 0, 1)
        metrics_grid.addWidget(self._metric_active, 2, 0)
        metrics_grid.addWidget(self._metric_integrity, 2, 1)
        metrics_grid.addWidget(self._metric_total, 4, 0)
        labels = [
            QLabel("Avg Marks"),
            QLabel("Completed"),
            QLabel("Active"),
            QLabel("Integrity"),
            QLabel("Total Exams"),
        ]
        for lbl in labels:
            lbl.setObjectName("metricLabel")
        metrics_grid.addWidget(labels[0], 1, 0)
        metrics_grid.addWidget(labels[1], 1, 1)
        metrics_grid.addWidget(labels[2], 3, 0)
        metrics_grid.addWidget(labels[3], 3, 1)
        metrics_grid.addWidget(labels[4], 5, 0)
        right_rail.addWidget(metrics)
        root.addWidget(right_rail_card, alignment=Qt.AlignmentFlag.AlignTop)
   
    def _wire(self):
        self._join_btn.clicked.connect(self._join_class)
        self._refresh_btn.clicked.connect(self.refresh_data)
        self._classes_list.currentItemChanged.connect(self._on_class_changed)
        self._classes_list.itemClicked.connect(self._open_selected_class_page)
        self._start_exam_btn.clicked.connect(self._start_selected_exam)
        self._upcoming_exams_home_list.currentItemChanged.connect(self._update_exam_action_buttons)
        self._class_view.upcoming_exams_list.currentItemChanged.connect(self._update_exam_action_buttons)
        self._nav_classes_btn.clicked.connect(lambda: self._switch_path("home"))
        self._nav_schedule_btn.clicked.connect(lambda: self._switch_path("schedule"))
        self._nav_analysis_btn.clicked.connect(lambda: self._switch_path("analysis"))
        self._analysis_filter.currentIndexChanged.connect(self._render_analysis_rows)
        self._analysis_list.itemDoubleClicked.connect(self._open_attempt_answers)
        self._class_view.attempted_exams_list.itemDoubleClicked.connect(self._open_attempt_answers)
        self._upcoming_exams_home_list.itemDoubleClicked.connect(self._open_upcoming_exam_view)
        self._class_view.upcoming_exams_list.itemDoubleClicked.connect(self._open_upcoming_exam_view)
        self._class_view.join_exam_requested.connect(self._join_exam_from_class_view)
        self._attempted_exams_home_list.itemDoubleClicked.connect(self._open_attempt_answers)
        self._exam_view.back_requested.connect(self._return_from_exam_page)
        self._exam_view.submit_requested.connect(self._submit_exam_answers)

    def _switch_content(self, widget: QWidget):
        """Show spinner, switch internal page, hide spinner after first paint."""
        self._content_spinner.show()

        def _do():
            self._content_stack.setCurrentWidget(widget)
            QTimer.singleShot(80, self._content_spinner.hide)

        QTimer.singleShot(0, _do)


    def _build_classes_page(self):
        layout = QHBoxLayout(self._classes_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        classes_card = QFrame()
        classes_card.setObjectName("classesCard")
        self._apply_shadow(classes_card)
        classes_col = QVBoxLayout(classes_card)
        classes_col.setContentsMargins(16, 14, 16, 14)
        classes_heading = QLabel("Classes")
        classes_heading.setObjectName("sectionHeading")
        classes_col.addWidget(classes_heading)
        self._classes_list.setObjectName("classesList")
        self._classes_list.setMinimumHeight(180)
        classes_col.addWidget(self._classes_list, 1)
        layout.addWidget(classes_card, 1)

        exams_card = QFrame()
        exams_card.setObjectName("examsCard")
        self._apply_shadow(exams_card)
        exams_col = QVBoxLayout(exams_card)
        exams_col.setContentsMargins(16, 14, 16, 14)
        exams_heading = QLabel("Exams")
        exams_heading.setObjectName("sectionHeading")
        exams_col.addWidget(exams_heading)
        upcoming_label = QLabel("Upcoming Exams")
        upcoming_label.setObjectName("miniHeading")
        exams_col.addWidget(upcoming_label)
        self._upcoming_exams_home_list.setObjectName("examsList")
        self._upcoming_exams_home_list.setMinimumHeight(120)
        exams_col.addWidget(self._upcoming_exams_home_list, 1)
        attempted_label = QLabel("Attempted Exams")
        attempted_label.setObjectName("miniHeading")
        exams_col.addWidget(attempted_label)
        self._attempted_exams_home_list.setObjectName("analysisList")
        self._attempted_exams_home_list.setMinimumHeight(120)
        exams_col.addWidget(self._attempted_exams_home_list, 1)
        self._start_exam_btn.setStyleSheet(
            f"QPushButton {{ background-color: {COLOR_PRIMARY}; color: white; border-radius: 8px; font-weight: bold; padding: 10px; }} "
            f"QPushButton:hover {{ background-color: {COLOR_PRIMARY_HOVER}; }} "
            f"QPushButton:disabled {{ background-color: {COLOR_BORDER_SOFT}; color: {COLOR_TEXT_MUTED}; }}"
        )
        exams_col.addWidget(self._start_exam_btn)
        layout.addWidget(exams_card, 1)

    def _build_schedule_page(self):
        layout = QVBoxLayout(self._schedule_page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("mainCard")
        self._apply_shadow(card)
        col = QVBoxLayout(card)
        col.setContentsMargins(18, 18, 18, 18)
        heading = QLabel("Schedule")
        heading.setObjectName("sectionHeading")
        self._schedule_label.setObjectName("subtitleLabel")
        self._schedule_label.setWordWrap(True)
        self._schedule_list.setObjectName("scheduleList")
        col.addWidget(heading)
        col.addWidget(self._schedule_label)
        col.addWidget(self._schedule_list, 1)
        col.addStretch(1)
        layout.addWidget(card)
   
    def _build_analysis_page(self):
        layout = QVBoxLayout(self._analysis_page)
        layout.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("mainCard")
        self._apply_shadow(card)
        col = QVBoxLayout(card)
        col.setContentsMargins(18, 18, 18, 18)
        head_row = QHBoxLayout()
        heading = QLabel("Analysis")
        heading.setObjectName("sectionHeading")
        details = QLabel("Use the right panel metrics to track marks, activity, and exam completion.")
        details.setObjectName("subtitleLabel")
        details.setWordWrap(True)
        self._analysis_filter.setObjectName("analysisFilter")
        self._analysis_filter.addItem("All", "all")
        self._analysis_filter.addItem("Submitted", "submitted")
        self._analysis_filter.addItem("Active", "active")
        head_row.addWidget(heading)
        head_row.addStretch(1)
        head_row.addWidget(self._analysis_filter)
        self._analysis_list.setObjectName("analysisList")
        col.addLayout(head_row)
        col.addWidget(details)
        col.addWidget(self._analysis_list, 1)
        col.addStretch(1)
        layout.addWidget(card)
   
    def _switch_path(self, path: str):
        if path == "home":
            self._switch_content(self._classes_page)
            self._welcome.setText("Home")
        elif path == "schedule":
            self._switch_content(self._schedule_page)
            self._welcome.setText("Schedule")
        elif path == "analysis":
            self._switch_content(self._analysis_page)
            self._welcome.setText("Analysis")
        self.path_changed.emit(path)

    def set_session(self, token: str, user_id: str, full_name: str):
        self._token = token
        self._user_id = user_id
        self._full_name = full_name
        self._welcome.setText("Home")
        self._subtitle.setText(f"Welcome back, {full_name}")
        self._profile_name.setText(full_name)
        self._profile_role.setText("Student")
        initials = "".join(part[:1].upper() for part in full_name.split()[:2]).strip() or "ST"
        self._avatar.setText(initials)
        self.refresh_data()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _extract_detail(self, resp: requests.Response) -> str:
        try:
            body = resp.json()
            if isinstance(body, dict):
                return str(body.get("detail", f"Server error ({resp.status_code})"))
        except ValueError:
            pass
        return f"Server error ({resp.status_code})"

    def _set_status(self, text: str, is_error: bool = False):
        color = "#C62828" if is_error else "#2557C7"
        self._status.setStyleSheet(f"font-size: 12px; color: {color};")
        self._status.setText(text)

    @Slot()
    def refresh_data(self):
        if not self._token:
            self._set_status("Missing session token.", is_error=True)
            return
        if self._refresh_worker and self._refresh_worker.isRunning():
            return  # already refreshing
        self._refresh_worker = ApiWorker(_http_fetch_dashboard, self._headers())
        self._refresh_worker.finished.connect(self._apply_dashboard_data)
        self._refresh_worker.errored.connect(
            lambda e: self._set_status(f"Refresh error: {e}", is_error=True)
        )
        self._refresh_worker.start()

    @Slot(object)
    def _apply_dashboard_data(self, result: dict):
        # ── Performance metrics ───────────────────────────────────────────
        perf = result.get("performance")
        if perf:
            self._metric_marks.setText(f"{perf.get('average_mcq_score', 0):.1f}")
            self._metric_completed.setText(str(perf.get("completed_sessions", 0)))
            self._metric_active.setText(str(perf.get("active_sessions", 0)))
            self._metric_integrity.setText(f"{perf.get('average_integrity_score', 0):.1f}")
            self._metric_total.setText(str(perf.get("total_sessions", 0)))

        # ── Classes ───────────────────────────────────────────────────────
        self._classes_list.clear()
        self._upcoming_exams_home_list.clear()
        self._attempted_exams_home_list.clear()
        self._class_view.upcoming_exams_list.clear()
        self._class_view.attempted_exams_list.clear()
        self._update_exam_action_buttons()
        self._class_name_by_id.clear()

        classes_status, classes_body = result.get("classes", (-1, ""))
        if classes_status == 200:
            classes = [normalize_class_payload(c) for c in (classes_body or [])]
            if not classes:
                self._classes_list.setMinimumHeight(180)
                self._classes_list.addItem("No classes currently joined.")
                self._upcoming_exams_home_list.addItem("No exams available.")
                self._attempted_exams_home_list.addItem("No exams available.")
                self._set_status("No classes yet. Join a class to continue.")
            else:
                for c in classes:
                    class_id = resolve_optional_id(c, "class_id")
                    if class_id:
                        self._class_name_by_id[class_id] = c.get("name", "Unknown class")
                    item = QListWidgetItem()
                    row_widget = ClassRowWidget(
                        c.get("name", "Unknown class"),
                        "Approved" if c.get("approved") else "Pending",
                    )
                    item.setSizeHint(row_widget.sizeHint())
                    item.setData(Qt.ItemDataRole.UserRole, c)
                    if not c.get("approved"):
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    self._classes_list.addItem(item)
                    self._classes_list.setItemWidget(item, row_widget)
                self._set_status("Classes loaded.")
                self._select_first_approved_class()
        elif classes_status == -1:
            logger.error("Failed loading classes: %s", classes_body)
            self._set_status("Network error while loading classes.", is_error=True)
        else:
            self._set_status(f"Failed to load classes: {classes_body}", is_error=True)

        # ── Schedule (uses class_name_by_id populated above) ──────────────
        self._schedule_list.clear()
        schedule_raw = result.get("schedule")
        if schedule_raw is not None:
            exams = [normalize_exam_payload(e) for e in (schedule_raw or [])]
            if not exams:
                self._schedule_label.setText("No scheduled exams yet.")
            else:
                exams_sorted = sorted(
                    exams,
                    key=lambda e: (e.get("scheduled_start") or "", e.get("title") or ""),
                )
                for exam in exams_sorted:
                    class_name = self._class_name_by_id.get(
                        resolve_optional_id(exam, "class_id") or "", "Unknown class"
                    )
                    start = self._fmt_dt(exam.get("scheduled_start"))
                    end   = self._fmt_dt(exam.get("scheduled_end"))
                    row = QListWidgetItem(
                        f"{exam.get('title', 'Exam')} | {class_name}\n"
                        f"{start} - {end} | {exam.get('status', 'unknown')}"
                    )
                    row.setData(Qt.ItemDataRole.UserRole, exam)
                    self._schedule_list.addItem(row)
                self._schedule_label.setText(f"{len(exams_sorted)} scheduled/available exam(s).")
        else:
            self._schedule_label.setText("Unable to load schedule right now.")

        # ── History ────────────────────────────────────────────────────────
        self._analysis_rows = result.get("history") or []
        self._render_analysis_rows()
        class_id = resolve_optional_id(self._selected_class, "class_id")
        if class_id:
            self._populate_attempted_exams(class_id)

    def _fmt_dt(self, value: Optional[str]) -> str:
        if not value:
            return "TBD"
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.strftime("%d %b %Y %H:%M")
        except (ValueError, TypeError):
            return str(value)

    def _render_analysis_rows(self):
        self._analysis_list.clear()
        filter_key = self._analysis_filter.currentData()
        rows = self._analysis_rows
        if filter_key == "submitted":
            rows = [r for r in rows if str(r.get("session_status", "")).lower() == "submitted"]
        elif filter_key == "active":
            rows = [
                r for r in rows
                if str(r.get("session_status", "")).lower() in {"active", "locked", "verifying"}
            ]

        if not rows:
            self._analysis_list.addItem("No attempts for selected filter.")
            return

        for row in rows:
            submitted = self._fmt_dt(row.get("submitted_at"))
            score = row.get("total_score", 0.0)
            integrity = row.get("integrity_score")
            integrity_text = f"{integrity:.1f}" if isinstance(integrity, (int, float)) else "N/A"
            item = QListWidgetItem(
                f"{row.get('exam_title', 'Exam')} | {row.get('class_name', 'Class')}\n"
                f"Score: {score} | Integrity: {integrity_text} | "
                f"Session: {row.get('session_status', 'unknown')} | Submitted: {submitted}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            self._analysis_list.addItem(item)

    @Slot(QListWidgetItem)
    def _open_attempt_answers(self, item: QListWidgetItem):
        payload = item.data(Qt.ItemDataRole.UserRole) or {}
        session_id = resolve_optional_id(payload, "session_id")
        exam_id = resolve_optional_id(payload, "exam_id")
        if not session_id or not exam_id:
            self._set_status("Attempt row missing session_id/exam_id.", is_error=True)
            return
        if self._attempt_worker and self._attempt_worker.isRunning():
            return
        self._set_status("Loading attempt…")
        self._attempt_worker = ApiWorker(
            _http_fetch_attempt, self._headers(), exam_id, session_id
        )
        self._attempt_worker.finished.connect(
            lambda result, p=payload: self._apply_attempt_answers(result, p)
        )
        self._attempt_worker.errored.connect(
            lambda e: self._set_status("Network error while opening attempt.", is_error=True)
        )
        self._attempt_worker.start()

    @Slot(object)
    def _apply_attempt_answers(self, result: dict, payload: dict):
        if "error" in result:
            self._set_status(result["error"], is_error=True)
            return
        session_id = resolve_optional_id(payload, "session_id")
        exam_id    = resolve_optional_id(payload, "exam_id")
        exam      = normalize_exam_payload(result["exam"] or {})
        questions = normalize_question_list(result["questions"] or [])
        answers   = result["answers"] or []
        graded = (
            any(a.get("examiner_score") is not None for a in answers)
            or payload.get("essay_score") is not None
        )
        self._exam_view.configure(
            session={"session_id": session_id, "exam_id": exam_id, "status": payload.get("session_status")},
            exam=exam,
            questions=questions,
            answers=answers,
            readonly=True,
            graded=bool(graded),
        )
        self._welcome.setText("Exam Review")
        self._switch_content(self._exam_page)
        self._set_status("Opened submitted attempt.")

    @Slot(QListWidgetItem)
    def _open_selected_class_page(self, item: QListWidgetItem):
        payload = item.data(Qt.ItemDataRole.UserRole) or {}
        class_id = resolve_optional_id(payload, "class_id")
        if not class_id:
            return
        self._selected_class = payload
        self._update_class_details(payload)
        self._switch_content(self._class_detail_page)
        self._welcome.setText(payload.get("name", "Class"))

    def _update_class_details(self, class_payload: dict):
        class_name = class_payload.get("name", "Unknown subject")
        class_code = class_payload.get("join_code")
        class_desc = class_payload.get("description") or "No class description provided."
        self._class_view.class_subject_value.setText(f"Course / Subject name: {class_name}")
        self._class_view.class_instructor_value.setText("Instructor Name: Not exposed by current student endpoints")
        self._class_view.class_code_value.setText(
            f"Class code: {class_code or 'Not exposed by current student endpoints'}"
        )
        self._class_view.class_desc_value.setText(f"Description: {class_desc}")

    def _populate_attempted_exams(self, class_id: str):
        self._attempted_exams_home_list.clear()
        self._class_view.attempted_exams_list.clear()
        rows = [
            row for row in self._analysis_rows
            if str(row.get("class_id", "")) == str(class_id)
        ]
        attempted_rows = [
            row for row in rows
            if str(row.get("session_status", "")).lower() in {"submitted", "terminated"}
        ]
        if not attempted_rows:
            self._attempted_exams_home_list.addItem("No exams available.")
            self._class_view.attempted_exams_list.addItem("No exams available.")
            return
        for row in attempted_rows:
            submitted = self._fmt_dt(row.get("submitted_at"))
            total = row.get("total_score", 0.0)
            line = f"{row.get('exam_title', 'Exam')} | Score: {total} | Submitted: {submitted}"
            item_home = QListWidgetItem(line)
            item_home.setData(Qt.ItemDataRole.UserRole, row)
            self._attempted_exams_home_list.addItem(item_home)
            item_detail = QListWidgetItem(line)
            item_detail.setData(Qt.ItemDataRole.UserRole, row)
            self._class_view.attempted_exams_list.addItem(item_detail)

    def _select_first_approved_class(self):
        for i in range(self._classes_list.count()):
            item = self._classes_list.item(i)
            payload = item.data(Qt.ItemDataRole.UserRole)
            if payload and payload.get("approved"):
                self._classes_list.setCurrentRow(i)
                return

    @Slot()
    def _join_class(self):
        code = self._join_input.text().strip().upper()
        if not code:
            self._set_status("Please enter a class join code.", is_error=True)
            return
        self._join_input.clear()
        if self._join_worker and self._join_worker.isRunning():
            return
        self._set_status("Joining class…")
        self._join_worker = ApiWorker(_http_join_class, self._headers(), code)
        self._join_worker.finished.connect(self._on_join_result)
        self._join_worker.errored.connect(
            lambda e: self._set_status("Network error while joining class.", is_error=True)
        )
        self._join_worker.start()

    @Slot(object)
    def _on_join_result(self, result: dict):
        status = result["status"]
        data   = result["data"]
        if status in (200, 201):
            self._set_status(data.get("message", "Join request submitted."))
            self.refresh_data()
        elif status == -1:
            self._set_status("Network error while joining class.", is_error=True)
        else:
            detail = data.get("detail", f"Server error ({status})")
            self._set_status(str(detail), is_error=True)

    @Slot()
    def _on_class_changed(self):
        item = self._classes_list.currentItem()
        self._upcoming_exams_home_list.clear()
        self._attempted_exams_home_list.clear()
        self._class_view.upcoming_exams_list.clear()
        self._class_view.attempted_exams_list.clear()
        if item is None:
            return
        class_payload = item.data(Qt.ItemDataRole.UserRole) or {}
        class_id = resolve_optional_id(class_payload, "class_id")
        if not class_id:
            return
        self._selected_class = class_payload
        self._update_class_details(class_payload)
        self._load_exams(class_id)

    def _load_exams(self, class_id: str):
        if self._exams_worker and self._exams_worker.isRunning():
            return
        self._exams_worker = ApiWorker(_http_fetch_exams, self._headers(), class_id)
        self._exams_worker.finished.connect(
            lambda result, cid=class_id: self._apply_exams(result, cid)
        )
        self._exams_worker.errored.connect(
            lambda e: self._set_status("Network error while loading exams.", is_error=True)
        )
        self._exams_worker.start()

    @Slot(object)
    def _apply_exams(self, result: dict, class_id: str):
        status = result["status"]
        data   = result["data"]
        if status != 200:
            msg = data if isinstance(data, str) else str(data)
            self._set_status(
                "Network error while loading exams." if status == -1
                else f"Failed to load exams: {msg}",
                is_error=True,
            )
            return

        exams = [normalize_exam_payload(e) for e in (data or [])]
        if not exams:
            self._upcoming_exams_home_list.addItem("No exams available.")
            self._class_view.upcoming_exams_list.addItem("No exams available.")
            self._update_exam_action_buttons()
            self._set_status("No exams found for this class.")
            return

        for exam in exams:
            eid = resolve_optional_id(exam, "class_id") or ""
            row_widget = ExamRowWidget(
                exam["title"],
                self._class_name_by_id.get(eid, "Class"),
                exam["status"],
            )
            item = QListWidgetItem()
            item.setSizeHint(row_widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, exam)
            self._upcoming_exams_home_list.addItem(item)
            self._upcoming_exams_home_list.setItemWidget(item, row_widget)
            detail_item = QListWidgetItem(
                f"{exam.get('title', 'Exam')} | {exam.get('status', 'unknown')} | "
                f"{self._fmt_dt(exam.get('scheduled_start'))}"
            )
            detail_item.setData(Qt.ItemDataRole.UserRole, exam)
            self._class_view.upcoming_exams_list.addItem(detail_item)
        self._update_exam_action_buttons()
        self._set_status("Exams loaded.")

    @Slot()
    def _start_selected_exam(self):
        item = self._upcoming_exams_home_list.currentItem()
        if item is None:
            self._set_status("Select an exam first.", is_error=True)
            return
        self._open_upcoming_exam_view(item)

    @Slot(QListWidgetItem)
    def _open_upcoming_exam_view(self, item: QListWidgetItem):
        exam_row = item.data(Qt.ItemDataRole.UserRole) or {}
        exam_id  = resolve_optional_id(exam_row, "exam_id")
        if not exam_id:
            self._set_status("Exam payload missing exam_id.", is_error=True)
            return
        if self._start_worker and self._start_worker.isRunning():
            return
        self._set_status("Starting exam…")
        self._start_worker = ApiWorker(_http_start_exam, self._headers(), exam_id)
        self._start_worker.finished.connect(self._apply_exam_started)
        self._start_worker.errored.connect(
            lambda e: self._set_status("Network error while starting exam.", is_error=True)
        )
        self._start_worker.start()

    @Slot(object)
    def _apply_exam_started(self, result: dict):
        if "error" in result:
            self._set_status(result["error"], is_error=True)
            return
        exam      = normalize_exam_payload(result["exam"] or {})
        session   = normalize_session_payload(result["session"] or {})
        questions = normalize_question_list(result["questions"] or [])
        require_entry_face = bool(exam.get("require_liveness_check", True))
        self._set_status(
            "Launching secure exam window…"
            if require_entry_face
            else "Launching secure exam window with entry liveness disabled…"
        )
        self.start_exam_requested.emit(session, exam, questions, self._token)

    @Slot()
    def _join_exam_from_class_view(self):
        item = self._class_view.selected_upcoming_exam()
        if item is None:
            self._set_status("Select an exam from class view first.", is_error=True)
            return
        self._open_upcoming_exam_view(item)

    @Slot()
    def _update_exam_action_buttons(self):
        def _is_joinable(item: QListWidgetItem | None) -> bool:
            if item is None:
                return False
            payload = item.data(Qt.ItemDataRole.UserRole) or {}
            if not isinstance(payload, dict):
                return False
            status = str(payload.get("status", "")).strip().lower()
            return status == "live"

        home_item = self._upcoming_exams_home_list.currentItem()
        class_item = self._class_view.selected_upcoming_exam()
        self._start_exam_btn.setEnabled(_is_joinable(home_item))
        self._class_view.join_exam_btn.setEnabled(_is_joinable(class_item))

    @Slot()
    def _return_from_exam_page(self):
        self._switch_content(self._classes_page)
        self._welcome.setText("Home")

    @Slot(dict, list)
    def _submit_exam_answers(self, session_payload: dict, answers: list[dict]):
        session_id = resolve_optional_id(session_payload, "session_id")
        exam_id    = resolve_optional_id(session_payload, "exam_id")
        if not session_id or not exam_id:
            self._set_status("Cannot submit: session context missing.", is_error=True)
            return
        if self._submit_worker and self._submit_worker.isRunning():
            return
        self._set_status("Submitting exam…")
        self._submit_worker = ApiWorker(
            _http_submit_exam,
            self._headers(),
            session_id,
            exam_id,
            answers,
            self._token,
            WS_URL,
        )
        self._submit_worker.finished.connect(self._on_submit_result)
        self._submit_worker.errored.connect(
            lambda e: self._set_status("Network error during submission.", is_error=True)
        )
        self._submit_worker.start()

    @Slot(object)
    def _on_submit_result(self, result: dict):
        if result.get("ok"):
            self._set_status("Exam submitted successfully.")
            self.refresh_data()
            self._switch_content(self._classes_page)
            self._welcome.setText("Home")
        else:
            self._set_status(result.get("error", "Submission failed."), is_error=True)
