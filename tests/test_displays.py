from PySide6.QtCore import QRect

from sidescreen.displays import physical_pixel_size


class ScaledScreen:
    def geometry(self) -> QRect:
        return QRect(-634, 1080, 1707, 1067)

    def devicePixelRatio(self) -> float:  # noqa: N802 - mirrors QScreen
        return 1.5


def test_physical_pixel_size_accounts_for_windows_display_scaling() -> None:
    assert physical_pixel_size(ScaledScreen()) == (2560, 1600)
