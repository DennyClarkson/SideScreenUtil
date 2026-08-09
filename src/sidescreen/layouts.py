from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QRect, QRectF


def grid_layout(keys: Iterable[int]) -> dict[int, QRectF]:
    items = list(keys)
    if not items:
        return {}
    columns = math.ceil(math.sqrt(len(items)))
    rows = math.ceil(len(items) / columns)
    gap = 0.025
    cell_width = (1.0 - gap * (columns + 1)) / columns
    cell_height = (1.0 - gap * (rows + 1)) / rows
    return {
        key: QRectF(
            gap + (index % columns) * (cell_width + gap),
            gap + (index // columns) * (cell_height + gap),
            cell_width,
            cell_height,
        )
        for index, key in enumerate(items)
    }


def strip_layout(keys: Iterable[int], vertical: bool = False) -> dict[int, QRectF]:
    items = list(keys)
    if not items:
        return {}
    gap = 0.025
    size = (1.0 - gap * (len(items) + 1)) / len(items)
    if vertical:
        return {
            key: QRectF(gap, gap + index * (size + gap), 1.0 - gap * 2, size)
            for index, key in enumerate(items)
        }
    return {
        key: QRectF(gap + index * (size + gap), gap, size, 1.0 - gap * 2)
        for index, key in enumerate(items)
    }


def source_relative_layout(rectangles: dict[int, QRect]) -> dict[int, QRectF]:
    if not rectangles:
        return {}
    union = QRect()
    for rectangle in rectangles.values():
        union = rectangle if union.isNull() else union.united(rectangle)
    if union.width() <= 0 or union.height() <= 0:
        return grid_layout(rectangles)
    padding = 0.025
    usable = 1.0 - padding * 2
    return {
        key: QRectF(
            padding + (rectangle.x() - union.x()) / union.width() * usable,
            padding + (rectangle.y() - union.y()) / union.height() * usable,
            max(0.08, rectangle.width() / union.width() * usable),
            max(0.08, rectangle.height() / union.height() * usable),
        )
        for key, rectangle in rectangles.items()
    }


def normalized_rect(rectangle: QRectF) -> QRectF:
    width = min(1.0, max(0.08, rectangle.width()))
    height = min(1.0, max(0.08, rectangle.height()))
    x = min(1.0 - width, max(0.0, rectangle.x()))
    y = min(1.0 - height, max(0.0, rectangle.y()))
    return QRectF(x, y, width, height)
