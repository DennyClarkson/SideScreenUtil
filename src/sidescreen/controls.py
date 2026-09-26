from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSlider, QWidget


def apply_control_theme(application: QApplication) -> None:
    """Use one style and palette for controls, popups and dialogs alike."""
    application.setStyle("Fusion")
    palette = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: "#202020",
        QPalette.ColorRole.WindowText: "#ffffff",
        QPalette.ColorRole.Base: "#313131",
        QPalette.ColorRole.AlternateBase: "#383838",
        QPalette.ColorRole.Text: "#ffffff",
        QPalette.ColorRole.Button: "#323232",
        QPalette.ColorRole.ButtonText: "#ffffff",
        QPalette.ColorRole.Highlight: "#60cdff",
        QPalette.ColorRole.HighlightedText: "#102027",
        QPalette.ColorRole.ToolTipBase: "#2b2b2b",
        QPalette.ColorRole.ToolTipText: "#ffffff",
    }.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#858585"))
    application.setPalette(palette)


class ValueSlider(QWidget):
    """Compact slider with a stable, readable value label."""

    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        formatter: Callable[[int], str] | None = None,
    ) -> None:
        super().__init__()
        self._formatter = formatter or str
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setMinimumWidth(130)
        # Fusion's 15px size hint clips the stylesheet's 20px handle. Reserve
        # space on the slider itself; a taller wrapper cannot change its hint.
        self.slider.setMinimumHeight(32)
        self.label = QLabel()
        self.label.setMinimumWidth(116)
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label.setProperty("class", "sliderValue")
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.label)
        self.slider.valueChanged.connect(self._value_changed)
        self._value_changed(self.slider.value())

    def _value_changed(self, value: int) -> None:
        self.label.setText(self._formatter(value))
        self.valueChanged.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int | float) -> None:
        self.slider.setValue(round(value))

    def setRange(self, minimum: int, maximum: int) -> None:
        self.slider.setRange(minimum, maximum)

    def setToolTip(self, text: str) -> None:  # noqa: N802 - Qt-compatible API
        super().setToolTip(text)
        self.slider.setToolTip(text)
        self.label.setToolTip(text)
