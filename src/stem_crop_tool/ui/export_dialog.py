"""Export request dialog for single images and image stacks."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stem_crop_tool.core.batch import (
    all_slice_indices,
    current_slice_indices,
    inclusive_slice_range,
)
from stem_crop_tool.core.dtypes import output_dtype_for
from stem_crop_tool.core.exceptions import STEMCropError
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    ImageMetadata,
    NormalizationMode,
)


class SliceScope(StrEnum):
    CURRENT = "current"
    RANGE = "range"
    ALL = "all"


class ExportDialog(QDialog):
    """Collect and validate an immutable export request."""

    def __init__(
        self,
        metadata: ImageMetadata,
        crop: CropRect,
        current_slice_index: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Crop")
        self.setModal(True)
        self.metadata = metadata
        self.crop = crop
        self.current_slice_index = int(current_slice_index)
        self._request: ExportRequest | None = None

        self.format_combo = QComboBox()
        self.format_combo.addItem("NumPy array (.npy)", ExportFormat.NPY.value)
        self.format_combo.addItem("PNG image (.png)", ExportFormat.PNG.value)
        self.normalize_checkbox = QCheckBox("Normalize each exported crop to 0–1")
        self.overwrite_checkbox = QCheckBox("Overwrite existing output files")
        self.dtype_label = QLabel()
        self.dtype_label.setWordWrap(True)
        self.normalization_warning = QLabel(
            "Each stack slice is normalized independently. Independently "
            "normalized slices are not quantitatively comparable; disable "
            "normalization to preserve original values."
        )
        self.normalization_warning.setWordWrap(True)
        self.normalization_warning.setStyleSheet("color: #9a6700;")

        format_form = QFormLayout()
        format_form.addRow("Format", self.format_combo)
        format_form.addRow("Source dtype", QLabel(str(metadata.dtype)))
        format_form.addRow("Output", self.dtype_label)
        format_form.addRow("", self.normalize_checkbox)
        format_form.addRow("", self.normalization_warning)
        format_form.addRow("", self.overwrite_checkbox)

        self.scope_group = QGroupBox("Stack slices (zero-based, inclusive range)")
        scope_layout = QVBoxLayout(self.scope_group)
        self.current_radio = QRadioButton(
            f"Current slice ({self.current_slice_index})"
        )
        self.range_radio = QRadioButton("Range")
        self.all_radio = QRadioButton(f"All slices (0–{metadata.slice_count - 1})")
        self.scope_buttons = QButtonGroup(self)
        self.scope_buttons.addButton(self.current_radio)
        self.scope_buttons.addButton(self.range_radio)
        self.scope_buttons.addButton(self.all_radio)
        self.current_radio.setChecked(True)

        range_row = QWidget()
        range_layout = QHBoxLayout(range_row)
        range_layout.setContentsMargins(24, 0, 0, 0)
        self.range_start_spin = QSpinBox()
        self.range_stop_spin = QSpinBox()
        for spin in (self.range_start_spin, self.range_stop_spin):
            spin.setRange(0, metadata.slice_count - 1)
        self.range_start_spin.setValue(self.current_slice_index)
        self.range_stop_spin.setValue(self.current_slice_index)
        range_layout.addWidget(QLabel("Start"))
        range_layout.addWidget(self.range_start_spin)
        range_layout.addWidget(QLabel("Stop"))
        range_layout.addWidget(self.range_stop_spin)
        range_layout.addStretch(1)
        scope_layout.addWidget(self.current_radio)
        scope_layout.addWidget(self.range_radio)
        scope_layout.addWidget(range_row)
        scope_layout.addWidget(self.all_radio)
        self.scope_group.setVisible(metadata.slice_count > 1)

        destination_row = QWidget()
        destination_layout = QHBoxLayout(destination_row)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Choose an output location")
        self.browse_button = QPushButton("Browse...")
        destination_layout.addWidget(self.destination_edit, 1)
        destination_layout.addWidget(self.browse_button)
        self.destination_label = QLabel("Output file")
        self.destination_error_label = QLabel()
        self.destination_error_label.setStyleSheet("color: #b42318;")

        self.selection_summary = QLabel()
        self.selection_summary.setWordWrap(True)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        layout = QVBoxLayout(self)
        layout.addLayout(format_form)
        layout.addWidget(self.scope_group)
        destination_form = QFormLayout()
        destination_form.addRow(self.destination_label, destination_row)
        destination_form.addRow("", self.destination_error_label)
        layout.addLayout(destination_form)
        layout.addWidget(self.selection_summary)
        layout.addWidget(self.button_box)

        self.format_combo.currentIndexChanged.connect(self._update_state)
        self.normalize_checkbox.toggled.connect(self._update_state)
        self.destination_edit.textChanged.connect(self._update_state)
        self.current_radio.toggled.connect(self._update_state)
        self.range_radio.toggled.connect(self._update_state)
        self.all_radio.toggled.connect(self._update_state)
        self.range_start_spin.valueChanged.connect(self._range_start_changed)
        self.range_stop_spin.valueChanged.connect(self._range_stop_changed)
        self.browse_button.clicked.connect(self._browse)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self._update_state()

    @property
    def output_format(self) -> ExportFormat:
        return ExportFormat(self.format_combo.currentData())

    @property
    def normalization(self) -> NormalizationMode:
        if self.normalize_checkbox.isChecked():
            return NormalizationMode.LOCAL_MINMAX
        return NormalizationMode.NONE

    @property
    def slice_scope(self) -> SliceScope:
        if self.metadata.slice_count == 1 or self.current_radio.isChecked():
            return SliceScope.CURRENT
        if self.range_radio.isChecked():
            return SliceScope.RANGE
        return SliceScope.ALL

    @property
    def request(self) -> ExportRequest | None:
        return self._request

    def selected_indices(self) -> tuple[int, ...]:
        count = self.metadata.slice_count
        if count == 1:
            return (0,)
        if self.slice_scope is SliceScope.CURRENT:
            return current_slice_indices(self.current_slice_index, count)
        if self.slice_scope is SliceScope.RANGE:
            return inclusive_slice_range(
                self.range_start_spin.value(),
                self.range_stop_spin.value(),
                count,
            )
        return all_slice_indices(count)

    @property
    def is_batch(self) -> bool:
        return len(self.selected_indices()) > 1

    def build_request(self) -> ExportRequest:
        raw_destination = self.destination_edit.text().strip()
        if not raw_destination:
            raise ValueError("choose an output location")
        destination = Path(raw_destination)
        indices = self.selected_indices()
        if len(indices) == 1:
            expected_suffix = f".{self.output_format.value}"
            if destination.suffix.lower() != expected_suffix:
                raise ValueError(
                    f"single export filename must end with '{expected_suffix}'"
                )
        output_dtype_for(self.metadata.dtype, self.output_format, self.normalization)
        return ExportRequest(
            destination=destination,
            crop=self.crop,
            output_format=self.output_format,
            normalization=self.normalization,
            slice_indices=indices,
            overwrite=self.overwrite_checkbox.isChecked(),
        )

    def accept(self) -> None:
        try:
            self._request = self.build_request()
        except (STEMCropError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "Export Crop", str(exc))
            return
        super().accept()

    def _range_start_changed(self, value: int) -> None:
        if value > self.range_stop_spin.value():
            self.range_stop_spin.setValue(value)
        self._update_state()

    def _range_stop_changed(self, value: int) -> None:
        if value < self.range_start_spin.value():
            self.range_start_spin.setValue(value)
        self._update_state()

    def _browse(self) -> None:
        if self.is_batch:
            selected = QFileDialog.getExistingDirectory(
                self,
                "Select Export Directory",
                self.destination_edit.text(),
            )
        else:
            suffix = self.output_format.value
            filter_text = (
                "NumPy array (*.npy)" if suffix == "npy" else "PNG image (*.png)"
            )
            suggested = self.destination_edit.text() or str(
                Path.cwd() / f"{Path(self.metadata.source_name).stem}_crop.{suffix}"
            )
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Select Export File",
                suggested,
                filter_text,
            )
        if selected:
            self.destination_edit.setText(selected)

    def _update_state(self) -> None:
        self.range_start_spin.setEnabled(self.range_radio.isChecked())
        self.range_stop_spin.setEnabled(self.range_radio.isChecked())
        self.normalization_warning.setVisible(self.normalize_checkbox.isChecked())
        indices = self.selected_indices()
        self.destination_label.setText(
            "Output directory" if len(indices) > 1 else "Output file"
        )
        self.selection_summary.setText(
            f"Crop: x={self.crop.x}, y={self.crop.y}, "
            f"{self.crop.width} × {self.crop.height}; "
            f"{len(indices)} slice{'s' if len(indices) != 1 else ''}."
        )

        destination_text = self.destination_edit.text().strip()
        valid = bool(destination_text)
        destination_error = ""
        if not destination_text:
            destination_error = "Choose an output location."
        elif len(indices) == 1:
            expected_suffix = f".{self.output_format.value}"
            if Path(destination_text).suffix.lower() != expected_suffix:
                destination_error = (
                    f"Single export filename must end with '{expected_suffix}'."
                )
                valid = False
        self.destination_error_label.setText(destination_error)
        try:
            dtype = output_dtype_for(
                self.metadata.dtype,
                self.output_format,
                self.normalization,
            )
        except STEMCropError as exc:
            self.dtype_label.setText(str(exc))
            self.dtype_label.setStyleSheet("color: #b42318;")
            valid = False
        else:
            detail = "normalized" if self.normalize_checkbox.isChecked() else "raw"
            self.dtype_label.setText(f"{dtype} ({detail})")
            self.dtype_label.setStyleSheet("")
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(valid)
