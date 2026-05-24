"""
run_exams_preview.py
--------------------
Standalone layout preview for ExamsPage.
No real backend required — uses MockApiClient with hardcoded dummy data.

Usage (from your project root):
    python run_exams_preview.py

Requirements:
    pip install PySide6
"""

from __future__ import annotations

import sys
import os

# ── Make sure the project root is on sys.path so all client.* imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

# ─────────────────────────────────────────────────────────────────────────────
#  MockApiClient
#  Implements every method that ExamsPage calls.
#  Returns realistic dummy data synchronously.
#  ApiWorker will call these off-thread — that is fine.
# ─────────────────────────────────────────────────────────────────────────────

class MockApiClient:
    """Drop-in replacement for ApiClient during layout preview."""

    # Called by ExamsPage._load_page_data
    def get_upcoming_exams(self) -> list[dict]:
        return [
            {
                "exam_id":          "EX-001",
                "title":            "Advanced Cybersecurity Architecture",
                "date":             "Oct 24, 10:00 AM",
                "duration_mins":    180,
                "face_id_required": True,
                "check_in_open":    True,
                # ViewDetailsDialog fields (served from cache)
                "start_time":       "Oct 24, 2023 at 10:00 AM",
                "examiner_name":    "Dr. Sarah Mitchell",
            },
            {
                "exam_id":          "EX-002",
                "title":            "Global Financial Regulation Standards",
                "date":             "Oct 28, 02:00 PM",
                "duration_mins":    90,
                "face_id_required": False,
                "check_in_open":    False,
                "start_time":       "Oct 28, 2023 at 02:00 PM",
                "examiner_name":    "Prof. James Harrington",
            },
            {
                "exam_id":          "EX-003",
                "title":            "Introduction to Quantum Computing",
                "date":             "Nov 05, 09:30 AM",
                "duration_mins":    120,
                "face_id_required": True,
                "check_in_open":    False,
                "start_time":       "Nov 05, 2023 at 09:30 AM",
                "examiner_name":    "Dr. Yuki Tanaka",
            },
            {
                "exam_id":          "EX-004",
                "title":            "Network Security Fundamentals",
                "date":             "Nov 12, 11:00 AM",
                "duration_mins":    60,
                "face_id_required": False,
                "check_in_open":    False,
                "start_time":       "Nov 12, 2023 at 11:00 AM",
                "examiner_name":    "Dr. Alan Brooks",
            },
        ]

    def get_pending_requests(self) -> list[dict]:
        return [
            {
                "request_id":   "REQ-9923",
                "exam_name":    "Data Privacy Compliance Lvl 2",
                "exam_id":      "SE-9923",
                "request_date": "Oct 20, 2023",
                "status":       "Awaiting Approval",
            },
            {
                "request_id":   "REQ-8812",
                "exam_name":    "Machine Learning Ethics",
                "exam_id":      "SE-8812",
                "request_date": "Oct 19, 2023",
                "status":       "Approved",
            },
        ]

    def submit_access_code(self, code: str) -> dict:
        """Simulates a successful join request."""
        return {
            "request_id":   f"REQ-{code[-4:].upper()}",
            "exam_name":    f"Exam [{code}]",
            "exam_id":      f"SE-{code[-4:].upper()}",
            "request_date": "Today",
            "status":       "Awaiting Approval",
        }

    def cancel_request(self, request_id: str) -> dict:
        """Simulates a successful cancellation."""
        return {"cancelled": request_id}

    # StatusBarWidget (used by dashboard, not exams — stub for safety)
    def get_system_status(self) -> dict:
        return {
            "camera":    {"active": True,  "label": "Active"},
            "network":   {"stable": True,  "label": "Stable", "latency_ms": 18},
            "last_scan": "2 minutes ago",
        }

    # token setter (called by set_session on dashboard — no-op here)
    def set_token(self, token: str) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  MockApiWorker
#  Runs the API function synchronously on the main thread.
#  Avoids the need for a real QThread in the preview.
# ─────────────────────────────────────────────────────────────────────────────

from PySide6.QtCore import QObject, Signal

class MockApiWorker(QObject):
    finished = Signal(object)
    errored  = Signal(str)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn   = fn
        self._args = args
        self._kwargs = kwargs

    def start(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as exc:
            self.errored.emit(str(exc))

    def deleteLater(self) -> None:  # noqa: N802
        super().deleteLater()


# ─────────────────────────────────────────────────────────────────────────────
#  Patch ApiWorker import before ExamsPage loads it
#  This replaces the real threaded worker with our synchronous mock
#  so the preview works without a running backend.
# ─────────────────────────────────────────────────────────────────────────────

import unittest.mock as mock

# Patch the ApiWorker that ExamsPage imports from its services path
sys.modules.setdefault("client", mock.MagicMock())
sys.modules.setdefault("client.exam", mock.MagicMock())
sys.modules.setdefault("client.dashboard.services", mock.MagicMock())

import importlib, types

# Build a fake api_worker module that exports MockApiWorker as ApiWorker
fake_worker_mod = types.ModuleType("client.exam.services.api_worker")
setattr(fake_worker_mod, "ApiWorker", MockApiWorker)
sys.modules["client.exam.services.api_worker"] = fake_worker_mod

# Build a fake api_client module
fake_client_mod = types.ModuleType("client.exam.services.api_client")
setattr(fake_client_mod, "ApiClient", MockApiClient)
sys.modules["client.exam.services.api_client"] = fake_client_mod

# Patch sidebar import to use the real file
import importlib.util, pathlib

def _load_from_path(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None:
        raise ValueError(f"Failed to load module {module_name} from {path}")
    mod  = importlib.util.module_from_spec(spec)
    if mod is None:
        raise ValueError(f"Failed to create module from spec for {module_name}")
    sys.modules[module_name] = mod
    if spec.loader is None:
        raise ValueError(f"Spec loader is None for {module_name}")
    spec.loader.exec_module(mod)
    return mod

_root = pathlib.Path(__file__).parent

# Load real sidebar
_load_from_path(
    "client.exam.views.sidebar",
    str(_root / "exam" / "views" / "sidebar.py"),
)

# Load shared info_dialog
_load_from_path(
    "client.Shared.info_dialog",
    str(_root / "Shared" / "info_dialog.py"),
)

_load_from_path(
    "client.Shared.view_details_dialog", 
    str(_root / "Shared" / "view_details_dialog.py"))

# Load exam sub-widgets in dependency order
for mod_name, rel_path in [
    ("client.exam.views.exam_card_widget",
     "exam/views/exam_card_widget.py"),
    ("client.exam.views.upcoming_exams_panel",
     "exam/views/upcoming_exams_panel.py"),
    ("client.exam.views.pending_request_card",
     "exam/views/pending_request_card.py"),
    ("client.exam.views.pending_requests_panel",
     "exam/views/pending_requests_panel.py"),
    ("client.exam.views.join_exam_widget",
     "exam/views/join_exam_widget.py"),
    ("client.exam.views.security_checklist_widget",
     "exam/views/security_checklist_widget.py"),
        ("client.exam.views.exams_page",
     "exam/views/exams_page.py"),
]:
    _load_from_path(mod_name, str(_root / rel_path))

# ─────────────────────────────────────────────────────────────────────────────
#  Launch
# ─────────────────────────────────────────────────────────────────────────────

from client.exam.views.exams_page import ExamsPage   # noqa: E402 — must be after patches

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    api  = MockApiClient()
    page = ExamsPage(api=api)
    page.setWindowTitle("ExamsPage — Layout Preview")
    page.resize(1280, 800)
    page.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
