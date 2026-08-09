from __future__ import annotations

import ctypes
import importlib.util
import logging
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from sidescreen.filters import FilterConfig, apply_filter
from sidescreen.i18n import tr
from sidescreen.models import WindowInfo
from sidescreen.win32_api import capture_window_bgra

LOGGER = logging.getLogger(__name__)
_NATIVE_MODULE: ModuleType | None = None
_MAX_CACHED_PIXELS = 1_000_000
_MAX_CACHED_DIMENSION = 1600


def _compact_frame(frame: np.ndarray, limit_resolution: bool = True) -> np.ndarray:
    """Own and, when needed, downsample a frame before it enters persistent caches."""
    if not limit_resolution:
        return np.array(frame, copy=True, order="C")
    height, width = frame.shape[:2]
    scale = min(
        1.0,
        (_MAX_CACHED_PIXELS / max(1, width * height)) ** 0.5,
        _MAX_CACHED_DIMENSION / max(1, width, height),
    )
    if scale >= 0.999:
        return np.array(frame, copy=True, order="C")
    target_width = max(1, round(width * scale))
    target_height = max(1, round(height * scale))
    x_indices = np.linspace(0, width - 1, target_width, dtype=np.int32)
    y_indices = np.linspace(0, height - 1, target_height, dtype=np.int32)
    return np.ascontiguousarray(frame[y_indices[:, None], x_indices[None, :], :])


def _load_native_capture() -> ModuleType:
    """Load the small WGC extension without importing its optional OpenCV wrapper."""
    global _NATIVE_MODULE
    if _NATIVE_MODULE is not None:
        return _NATIVE_MODULE
    path = Path(__file__).resolve().parent / "native" / "windows_capture.pyd"
    if not path.exists():
        raise RuntimeError(f"WGC native module is missing: {path}")
    module_name = "_sidescreen_wgc.windows_capture"
    specification = importlib.util.spec_from_file_location(module_name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError("Unable to load the WGC native module")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    _NATIVE_MODULE = module
    return module


class GdiCaptureWorker(QThread):
    frame_ready = Signal(object, int, int)
    failed = Signal(str)
    source_closed = Signal()

    def __init__(
        self,
        hwnd: int,
        fps: int,
        filter_provider: Any,
        resolution_limit_provider: Any,
    ) -> None:
        super().__init__()
        self.hwnd = hwnd
        self.fps = max(1, fps)
        self._filter_provider = filter_provider
        self._resolution_limit_provider = resolution_limit_provider
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()

    def run(self) -> None:
        delay = 1.0 / self.fps
        consecutive_errors = 0
        while not self._stopping.is_set():
            started = time.monotonic()
            try:
                data, width, height = capture_window_bgra(self.hwnd)
                raw = _compact_frame(
                    np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4)),
                    self._resolution_limit_provider(),
                )
                filtered = apply_filter(raw, self._filter_provider())
                consecutive_errors = 0
                self.frame_ready.emit(filtered, filtered.shape[1], filtered.shape[0])
            except RuntimeError as exc:
                consecutive_errors += 1
                if "关闭" in str(exc) or "closed" in str(exc).lower():
                    self.source_closed.emit()
                    return
                if consecutive_errors >= 3:
                    self.failed.emit(str(exc))
                    consecutive_errors = 0
            elapsed = time.monotonic() - started
            self._stopping.wait(max(0.0, delay - elapsed))


class CaptureSession(QObject):
    frame_ready = Signal(object, int, int)
    failed = Signal(str)
    source_closed = Signal()
    backend_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._capture: Any = None
        self._capture_control: Any = None
        self._gdi_worker: GdiCaptureWorker | None = None
        self._running = False
        self._generation = 0
        self._last_frame_at = 0.0
        self._minimum_interval = 1 / 12
        self._filter_config = FilterConfig()
        self._last_raw_frame: np.ndarray | None = None
        self._limit_resolution = True

    def start(self, window: WindowInfo, fps: int, filter_config: FilterConfig) -> None:
        self.stop()
        self._filter_config = filter_config
        self._running = True
        generation = self._generation
        self._minimum_interval = 1 / max(1, fps)
        try:
            self._start_wgc(window, generation)
            self.backend_changed.emit("WGC")
        except Exception as exc:
            LOGGER.exception("WGC start failed; falling back to PrintWindow")
            self.failed.emit(tr("capture.wgc_fallback", error=exc))
            self._start_gdi(window, fps)
            self.backend_changed.emit("PrintWindow")

    def _start_wgc(self, window: WindowInfo, generation: int) -> None:
        native = _load_native_capture()

        def on_frame_arrived(
            buffer_pointer: int,
            buffer_length: int,
            width: int,
            height: int,
            _stop_list: list[bool],
            _timespan: int,
        ) -> None:
            if not self._running or generation != self._generation:
                return
            now = time.monotonic()
            if now - self._last_frame_at < self._minimum_interval * 0.80:
                return
            self._last_frame_at = now
            row_pitch = int(buffer_length / height)
            if row_pitch < width * 4:
                return
            pointer = ctypes.cast(buffer_pointer, ctypes.POINTER(ctypes.c_uint8))
            raw = np.ctypeslib.as_array(pointer, shape=(height, row_pitch))
            frame = _compact_frame(
                raw[:, : width * 4].reshape(height, width, 4),
                self._limit_resolution,
            )
            self._publish_frame(frame, now)

        def on_closed() -> None:
            if self._running and generation == self._generation:
                self.source_closed.emit()

        self._capture = native.NativeWindowsCapture(
            on_frame_arrived,
            on_closed,
            False,
            False,
            False,
            max(1, int(self._minimum_interval * 1000)),
            False,
            None,
            None,
            window.hwnd,
        )
        self._capture_control = self._capture.start_free_threaded()

    def _start_gdi(self, window: WindowInfo, fps: int) -> None:
        worker = GdiCaptureWorker(
            window.hwnd,
            fps,
            lambda: self._filter_config,
            lambda: self._limit_resolution,
        )
        worker.frame_ready.connect(self.frame_ready)
        worker.failed.connect(self.failed)
        worker.source_closed.connect(self.source_closed)
        self._gdi_worker = worker
        worker.start()

    def _publish_frame(self, raw: np.ndarray, now: float | None = None) -> None:
        self._last_raw_frame = raw
        filtered = apply_filter(raw, self._filter_config, now)
        self.frame_ready.emit(filtered, filtered.shape[1], filtered.shape[0])

    def set_filter(self, filter_config: FilterConfig, refresh: bool = True) -> None:
        self._filter_config = filter_config
        if refresh:
            self.refresh_last_frame()

    def set_resolution_limit(self, enabled: bool) -> None:
        self._limit_resolution = bool(enabled)

    def refresh_last_frame(self) -> None:
        if self._running and self._last_raw_frame is not None:
            filtered = apply_filter(self._last_raw_frame, self._filter_config)
            self.frame_ready.emit(filtered, filtered.shape[1], filtered.shape[0])

    def stop(self) -> None:
        self._running = False
        self._generation += 1
        if self._capture_control is not None:
            try:
                self._capture_control.stop()
            except Exception:
                LOGGER.exception("Failed to stop WGC capture")
        self._capture_control = None
        self._capture = None
        if self._gdi_worker is not None:
            self._gdi_worker.stop()
            self._gdi_worker.wait(1500)
            self._gdi_worker = None
        self._last_raw_frame = None
