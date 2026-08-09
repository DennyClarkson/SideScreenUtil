from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget


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
        self.slider.setMinimumWidth(190)
        self.label = QLabel()
        self.label.setMinimumWidth(104)
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
