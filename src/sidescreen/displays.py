from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QScreen

from sidescreen.i18n import tr


def physical_pixel_size(screen: QScreen) -> tuple[int, int]:
    """Return the current output size instead of Qt's DPI-scaled desktop size."""
    geometry = screen.geometry()
    ratio = max(1.0, float(screen.devicePixelRatio()))
    return round(geometry.width() * ratio), round(geometry.height() * ratio)


def screen_id(screen: QScreen) -> str:
    identity = "|".join(
        part.strip()
        for part in (
            screen.manufacturer(),
            screen.model(),
            screen.serialNumber(),
            screen.name(),
        )
        if part and part.strip()
    )
    if screen.serialNumber():
        return identity
    geometry = screen.geometry()
    return f"{identity}|{geometry.width()}x{geometry.height()}@{geometry.x()},{geometry.y()}"


def screen_label(screen: QScreen, index: int) -> str:
    primary = f" · {tr('display.primary')}" if screen is QGuiApplication.primaryScreen() else ""
    name = (
        screen.model().strip()
        or screen.manufacturer().strip()
        or screen.name().strip()
        or tr("display.fallback", number=index + 1)
    )
    width, height = physical_pixel_size(screen)
    scale = round(float(screen.devicePixelRatio()) * 100)
    return f"{index + 1}. {name} — {width}×{height} · {scale}%{primary}"


def find_screen(identity: str) -> QScreen | None:
    for screen in QGuiApplication.screens():
        if screen_id(screen) == identity:
            return screen
    return None
