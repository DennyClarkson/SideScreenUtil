from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from sidescreen.i18n import tr
from sidescreen.layouts import normalized_rect


class LayoutEditor(QWidget):
    layout_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(300, 210)
        self.setMouseTracking(True)
        self._titles: dict[int, str] = {}
        self._layout: dict[int, QRectF] = {}
        self._selected: int | None = None
        self._drag_origin = QPointF()
        self._original = QRectF()
        self._resizing = False

    def set_items(self, titles: dict[int, str], layout: dict[int, QRectF]) -> None:
        self._titles = titles.copy()
        self._layout = {key: QRectF(value) for key, value in layout.items() if key in titles}
        if self._selected not in titles:
            self._selected = None
        self.update()

    def set_layout(self, layout: dict[int, QRectF]) -> None:
        self._layout = {key: normalized_rect(QRectF(value)) for key, value in layout.items()}
        self.update()

    def layout_data(self) -> dict[int, QRectF]:
        return {key: QRectF(value) for key, value in self._layout.items()}

    def _canvas(self) -> QRectF:
        outer = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        ratio = 16 / 9
        if outer.width() / max(1.0, outer.height()) > ratio:
            width = outer.height() * ratio
            return QRectF(outer.center().x() - width / 2, outer.y(), width, outer.height())
        height = outer.width() / ratio
        return QRectF(outer.x(), outer.center().y() - height / 2, outer.width(), height)

    def _to_pixels(self, rectangle: QRectF) -> QRectF:
        canvas = self._canvas()
        return QRectF(
            canvas.x() + rectangle.x() * canvas.width(),
            canvas.y() + rectangle.y() * canvas.height(),
            rectangle.width() * canvas.width(),
            rectangle.height() * canvas.height(),
        )

    def _to_normalized_delta(self, delta: QPointF) -> QPointF:
        canvas = self._canvas()
        return QPointF(delta.x() / canvas.width(), delta.y() / canvas.height())

    def _hit_test(self, position: QPointF) -> tuple[int | None, bool]:
        for key in reversed(list(self._layout)):
            rectangle = self._to_pixels(self._layout[key])
            handle = QRectF(rectangle.right() - 16, rectangle.bottom() - 16, 20, 20)
            if handle.contains(position):
                return key, True
            if rectangle.contains(position):
                return key, False
        return None, False

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        key, resizing = self._hit_test(event.position())
        self._selected = key
        self._resizing = resizing
        self._drag_origin = event.position()
        self._original = QRectF(self._layout.get(key, QRectF()))
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._selected is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            key, resizing = self._hit_test(event.position())
            self.setCursor(
                Qt.CursorShape.SizeFDiagCursor
                if key is not None and resizing
                else Qt.CursorShape.SizeAllCursor
                if key is not None
                else Qt.CursorShape.ArrowCursor
            )
            return
        delta = self._to_normalized_delta(event.position() - self._drag_origin)
        rectangle = QRectF(self._original)
        if self._resizing:
            rectangle.setWidth(rectangle.width() + delta.x())
            rectangle.setHeight(rectangle.height() + delta.y())
        else:
            rectangle.translate(delta)
        self._layout[self._selected] = normalized_rect(rectangle)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._selected is not None:
            self.layout_changed.emit(self.layout_data())

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        canvas = self._canvas()
        painter.setPen(QPen(QColor("#24324a"), 1))
        painter.setBrush(QColor("#050912"))
        painter.drawRoundedRect(canvas, 12, 12)
        if not self._layout:
            painter.setPen(QColor("#64748b"))
            painter.drawText(canvas, Qt.AlignmentFlag.AlignCenter, tr("layout.empty"))
            return
        for index, (key, normalized) in enumerate(self._layout.items()):
            rectangle = self._to_pixels(normalized).adjusted(2, 2, -2, -2)
            selected = key == self._selected
            hue = (195 + index * 47) % 360
            fill = QColor.fromHsv(hue, 120, 72 if not selected else 92)
            border = QColor("#22d3ee") if selected else QColor.fromHsv(hue, 180, 210)
            painter.setPen(QPen(border, 2 if selected else 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rectangle, 8, 8)
            painter.setPen(QColor("#e6f7ff"))
            title = self._titles.get(key, tr("common.window"))
            text = painter.fontMetrics().elidedText(
                title, Qt.TextElideMode.ElideRight, max(20, int(rectangle.width() - 18))
            )
            painter.drawText(rectangle.adjusted(9, 7, -9, -7), Qt.AlignmentFlag.AlignTop, text)
            if selected:
                painter.setBrush(QColor("#22d3ee"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(rectangle.bottomRight() - QPointF(7, 7), 4, 4)
