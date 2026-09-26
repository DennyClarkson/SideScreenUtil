"""Exercise real GDI row order, without relying on WGC failing by chance."""

import ctypes

import numpy as np
import win32con
import win32gui

from sidescreen.win32_api import capture_window_bgra


def test_printwindow_keeps_top_and_bottom_in_order(monkeypatch):
    def paint(hwnd, message, dc, flags):
        if message in (win32con.WM_PRINT, win32con.WM_PRINTCLIENT, win32con.WM_PAINT):
            paint_state = None
            if message == win32con.WM_PAINT:
                dc, paint_state = win32gui.BeginPaint(hwnd)
            top = win32gui.CreateSolidBrush(0x0000FF)
            bottom = win32gui.CreateSolidBrush(0xFF0000)
            try:
                win32gui.FillRect(dc, (0, 0, 80, 30), top)
                win32gui.FillRect(dc, (0, 30, 80, 60), bottom)
            finally:
                win32gui.DeleteObject(top)
                win32gui.DeleteObject(bottom)
                if paint_state is not None:
                    win32gui.EndPaint(hwnd, paint_state)
            return 0
        return win32gui.DefWindowProc(hwnd, message, dc, flags)

    window_class = win32gui.WNDCLASS()
    window_class.lpszClassName = "SideScreenOrientationTest"
    window_class.lpfnWndProc = paint
    atom = win32gui.RegisterClass(window_class)
    hwnd = win32gui.CreateWindowEx(
        0, atom, "Orientation test", win32con.WS_POPUP, 0, 0, 80, 60, 0, 0, 0, None
    )

    def print_pattern(window, dc, flags):
        paint(window, win32con.WM_PRINT, dc, flags)
        return 1

    monkeypatch.setattr(ctypes.windll.user32, "PrintWindow", print_pattern)
    try:
        data, width, height = capture_window_bgra(hwnd)
        pixels = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)
        assert pixels[5, 5, :3].tolist() == [0, 0, 255]
        assert pixels[-5, 5, :3].tolist() == [255, 0, 0]
    finally:
        win32gui.DestroyWindow(hwnd)
        win32gui.UnregisterClass(atom, 0)
        ctypes.windll.kernel32.SetLastError(0)
