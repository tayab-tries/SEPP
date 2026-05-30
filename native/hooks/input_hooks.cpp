/*
 * native/hooks/input_hooks.cpp
 * Module 7 — Low-Level Input Hooks DLL
 *
 * Compiled as a Windows DLL, loaded from Python via ctypes.
 *
 * Blocks and reports:
 *   - Win key (left + right)       → WIN_KEY
 *   - Alt+Tab                      → ALT_TAB
 *   - Alt+F4                       → ALT_F4
 *   - PrintScreen                  → PRINT_SCREEN
 *   - Ctrl+Shift+Esc (Task Mgr)   → TASK_MANAGER
 *   - Ctrl+Esc (Start menu)        → CTRL_ESC
 *
 * Build with MinGW:
 *   cd client/native/hooks
 *   cmake -B build -S . -G "MinGW Makefiles"
 *   cmake --build build
 *   → outputs input_hooks.dll to client/native/
 *
 * Python usage:
 *   hooks = ctypes.CDLL("./native/input_hooks.dll")
 *   hooks.install_hooks.argtypes = [ctypes.c_void_p, EventCallbackType]
 *   hooks.install_hooks.restype  = ctypes.c_int
 *   result = hooks.install_hooks(hwnd, callback)
 */

#include <windows.h>

// ── Globals ────────────────────────────────────────────────────────────────

static HHOOK g_keyboard_hook = NULL;
static HWND  g_exam_hwnd     = NULL;

// Callback type — matches Python ctypes.CFUNCTYPE(None, c_char_p, c_int)
typedef void (*EventCallback)(const char* event_type, int vk_code);
static EventCallback g_callback = NULL;


// ── DLL Entry Point ────────────────────────────────────────────────────────

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    // No per-thread or per-process init needed
    return TRUE;
}


// ── Keyboard Hook Procedure ────────────────────────────────────────────────

LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode < 0) {
        return CallNextHookEx(g_keyboard_hook, nCode, wParam, lParam);
    }

    KBDLLHOOKSTRUCT* p = (KBDLLHOOKSTRUCT*)lParam;
    DWORD vk           = p->vkCode;
    bool  keyDown      = (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN);

    if (keyDown) {
        bool alt   = (GetAsyncKeyState(VK_MENU)    & 0x8000) != 0;
        bool ctrl  = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
        bool shift = (GetAsyncKeyState(VK_SHIFT)   & 0x8000) != 0;

        // ── Win keys (covers Win+D, Win+Tab, Win+L, Win+R etc.) ───────
        if (vk == VK_LWIN || vk == VK_RWIN) {
            if (g_callback) g_callback("WIN_KEY", (int)vk);
            return 1;
        }

        // ── Alt+Tab ────────────────────────────────────────────────────
        if (alt && vk == VK_TAB) {
            if (g_callback) g_callback("ALT_TAB", (int)vk);
            return 1;
        }

        // ── Alt+F4 ─────────────────────────────────────────────────────
        if (alt && vk == VK_F4) {
            if (g_callback) g_callback("ALT_F4", (int)vk);
            return 1;
        }

        // ── PrintScreen ────────────────────────────────────────────────
        if (vk == VK_SNAPSHOT) {
            if (g_callback) g_callback("PRINT_SCREEN", (int)vk);
            return 1;
        }

        // ── Ctrl+Shift+Esc (Task Manager) — MUST check before Ctrl+Esc
        if (ctrl && shift && vk == VK_ESCAPE) {
            if (g_callback) g_callback("TASK_MANAGER", (int)vk);
            return 1;
        }

        // ── Ctrl+Esc (Start menu) ──────────────────────────────────────
        if (ctrl && vk == VK_ESCAPE) {
            if (g_callback) g_callback("CTRL_ESC", (int)vk);
            return 1;
        }
    }

    return CallNextHookEx(g_keyboard_hook, nCode, wParam, lParam);
}


// ── Exported API ───────────────────────────────────────────────────────────

extern "C" {

    /*
     * Install the keyboard hook.
     * exam_hwnd: handle to the exam window (for context)
     * callback:  Python callback fired on every blocked key
     * Returns:   0 on success, Win32 error code on failure
     */
    __declspec(dllexport)
    int install_hooks(HWND exam_hwnd, EventCallback callback) {
        g_exam_hwnd = exam_hwnd;
        g_callback  = callback;

        g_keyboard_hook = SetWindowsHookEx(
            WH_KEYBOARD_LL,
            LowLevelKeyboardProc,
            GetModuleHandle(NULL),
            0   // 0 = global hook (all threads on the desktop)
        );

        if (!g_keyboard_hook) {
            return (int)GetLastError();
        }
        return 0;
    }


    /*
     * Uninstall the keyboard hook.
     * Call this when the exam ends or the app closes.
     */
    __declspec(dllexport)
    void uninstall_hooks() {
        if (g_keyboard_hook) {
            UnhookWindowsHookEx(g_keyboard_hook);
            g_keyboard_hook = NULL;
        }
    }


static DWORD g_pump_thread_id = 0;

    /*
     * Message pump — REQUIRED for the hook to fire.
     * Run this on a dedicated background thread from Python:
     *
     *   pump_thread = threading.Thread(
     *       target=dll.run_message_pump, daemon=True
     *   )
     *   pump_thread.start()
     *
     * The hook will NOT intercept any keys without this running.
     */
    __declspec(dllexport)
    void run_message_pump() {
        g_pump_thread_id = GetCurrentThreadId();
        MSG msg;
        while (GetMessage(&msg, NULL, 0, 0)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        g_pump_thread_id = 0;
    }


    /*
     * Stop the message pump — call before uninstall_hooks().
     * Posts WM_QUIT to the message loop thread.
     */
    __declspec(dllexport)
    void stop_message_pump() {
        if (g_pump_thread_id != 0) {
            PostThreadMessage(g_pump_thread_id, WM_QUIT, 0, 0);
        }
    }

}  // extern "C"