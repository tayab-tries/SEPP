"""
client/modules/proctoring/activity_monitor.py
Module 4a — Screen & Activity Monitor (Windows-native)

Monitors:
  - Active foreground window (window switch detection)
  - Cursor position vs monitor bounds (dual monitor detection)
  - Running processes (prohibited app detection)
  - Clipboard changes
  - VM detection (called once at exam start)

Uses pywin32 for Windows API access.
The C++ DLL (native/hooks/) handles low-level keyboard hooks separately.

Optimizations implemented:
  13. Process scanner interval scaling — scans every 30s normally,
      every 10s after a recent violation is detected
"""

import ctypes
import ctypes.wintypes
import logging
import psutil
import threading
import time
from datetime import datetime
from typing import Callable, Optional

import win32api
import win32gui

from shared.constants import EventType, EventSeverity
from client.modules.proctoring.event_logger import ProctoringEvent

logger = logging.getLogger(__name__)

# ── Prohibited processes ───────────────────────────────────────────────────
PROHIBITED_PROCESSES = {
    "teamviewer.exe",
    "anydesk.exe",
    "obs64.exe",
    "obs32.exe",
    "sharex.exe",
    "screenpresso.exe",
    "vnc.exe",
    "vncserver.exe",
    "rustdesk.exe",
    "discord.exe",
    "zoom.exe",
    "mstsc.exe",        # Remote Desktop Client
    "parsec.exe",
    "radmin.exe",
    "ltservice.exe",    # LogMeIn
    "ltsvc.exe",        # LogMeIn
    "screenconnect.exe",
}

# ── Poll intervals ─────────────────────────────────────────────────────────
WINDOW_POLL_INTERVAL    = 1.0   # Seconds between foreground window checks
CURSOR_POLL_INTERVAL    = 0.5   # Seconds between cursor position checks
CLIPBOARD_POLL_INTERVAL = 2.0   # Seconds between clipboard sequence checks

# ── Process scanner intervals (optimization 13) ───────────────────────────
PROCESS_SCAN_NORMAL  = 30   # Normal scan interval in seconds
PROCESS_SCAN_ALERT   = 10   # Faster scan after a violation is detected
PROCESS_ALERT_WINDOW = 120  # Seconds to stay in fast-scan mode after violation

# ── Window title match ─────────────────────────────────────────────────────
APP_WINDOW_TITLE = "ExamApp"

# ── VM fingerprints ────────────────────────────────────────────────────────
VM_BIOS_STRINGS  = {"vmware", "virtualbox", "qemu", "xen", "innotek", "bochs"}
VM_MODEL_STRINGS = {"vmware virtual", "virtualbox", "qemu", "kvm virtual"}
VM_DISK_STRINGS  = {"vmware", "virtualbox", "vbox", "qemu virtual"}
VM_NIC_STRINGS   = {"vmware", "virtualbox", "vbox host", "hyper-v virtual"}


class ActivityMonitor:
    """
    Screen and process monitoring — all checks run as daemon threads.
    Each check is independent — one crashing does not affect others.
    """

    def __init__(
        self,
        emit_event: Callable[[ProctoringEvent], None],
        exam_window_hwnd: Optional[int] = None,
    ):
        self.emit_event  = emit_event
        self.exam_hwnd   = exam_window_hwnd
        self._running    = False
        self._threads:   list[threading.Thread] = []
        self._monitor_bounds = self._get_monitor_bounds()

        # Safe initialization — GetClipboardSequenceNumber can fail
        try:
            self._last_clipboard_seq = win32api.GetClipboardSequenceNumber() # type: ignore[attr-defined]
        except Exception:
            self._last_clipboard_seq = 0

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        checks = [
            ("WindowWatcher",    self._window_watcher),
            ("CursorWatcher",    self._cursor_watcher),
            ("ProcessScanner",   self._process_scanner),
            ("ClipboardWatcher", self._clipboard_watcher),
        ]
        for name, fn in checks:
            t = threading.Thread(target=fn, daemon=True, name=name)
            t.start()
            self._threads.append(t)
        logger.info("ActivityMonitor started (%d threads)", len(self._threads))

    def stop(self):
        self._running = False
        logger.info("ActivityMonitor stopped")

    def set_exam_window(self, hwnd: int):
        """Set the exam window handle after the window is created."""
        self.exam_hwnd = hwnd

    # ── Monitor layout ─────────────────────────────────────────────────────

    def _get_monitor_bounds(self) -> list[dict]:
        """Return bounding boxes for all connected monitors."""
        monitors: list[dict] = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            try:
                r = lprcMonitor.contents
                monitors.append({
                    "left":    r.left,
                    "top":     r.top,
                    "right":   r.right,
                    "bottom":  r.bottom,
                    "primary": (r.left == 0 and r.top == 0),
                })
            except Exception:
                pass
            return True

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.c_double,
        )
        try:
            ctypes.windll.user32.EnumDisplayMonitors(
                None, None, MonitorEnumProc(callback), 0
            )
        except Exception:
            pass
        return monitors

    def _get_primary_bounds(self) -> dict:
        for m in self._monitor_bounds:
            if m["primary"]:
                return m
        return (
            self._monitor_bounds[0]
            if self._monitor_bounds
            else {"left": 0, "top": 0, "right": 1920, "bottom": 1080}
        )

    # ── Window watcher ─────────────────────────────────────────────────────

    def _window_watcher(self):
        """
        Poll foreground window title every second.
        Flag if focus leaves the exam window.
        """
        while self._running:
            try:
                hwnd  = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)

                if title and APP_WINDOW_TITLE not in title:
                    self.emit_event(ProctoringEvent(
                        event_type=EventType.WINDOW_SWITCH,
                        severity=EventSeverity.MEDIUM,
                        timestamp=datetime.utcnow(),
                        metadata={"switched_to": title[:100]},
                    ))
            except Exception:
                pass

            time.sleep(WINDOW_POLL_INTERVAL)

    # ── Cursor watcher ─────────────────────────────────────────────────────

    def _cursor_watcher(self):
        """
        Detect cursor moving to a secondary monitor.
        Only active if more than one monitor is detected.
        Requires cursor to stay off-primary for >1s before flagging
        to avoid false positives from quick cursor movements.
        """
        if len(self._monitor_bounds) < 2:
            logger.info("Single monitor detected — cursor watcher inactive")
            return

        primary          = self._get_primary_bounds()
        off_primary_since: Optional[datetime] = None

        while self._running:
            try:
                x, y = win32api.GetCursorPos()
                on_primary = (
                    primary["left"] <= x <= primary["right"] and
                    primary["top"]  <= y <= primary["bottom"]
                )

                if not on_primary:
                    if off_primary_since is None:
                        off_primary_since = datetime.utcnow()
                    elif (datetime.utcnow() - off_primary_since).total_seconds() > 1.0:
                        self.emit_event(ProctoringEvent(
                            event_type=EventType.CURSOR_OFF_SCREEN,
                            severity=EventSeverity.MEDIUM,
                            timestamp=datetime.utcnow(),
                            metadata={"cursor_x": x, "cursor_y": y},
                        ))
                        off_primary_since = None  # Reset — avoid event flooding
                else:
                    off_primary_since = None

            except Exception:
                pass

            time.sleep(CURSOR_POLL_INTERVAL)

    # ── Process scanner ────────────────────────────────────────────────────

    def _process_scanner(self):
        """
        Scan running processes for prohibited apps.

        Optimization 13 — interval scaling:
        Normal: scan every 30s
        After violation: scan every 10s for 120s then revert to 30s
        This ensures fast re-detection if a student tries to restart
        a prohibited app after being caught.
        """
        last_violation_time: Optional[datetime] = None

        while self._running:
            try:
                running    = {p.name().lower() for p in psutil.process_iter(["name"])}
                violations = running & PROHIBITED_PROCESSES

                if violations:
                    last_violation_time = datetime.utcnow()
                    for proc_name in violations:
                        self.emit_event(ProctoringEvent(
                            event_type=EventType.PROHIBITED_PROCESS,
                            severity=EventSeverity.CRITICAL,
                            timestamp=datetime.utcnow(),
                            metadata={"process": proc_name},
                        ))

            except Exception:
                pass

            # Determine next scan interval (optimization 13)
            if last_violation_time is not None:
                secs_since = (datetime.utcnow() - last_violation_time).total_seconds()
                interval = (
                    PROCESS_SCAN_ALERT
                    if secs_since < PROCESS_ALERT_WINDOW
                    else PROCESS_SCAN_NORMAL
                )
            else:
                interval = PROCESS_SCAN_NORMAL

            time.sleep(interval)

    # ── Clipboard watcher ──────────────────────────────────────────────────

    def _clipboard_watcher(self):
        """
        Detect clipboard changes using the sequence number.
        The sequence number increments on every clipboard write —
        cheap, reliable, no need to read clipboard content.
        """
        while self._running:
            try:
                seq = win32api.GetClipboardSequenceNumber() # type: ignore[attr-defined]
                if seq != self._last_clipboard_seq:
                    self._last_clipboard_seq = seq
                    self.emit_event(ProctoringEvent(
                        event_type=EventType.CLIPBOARD_WRITE,
                        severity=EventSeverity.LOW,
                        timestamp=datetime.utcnow(),
                        metadata={},
                    ))
            except Exception:
                pass
            time.sleep(CLIPBOARD_POLL_INTERVAL)


# ── VM detection ───────────────────────────────────────────────────────────

def detect_virtual_machine() -> tuple[bool, list[str]]:
    """
    Check common VM indicators via WMI.
    Returns (is_vm: bool, indicators: list[str]).

    Called once at exam start before session is activated.
    If VM is detected the exam_window should emit VM_DETECTED event
    and block the student from proceeding.
    """
    indicators: list[str] = []

    try:
        import wmi
        c = wmi.WMI()

        # BIOS manufacturer check
        for bios in c.Win32_BIOS():
            mfr = (bios.Manufacturer or "").lower()
            if any(s in mfr for s in VM_BIOS_STRINGS):
                indicators.append(f"BIOS:{bios.Manufacturer}")

        # Computer system model check
        for cs in c.Win32_ComputerSystem():
            model = (cs.Model or "").lower()
            if any(s in model for s in VM_MODEL_STRINGS):
                indicators.append(f"Model:{cs.Model}")

        # Disk drive check
        for disk in c.Win32_DiskDrive():
            caption = (disk.Caption or "").lower()
            if any(s in caption for s in VM_DISK_STRINGS):
                indicators.append(f"Disk:{disk.Caption}")

        # Network adapter check — VM adapters have recognizable names
        for adapter in c.Win32_NetworkAdapter():
            name = (adapter.Name or "").lower()
            # These strings only appear inside VM guests, not on Hyper-V host machines
            if any(s in name for s in {
                "vmware network adapter",
                "virtualbox host-only",
                "vbox host-only",
                "hyper-v virtual ethernet adapter",  # Guest-side adapter name
                "microsoft hyper-v network adapter", # Guest-side adapter name
            }):
                indicators.append(f"NIC:{adapter.Name}")
    except Exception as e:
        logger.warning("VM detection WMI query failed: %s", e)

    return len(indicators) > 0, indicators
