"""Synchronized controls for selecting a stack slice."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QSpinBox, QWidget


class StackControls(QWidget):
    """Expose a zero-based slice index while showing a one-based position."""

    slice_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("stack_controls")
        self._slice_count = 1
        self.label = QLabel("Slice")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.spin_box = QSpinBox()
        self.position_label = QLabel("1 / 1")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin_box)
        layout.addWidget(self.position_label)

        self.slider.valueChanged.connect(self._set_from_control)
        self.spin_box.valueChanged.connect(self._set_from_control)
        self.set_slice_count(1)

    @property
    def slice_count(self) -> int:
        return self._slice_count

    @property
    def current_index(self) -> int:
        return self.slider.value()

    def set_slice_count(self, count: int) -> None:
        count = int(count)
        if count < 1:
            raise ValueError("slice count must be positive")
        self._slice_count = count
        with QSignalBlocker(self.slider), QSignalBlocker(self.spin_box):
            self.slider.setRange(0, count - 1)
            self.spin_box.setRange(0, count - 1)
            self.slider.setValue(0)
            self.spin_box.setValue(0)
        self._update_position(0)
        self.setVisible(count > 1)

    def set_current_index(self, index: int) -> None:
        index = int(index)
        if index < 0 or index >= self._slice_count:
            raise IndexError("slice index is outside the stack")
        with QSignalBlocker(self.slider), QSignalBlocker(self.spin_box):
            self.slider.setValue(index)
            self.spin_box.setValue(index)
        self._update_position(index)

    def _set_from_control(self, index: int) -> None:
        self.set_current_index(index)
        self.slice_changed.emit(index)

    def _update_position(self, index: int) -> None:
        self.position_label.setText(f"{index + 1} / {self._slice_count}")
