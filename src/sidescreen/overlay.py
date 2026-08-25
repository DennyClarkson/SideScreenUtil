from __future__ import annotations

import math
import time

import numpy as np
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget

from sidescreen.i18n import tr
from sidescreen.layouts import grid_layout, normalized_rect
from sidescreen.models import AppSettings
from sidescreen.motion import DriftMotion
from sidescreen.win32_api import make_window_no_activate


class MonitorOverlay(QWidget):
    def __init__(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._frames: dict[int, QImage] = {}
        self._frame_buffers: dict[int, np.ndarray] = {}
        self._titles: dict[int, str] = {}
        self._settings = AppSettings()
        self._motion = DriftMotion()
        self._screen: QScreen | None = None
        self._active = False
        self._pointer_suppressed = False
        self._session_started_at = time.monotonic()
        self._layout: dict[int, QRectF] = {}
        self._layout_from: dict[int, QRectF] = {}
        self._layout_target: dict[int, QRectF] = {}
        self._layout_started_at = 0.0
        self._layout_duration = 0.46
        self._fade: QPropertyAnimation | None = None
        self._layout_editing = False
        self._edit_composition: QRectF | None = None
        self._edit_selected: int | None = None
        self._edit_action = ""
        self._drag_offset = (0.0, 0.0)
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self.update)

    layout_edited = Signal(object)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def pointer_suppressed(self) -> bool:
        return self._pointer_suppressed

    @property
    def layout_editing(self) -> bool:
        return self._layout_editing

    @property
    def frame_sizes(self) -> dict[int, tuple[int, int]]:
        return {key: (image.width(), image.height()) for key, image in self._frames.items()}

    def activate(self, screen: QScreen, settings: AppSettings) -> None:
        self._screen = screen
        self.update_settings(settings)
        self._motion.reset()
        self._session_started_at = time.monotonic()
        self._active = True
        self._pointer_suppressed = False
        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.setWindowOpacity(0.0)
        self.show()
        make_window_no_activate(int(self.winId()))
        self.raise_()
        self._fade_to(1.0, 420, QEasingCurve.Type.OutCubic)
        self._animation_timer.start()

    def update_settings(self, settings: AppSettings) -> None:
        self._settings = settings.normalized()
        self._motion.configure(self._settings.move_seconds, self._settings.size_variation)
        self.update()

    def deactivate(self, animated: bool = True) -> None:
        if self._layout_editing:
            self.finish_layout_editing(False)
        self._active = False
        self._pointer_suppressed = False
        if animated and self.isVisible():
            self._fade_to(0.0, 220, QEasingCurve.Type.InCubic, self._finish_deactivate)
        else:
            self._finish_deactivate()

    def _finish_deactivate(self) -> None:
        if self._active:
            return
        self._animation_timer.stop()
        self.hide()
        self.setWindowOpacity(1.0)
        self._frames.clear()
        self._frame_buffers.clear()
        self._layout.clear()

    def suppress_for_pointer(self) -> None:
        if self._active and not self._layout_editing and not self._pointer_suppressed:
            self._pointer_suppressed = True
            self._fade_to(0.0, 110, QEasingCurve.Type.InCubic, self._finish_pointer_hide)

    def _finish_pointer_hide(self) -> None:
        if self._active and self._pointer_suppressed:
            self.hide()

    def reveal(self) -> None:
        if not self._active:
            return
        self._pointer_suppressed = False
        if self._screen is not None:
            self.setGeometry(self._screen.geometry())
        self.setWindowOpacity(0.0)
        self.show()
        make_window_no_activate(int(self.winId()))
        self.raise_()
        self._fade_to(1.0, 320, QEasingCurve.Type.OutCubic)

    def _fade_to(
        self,
        opacity: float,
        duration: int,
        easing: QEasingCurve.Type,
        finished: object | None = None,
    ) -> None:
        if self._fade is not None:
            self._fade.stop()
            self._fade.deleteLater()
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(opacity)
        animation.setDuration(duration)
        animation.setEasingCurve(easing)
        if callable(finished):
            animation.finished.connect(finished)
        animation.start()
        self._fade = animation

    def set_sources(self, window_ids: list[int]) -> None:
        valid = set(window_ids)
        for key in list(self._frames):
            if key not in valid:
                self._frames.pop(key, None)
                self._frame_buffers.pop(key, None)
        if not self._layout_target or set(self._layout_target) != valid:
            self.set_layout(grid_layout(window_ids))

    def set_source_titles(self, titles: dict[int, str]) -> None:
        self._titles = dict(titles)

    def set_layout(self, layout: dict[int, QRectF], animate: bool = True) -> None:
        target = {key: normalized_rect(value) for key, value in layout.items()}
        now = time.monotonic()
        current = self._interpolated_layout(now)
        self._layout_from = {}
        for key, rectangle in target.items():
            if key in current:
                self._layout_from[key] = current[key]
            else:
                center = rectangle.center()
                self._layout_from[key] = QRectF(center.x(), center.y(), 0.01, 0.01)
        self._layout_target = target
        self._layout_started_at = now
        if not animate:
            self._layout = target.copy()
            self._layout_from = target.copy()
        self.update()

    def set_frame(self, hwnd: int, data: object, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if isinstance(data, np.ndarray):
            frame = np.ascontiguousarray(data)
        else:
            try:
                frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4)).copy()
            except (TypeError, ValueError):
                return
        if frame.ndim != 3 or frame.shape[0] != height or frame.shape[1] != width:
            return
        image = QImage(
            frame.data,
            width,
            height,
            int(frame.strides[0]),
            QImage.Format.Format_ARGB32,
        )
        # Destroy the previous QImage before releasing the array it references.
        self._frames[hwnd] = image
        self._frame_buffers[hwnd] = frame
        self.update()

    def start_layout_editing(self) -> bool:
        if not self._active or not self._layout_target:
            return False
        if self._pointer_suppressed or not self.isVisible():
            self.reveal()
        now = time.monotonic()
        current = self._interpolated_layout(now)
        self._layout = {key: QRectF(value) for key, value in current.items()}
        self._layout_target = {key: QRectF(value) for key, value in current.items()}
        self._layout_from = {key: QRectF(value) for key, value in current.items()}
        self._layout_editing = True
        self._edit_composition = self._composition_rect(now)
        self._edit_selected = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        return True

    def finish_layout_editing(self, emit: bool = True) -> None:
        if not self._layout_editing:
            return
        self._layout_editing = False
        self._edit_composition = None
        self._edit_selected = None
        self._edit_action = ""
        self.setCursor(Qt.CursorShape.BlankCursor)
        layout = {key: QRectF(value) for key, value in self._layout_target.items()}
        self.update()
        if emit:
            self.layout_edited.emit(layout)

    def toggle_layout_editing(self) -> bool:
        if self._layout_editing:
            self.finish_layout_editing()
            return False
        return self.start_layout_editing()

    def _is_periodic_blank(self, now: float) -> bool:
        every = self._settings.blank_every_minutes * 60
        duration = self._settings.blank_seconds
        if every <= 0 or duration <= 0:
            return False
        elapsed = max(0.0, now - self._session_started_at)
        cycle = every + duration
        return elapsed % cycle >= every

    def _composition_rect(self, now: float) -> QRectF:
        if self._layout_editing and self._edit_composition is not None:
            return QRectF(self._edit_composition)
        available_width = max(1, self.width())
        available_height = max(1, self.height())
        motion = self._motion.sample(now)
        scale = self._settings.preview_scale * motion.scale
        width = max(1.0, available_width * scale)
        height = max(1.0, available_height * scale)
        free_x = max(0.0, available_width - width)
        free_y = max(0.0, available_height - height)
        return QRectF(free_x * motion.x, free_y * motion.y, width, height)

    def _interpolated_layout(self, now: float) -> dict[int, QRectF]:
        if not self._layout_target:
            return self._layout
        progress = min(1.0, max(0.0, (now - self._layout_started_at) / self._layout_duration))
        eased = 0.5 - 0.5 * math.cos(progress * math.pi)
        result: dict[int, QRectF] = {}
        for key, target in self._layout_target.items():
            start = self._layout_from.get(key, target)
            result[key] = QRectF(
                start.x() + (target.x() - start.x()) * eased,
                start.y() + (target.y() - start.y()) * eased,
                start.width() + (target.width() - start.width()) * eased,
                start.height() + (target.height() - start.height()) * eased,
            )
        self._layout = result
        return result

    @staticmethod
    def _fit_image(image: QImage, cell: QRectF) -> QRectF:
        if image.isNull() or cell.isEmpty():
            return QRectF()
        image_ratio = image.width() / max(1, image.height())
        cell_ratio = cell.width() / max(1.0, cell.height())
        if image_ratio > cell_ratio:
            width = cell.width()
            height = width / image_ratio
        else:
            height = cell.height()
            width = height * image_ratio
        return QRectF(
            cell.center().x() - width / 2,
            cell.center().y() - height / 2,
            width,
            height,
        )

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        now = time.monotonic()
        if not self._frames or (self._is_periodic_blank(now) and not self._layout_editing):
            return
        composition = self._composition_rect(now)
        layout = self._interpolated_layout(now)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        for hwnd, normalized in layout.items():
            image = self._frames.get(hwnd)
            if image is None or image.isNull():
                continue
            cell = QRectF(
                composition.x() + normalized.x() * composition.width(),
                composition.y() + normalized.y() * composition.height(),
                normalized.width() * composition.width(),
                normalized.height() * composition.height(),
            )
            painter.drawImage(self._fit_image(image, cell), image)
            if self._layout_editing:
                selected = hwnd == self._edit_selected
                color = QColor("#ffffff") if selected else QColor(255, 255, 255, 150)
                painter.setPen(QPen(color, 3 if selected else 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(cell, 7, 7)
                painter.fillRect(
                    QRectF(cell.right() - 15, cell.bottom() - 15, 13, 13),
                    QColor("#ffffff"),
                )
                title = self._titles.get(hwnd, f"{tr('common.window')} {hwnd}")
                painter.setPen(QColor("#ffffff"))
                painter.fillRect(
                    QRectF(cell.left(), cell.top(), min(cell.width(), 280), 28),
                    QColor(0, 0, 0, 190),
                )
                painter.drawText(
                    QRectF(cell.left() + 8, cell.top(), min(cell.width() - 12, 264), 28),
                    Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                    title,
                )
        if self._layout_editing:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 210))
            banner = QRectF(max(18, self.width() / 2 - 265), 18, 530, 44)
            painter.drawRoundedRect(banner, 12, 12)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                banner,
                Qt.AlignmentFlag.AlignCenter,
                tr("layout.overlay_banner"),
            )

    def _cell_rect(self, normalized: QRectF) -> QRectF:
        composition = self._composition_rect(time.monotonic())
        return QRectF(
            composition.x() + normalized.x() * composition.width(),
            composition.y() + normalized.y() * composition.height(),
            normalized.width() * composition.width(),
            normalized.height() * composition.height(),
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._layout_editing or event.button() != Qt.MouseButton.LeftButton:
            return
        position = event.position()
        self._edit_selected = None
        for hwnd in reversed(list(self._layout_target)):
            rectangle = self._layout_target[hwnd]
            cell = self._cell_rect(rectangle)
            if cell.adjusted(-3, -3, 3, 3).contains(position):
                self._edit_selected = hwnd
                handle = QRectF(cell.right() - 24, cell.bottom() - 24, 28, 28)
                self._edit_action = "resize" if handle.contains(position) else "move"
                composition = self._composition_rect(time.monotonic())
                nx = (position.x() - composition.x()) / max(1.0, composition.width())
                ny = (position.y() - composition.y()) / max(1.0, composition.height())
                self._drag_offset = (nx - rectangle.x(), ny - rectangle.y())
                break
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._layout_editing or self._edit_selected is None or not self._edit_action:
            return
        composition = self._composition_rect(time.monotonic())
        nx = (event.position().x() - composition.x()) / max(1.0, composition.width())
        ny = (event.position().y() - composition.y()) / max(1.0, composition.height())
        rectangle = QRectF(self._layout_target[self._edit_selected])
        if self._edit_action == "resize":
            rectangle.setWidth(max(0.08, nx - rectangle.x()))
            rectangle.setHeight(max(0.08, ny - rectangle.y()))
        else:
            rectangle.moveTo(nx - self._drag_offset[0], ny - self._drag_offset[1])
        rectangle = normalized_rect(rectangle)
        self._layout_target[self._edit_selected] = rectangle
        self._layout[self._edit_selected] = QRectF(rectangle)
        self._layout_from[self._edit_selected] = QRectF(rectangle)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._layout_editing and event.button() == Qt.MouseButton.LeftButton:
            self._edit_action = ""
            event.accept()
