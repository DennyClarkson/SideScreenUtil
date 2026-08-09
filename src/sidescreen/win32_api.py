from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes
from pathlib import Path

import numpy as np
import win32api
import win32con
import win32gui
import win32process
import win32ui

from sidescreen.i18n import tr
from sidescreen.models import WindowInfo

LOGGER = logging.getLogger(__name__)

DWMWA_CLOAKED = 14
PW_RENDERFULLCONTENT = 0x00000002


def enable_per_monitor_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()


def _is_cloaked(hwnd: int) -> bool:
    value = wintypes.DWORD()
    try:
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd,
            DWMWA_CLOAKED,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
        return result == 0 and bool(value.value)
    except (AttributeError, OSError):
        return False


def _process_name(pid: int) -> str:
    process = None
    try:
        process = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
        path = win32process.GetModuleFileNameEx(process, 0)
        return Path(path).name
    except Exception:
        return ""
    finally:
        if process:
            try:
                process.Close()
            except Exception:
                pass


def enumerate_windows() -> list[WindowInfo]:
    own_pid = os.getpid()
    windows: list[WindowInfo] = []

    def callback(hwnd: int, _extra: object) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd) or _is_cloaked(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd).strip()
            if not title:
                return True
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            # Exclude tiny tray popups and utility surfaces that expose a title
            # but are not useful monitoring targets.
            if right - left < 160 or bottom - top < 90:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == own_pid:
                return True
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex_style & win32con.WS_EX_TOOLWINDOW:
                return True
            windows.append(WindowInfo(hwnd, title, _process_name(pid), pid))
        except Exception:
            pass
        finally:
            # Calls such as GetModuleFileNameEx may fail for protected processes
            # and leave a harmless thread-local error behind. EnumWindows in newer
            # pywin32 releases otherwise reports that stale error as its own.
            ctypes.windll.kernel32.SetLastError(0)
        return True

    # pywin32 312 can incorrectly turn a null LPARAM (None) into WinError 3.
    # Passing the numeric null value is stable across supported pywin32 versions.
    try:
        win32gui.EnumWindows(callback, 0)
    except Exception:
        # A non-interactive/off-screen Windows station can reject enumeration.
        # Keep the settings UI usable and allow the user to refresh after login.
        LOGGER.exception("Unable to enumerate top-level windows")
    windows.sort(key=lambda item: (item.process_name.casefold(), item.title.casefold()))
    return windows


def window_exists(hwnd: int) -> bool:
    return bool(win32gui.IsWindow(hwnd))


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    try:
        if not window_exists(hwnd):
            return None
        return tuple(int(value) for value in win32gui.GetWindowRect(hwnd))
    except Exception:
        return None


def capture_window_bgra(hwnd: int) -> tuple[bytes, int, int]:
    """Fallback capture for traditional Win32 windows using PrintWindow."""
    if not window_exists(hwnd):
        raise RuntimeError(tr("capture.window_closed"))
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise RuntimeError(tr("capture.invalid_size"))

    window_dc = win32gui.GetWindowDC(hwnd)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source_dc, width, height)
    memory_dc.SelectObject(bitmap)
    try:
        success = ctypes.windll.user32.PrintWindow(
            hwnd,
            memory_dc.GetSafeHdc(),
            PW_RENDERFULLCONTENT,
        )
        if not success:
            raise RuntimeError(tr("capture.print_failed"))
        raw = bitmap.GetBitmapBits(True)
        image = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 4))
        image = np.ascontiguousarray(np.flipud(image))
        return image.tobytes(), width, height
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def make_window_no_activate(hwnd: int) -> None:
    try:
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_SHOWWINDOW,
        )
    except Exception:
        pass
