from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QDialogButtonBox

from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ImageMetadata,
    NormalizationMode,
)
from stem_crop_tool.ui.export_dialog import ExportDialog


def _dialog(qtbot, *, dtype=np.uint16, shape=(8, 20, 30)) -> ExportDialog:
    metadata = ImageMetadata("stack.npy", "npy", shape, np.dtype(dtype))
    dialog = ExportDialog(metadata, CropRect(2, 3, 10, 8), 3)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_dialog_builds_current_range_and_all_slice_requests(qtbot, tmp_path) -> None:
    dialog = _dialog(qtbot)
    dialog.destination_edit.setText(str(tmp_path / "current.npy"))
    current = dialog.build_request()
    assert current.slice_indices == (3,)
    assert current.destination == tmp_path / "current.npy"

    dialog.range_radio.setChecked(True)
    dialog.range_start_spin.setValue(2)
    dialog.range_stop_spin.setValue(5)
    dialog.destination_edit.setText(str(tmp_path / "range"))
    selected_range = dialog.build_request()
    assert selected_range.slice_indices == (2, 3, 4, 5)
    assert dialog.is_batch

    dialog.all_radio.setChecked(True)
    dialog.destination_edit.setText(str(tmp_path / "all"))
    all_slices = dialog.build_request()
    assert all_slices.slice_indices == tuple(range(8))


def test_dialog_rejects_raw_float_png_and_explains_normalization(qtbot, tmp_path) -> None:
    dialog = _dialog(qtbot, dtype=np.float32)
    png_index = dialog.format_combo.findData(ExportFormat.PNG.value)
    dialog.format_combo.setCurrentIndex(png_index)
    dialog.destination_edit.setText(str(tmp_path / "crop.png"))
    ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)

    assert not ok_button.isEnabled()
    assert "enable normalization or export NPY" in dialog.dtype_label.text()

    dialog.normalize_checkbox.setChecked(True)
    request = dialog.build_request()
    assert ok_button.isEnabled()
    assert request.output_format is ExportFormat.PNG
    assert request.normalization is NormalizationMode.LOCAL_MINMAX
    assert "not quantitatively comparable" in dialog.normalization_warning.text()


def test_2d_dialog_uses_single_file_and_validates_suffix(qtbot, tmp_path) -> None:
    dialog = _dialog(qtbot, shape=(20, 30))
    assert dialog.selected_indices() == (0,)
    assert not dialog.scope_group.isVisible()

    dialog.destination_edit.setText(str(tmp_path / "crop.png"))
    ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok_button.isEnabled()
    assert "must end with '.npy'" in dialog.destination_error_label.text()
    try:
        dialog.build_request()
    except ValueError as exc:
        assert "must end with '.npy'" in str(exc)
    else:
        raise AssertionError("wrong single-file suffix was accepted")

    dialog.destination_edit.setText(str(tmp_path / "crop.npy"))
    request = dialog.build_request()
    assert request.destination == Path(tmp_path / "crop.npy")
    assert request.slice_indices == (0,)
