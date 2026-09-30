"""Numeric crop editor synchronized with the graphics view."""

from __future__ import annotations

from contextlib import ExitStack

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from stem_crop_tool.core.crop import rect_from_fields
from stem_crop_tool.core.models import CropRect


class CropControls(QGroupBox):
    """Edit a crop as exact zero-based source-pixel coordinates."""

    rect_edited = Signal(object)
    new_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Crop (source pixels)", parent)
        self._image_size: tuple[int, int] | None = None
        self._rect: CropRect | None = None

        self.x_spin = self._spin_box("crop_x")
        self.y_spin = self._spin_box("crop_y")
        self.width_spin = self._spin_box("crop_width")
        self.height_spin = self._spin_box("crop_height")
        self.x_label = QLabel("X")
        self.y_label = QLabel("Y")
        self.width_label = QLabel("Width")
        self.height_label = QLabel("Height")
        self.new_button = QPushButton("New Crop")
        self.clear_button = QPushButton("Clear")
        self.summary_label = QLabel("No selection")

        field_row = QHBoxLayout()
        field_row.setSpacing(6)
        for index, (label, spin) in enumerate(
            (
                (self.x_label, self.x_spin),
                (self.y_label, self.y_spin),
                (self.width_label, self.width_spin),
                (self.height_label, self.height_spin),
            )
        ):
            if index:
                field_row.addSpacing(12)
            label.setBuddy(spin)
            field_row.addWidget(label)
            field_row.addWidget(spin, 1)
        field_row.addSpacing(12)
        field_row.addWidget(self.new_button)
        field_row.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.addLayout(field_row)
        layout.addWidget(self.summary_label)

        for spin in self._spins:
            spin.valueChanged.connect(self._fields_changed)
        self.new_button.clicked.connect(self.new_requested)
        self.clear_button.clicked.connect(self.clear_requested)
        self.clear_image()

    @staticmethod
    def _spin_box(name: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setObjectName(name)
        spin.setKeyboardTracking(False)
        return spin

    @property
    def _spins(self) -> tuple[QSpinBox, QSpinBox, QSpinBox, QSpinBox]:
        return self.x_spin, self.y_spin, self.width_spin, self.height_spin

    @property
    def crop_rect(self) -> CropRect | None:
        return self._rect

    def set_image_size(self, width: int, height: int) -> None:
        width = int(width)
        height = int(height)
        if width < 1 or height < 1:
            raise ValueError("image dimensions must be positive")
        self._image_size = (width, height)
        self.setEnabled(True)
        self.new_button.setEnabled(True)
        self.set_rect(None)

    def clear_image(self) -> None:
        self._image_size = None
        self._rect = None
        self.setEnabled(False)
        self._set_fields_enabled(False)
        self.summary_label.setText("No image open")

    def set_rect(self, rect: CropRect | None) -> None:
        self._rect = rect
        if self._image_size is None:
            self.clear_image()
            return
        if rect is None:
            self._set_fields_enabled(False)
            self.clear_button.setEnabled(False)
            self.summary_label.setText("No selection — drag on the image to create one")
            return

        image_width, image_height = self._image_size
        with ExitStack() as stack:
            for spin in self._spins:
                stack.enter_context(QSignalBlocker(spin))
            self.x_spin.setRange(0, image_width - 1)
            self.y_spin.setRange(0, image_height - 1)
            self.width_spin.setRange(1, image_width - rect.x)
            self.height_spin.setRange(1, image_height - rect.y)
            self.x_spin.setValue(rect.x)
            self.y_spin.setValue(rect.y)
            self.width_spin.setValue(rect.width)
            self.height_spin.setValue(rect.height)
        self._set_fields_enabled(True)
        self.clear_button.setEnabled(True)
        self.summary_label.setText(
            f"x={rect.x}, y={rect.y}, width={rect.width}, height={rect.height}"
        )

    def _set_fields_enabled(self, enabled: bool) -> None:
        for spin in self._spins:
            spin.setEnabled(enabled)

    def _fields_changed(self) -> None:
        if self._image_size is None or self._rect is None:
            return
        image_width, image_height = self._image_size
        rect = rect_from_fields(
            self.x_spin.value(),
            self.y_spin.value(),
            self.width_spin.value(),
            self.height_spin.value(),
            image_width,
            image_height,
        )
        self.rect_edited.emit(rect)
