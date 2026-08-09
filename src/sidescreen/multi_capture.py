from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from sidescreen.capture import CaptureSession
from sidescreen.filters import FilterConfig
from sidescreen.i18n import tr
from sidescreen.models import WindowInfo


class MultiCaptureManager(QObject):
    frame_ready = Signal(int, object, int, int)
    warning = Signal(str)
    source_closed = Signal(int)
    backends_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._sessions: dict[int, CaptureSession] = {}
        self._windows: dict[int, WindowInfo] = {}
        self._backends: dict[int, str] = {}
        self._filter = FilterConfig()
        self._fps = 12
        self._limit_resolution = True

    @property
    def window_ids(self) -> set[int]:
        return set(self._sessions)

    def sync_windows(
        self,
        windows: list[WindowInfo],
        fps: int,
        filter_config: FilterConfig,
        limit_resolution: bool = True,
    ) -> None:
        desired = {window.hwnd: window for window in windows}
        if fps != self._fps and self._sessions:
            self.stop_all()
        self._fps = fps
        self._filter = filter_config
        self._limit_resolution = bool(limit_resolution)

        for session in self._sessions.values():
            session.set_resolution_limit(self._limit_resolution)

        for hwnd in set(self._sessions) - set(desired):
            self._remove(hwnd)
        for hwnd, window in desired.items():
            self._windows[hwnd] = window
            if hwnd not in self._sessions:
                self._add(window)
        self._emit_backends()

    def _add(self, window: WindowInfo) -> None:
        session = CaptureSession()
        hwnd = window.hwnd
        session.frame_ready.connect(
            lambda data, width, height, key=hwnd: self.frame_ready.emit(key, data, width, height)
        )
        session.failed.connect(self.warning)
        session.source_closed.connect(lambda key=hwnd: self._closed(key))
        session.backend_changed.connect(lambda backend, key=hwnd: self._backend(key, backend))
        self._sessions[hwnd] = session
        session.set_resolution_limit(self._limit_resolution)
        session.start(window, self._fps, self._filter)

    def _remove(self, hwnd: int) -> None:
        session = self._sessions.pop(hwnd, None)
        if session is not None:
            session.stop()
            session.deleteLater()
        self._windows.pop(hwnd, None)
        self._backends.pop(hwnd, None)

    def _closed(self, hwnd: int) -> None:
        self._remove(hwnd)
        self.source_closed.emit(hwnd)
        self._emit_backends()

    def _backend(self, hwnd: int, backend: str) -> None:
        self._backends[hwnd] = backend
        self._emit_backends()

    def _emit_backends(self) -> None:
        if not self._sessions:
            self.backends_changed.emit(tr("capture.none"))
            return
        counts: dict[str, int] = {}
        for hwnd in self._sessions:
            backend = self._backends.get(hwnd, tr("capture.starting"))
            counts[backend] = counts.get(backend, 0) + 1
        summary = " · ".join(f"{name} ×{count}" for name, count in counts.items())
        self.backends_changed.emit(summary)

    def set_filter(self, filter_config: FilterConfig) -> None:
        self._filter = filter_config
        for session in self._sessions.values():
            session.set_filter(filter_config)

    def set_resolution_limit(self, enabled: bool) -> None:
        self._limit_resolution = bool(enabled)
        for session in self._sessions.values():
            session.set_resolution_limit(self._limit_resolution)

    def refresh_animated_filters(self) -> None:
        if self._filter.animated:
            for session in self._sessions.values():
                session.refresh_last_frame()

    def stop_all(self) -> None:
        for hwnd in list(self._sessions):
            self._remove(hwnd)
        self._emit_backends()
