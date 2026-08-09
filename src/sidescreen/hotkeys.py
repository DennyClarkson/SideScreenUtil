from __future__ import annotations

import ctypes

from PySide6.QtCore import QObject, QTimer, Signal


class GlobalLayoutHotkey(QObject):
    """Edge-triggered Ctrl+Alt+L watcher that works outside the control window."""

    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._was_down = False
        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    @staticmethod
    def _down(key: int) -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000)

    def _poll(self) -> None:
        pressed = self._down(0x11) and self._down(0x12) and self._down(ord("L"))
        if pressed and not self._was_down:
            self.activated.emit()
        self._was_down = pressed
