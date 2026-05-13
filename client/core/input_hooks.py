"""
client/core/input_hooks.py
Module 7 (Python side) — Low-Level Keyboard Hook Wrapper

Loads native/hooks/input_hooks.dll and installs a global Windows
keyboard hook via SetWindowsHookEx (WH_KEYBOARD_LL).

Blocked keys (handled by C++ DLL):
  - Win key (left + right)
  - Alt+Tab
  - Alt+F4
  - PrintScreen
  - Ctrl+Escape (Start menu)
  - Ctrl+Shift+Escape (Task Manager)

Usage:
    hooks = InputHooks(exam_hwnd, on_blocked_key)
    if hooks.install():
        # exam runs
        hooks.uninstall()

Build the DLL first:
    cd client/native/hooks
    cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release
    → outputs input_hooks.dll to client/native/

Critical ctypes notes:
  - argtypes and restype MUST be set explicitly on 64-bit Windows
    Otherwise ctypes truncates pointers to 32-bit causing silent crashes
  - Callback reference MUST be kept alive as a Python object
    Python GC will collect it if not stored, causing access violations
  - Exceptions inside ctypes callbacks crash the message pump silently
    All callback code is wrapped in try/except
"""

import ctypes
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# DLL location — built by CMake into client/native/
DLL_PATH = Path(__file__).parent.parent / "native" / "input_hooks.dll"

# Callback type — must match C++ typedef exactly:
# typedef void (*EventCallback)(const char* event_type, int vk_code);
EventCallbackType = ctypes.CFUNCTYPE(
    None,            # return type: void
    ctypes.c_char_p, # arg 1: const char* event_type
    ctypes.c_int,    # arg 2: int vk_code
)

# Human-readable names for virtual key codes
VK_NAMES: dict[int, str] = {
    0x09:  "Tab",
    0x1B:  "Escape",
    0x2C:  "PrintScreen",
    0x5B:  "Left Win",
    0x5C:  "Right Win",
    0x73:  "F4",
    0xA4:  "Left Alt",
    0xA5:  "Right Alt",
    0xA2:  "Left Ctrl",
    0xA3:  "Right Ctrl",
}


class InputHooks:
    """
    Installs low-level Windows keyboard hooks via the C++ DLL.

    on_event: called with (event_type: str, vk_code: int) for every
              blocked key press. event_type is one of:
              WIN_KEY, ALT_TAB, ALT_F4, PRINT_SCREEN,
              CTRL_ESC, TASK_MANAGER
    """

    def __init__(
        self,
        exam_hwnd: int,
        on_event: Callable[[str, int], None],
    ):
        self.exam_hwnd    = exam_hwnd
        self.on_event     = on_event
        self._dll         = None
        self._callback_ref = None  # ctypes CFUNCTYPE callback — must stay alive to prevent GC crash
        self._pump_thread: Optional[threading.Thread]   = None
        self._installed   = False

    @property
    def is_installed(self) -> bool:
        """True if hooks are currently active."""
        return self._installed

    def install(self) -> bool:
        """
        Load the DLL, set up the callback, install keyboard hooks,
        and start the message pump thread.

        Returns True on success, False on any failure.
        Logs the specific failure reason.
        """
        if self._installed:
            logger.warning("Input hooks already installed — skipping")
            return True

        if not DLL_PATH.exists():
            logger.error(
                "input_hooks.dll not found at %s\n"
                "Build it with:\n"
                "  cd client/native/hooks\n"
                "  cmake -B build -S . -DCMAKE_BUILD_TYPE=Release\n"
                "  cmake --build build --config Release",
                DLL_PATH,
            )
            return False

        try:
            self._dll = ctypes.CDLL(str(DLL_PATH))

            # ── Set function signatures explicitly ─────────────────────────
            # CRITICAL: argtypes and restype must be set on 64-bit Windows.
            # Without this, ctypes assumes int (32-bit) for all args and
            # return values, which truncates 64-bit pointers silently.

            # int install_hooks(HWND exam_hwnd, EventCallback callback)
            self._dll.install_hooks.argtypes = [
                ctypes.c_void_p,   # HWND exam_hwnd
                EventCallbackType, # EventCallback callback
            ]
            self._dll.install_hooks.restype = ctypes.c_int

            # void uninstall_hooks(void)
            self._dll.uninstall_hooks.argtypes = []
            self._dll.uninstall_hooks.restype  = None

            # void run_message_pump(void)
            self._dll.run_message_pump.argtypes = []
            self._dll.run_message_pump.restype  = None

            # void stop_message_pump(void)
            self._dll.stop_message_pump.argtypes = []
            self._dll.stop_message_pump.restype  = None

            # ── Create callback ────────────────────────────────────────────
            # Wrapped in try/except — exceptions inside ctypes callbacks
            # crash the message pump thread silently without this guard

            def _safe_callback(event_type_bytes: bytes, vk_code: int):
                try:
                    event_type = event_type_bytes.decode("utf-8", errors="replace")
                    vk_name    = VK_NAMES.get(vk_code, f"VK_{vk_code:#04x}")
                    logger.debug("Blocked key: %s (vk=%s)", event_type, vk_name)
                    self.on_event(event_type, vk_code)
                except Exception as e:
                    # Never let exceptions escape into C++ territory
                    logger.error("Callback exception (suppressed): %s", e)

            # Store reference — Python GC would collect it otherwise
            # causing a hard crash when C++ tries to call the callback
            self._callback_ref = EventCallbackType(_safe_callback)

            # ── Install hooks ──────────────────────────────────────────────
            result = self._dll.install_hooks(
                ctypes.c_void_p(self.exam_hwnd),
                self._callback_ref,
            )

            if result != 0:
                logger.error(
                    "install_hooks() failed with Win32 error code %d\n"
                    "Common causes:\n"
                    "  - Antivirus blocking SetWindowsHookEx\n"
                    "  - Insufficient privileges (try running as Administrator)\n"
                    "  - UAC blocking global hook installation",
                    result,
                )
                return False

            # ── Start message pump ─────────────────────────────────────────
            # The hook WILL NOT FIRE without a running message pump.
            # This thread runs GetMessage() loop in the background.
            self._pump_thread = threading.Thread(
                target=self._dll.run_message_pump,
                daemon=True,
                name="HookMessagePump",
            )
            self._pump_thread.start()

            self._installed = True
            logger.info("Input hooks installed — keyboard blocking active")
            return True

        except OSError as e:
            logger.error("Failed to load input_hooks.dll: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error installing hooks: %s", e)
            return False

    def uninstall(self):
        """
        Uninstall hooks and stop the message pump.
        Safe to call even if install() failed or was never called.
        """
        if not self._installed:
            return

        if self._dll:
            try:
                self._dll.uninstall_hooks()
                self._dll.stop_message_pump()
                self._installed = False
                logger.info("Input hooks uninstalled")
            except Exception as e:
                logger.error("Failed to uninstall hooks: %s", e)
