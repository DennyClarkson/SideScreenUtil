from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QScreen

from sidescreen.i18n import tr


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
    geometry = screen.geometry()
    primary = f" · {tr('display.primary')}" if screen is QGuiApplication.primaryScreen() else ""
    model = " ".join(part for part in (screen.manufacturer(), screen.model()) if part).strip()
    name = model or screen.name() or tr("display.fallback", number=index + 1)
    return (
        f"{index + 1}. {name} — {geometry.width()}×{geometry.height()} "
        f"({geometry.x()}, {geometry.y()}){primary}"
    )


def find_screen(identity: str) -> QScreen | None:
    for screen in QGuiApplication.screens():
        if screen_id(screen) == identity:
            return screen
    return None
