from __future__ import annotations

import numpy as np

from stem_crop_tool.core.crop import crop_array
from stem_crop_tool.core.metadata import output_record, single_sidecar
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ImageMetadata,
    NormalizationMode,
)
from stem_crop_tool.ui.crop_controls import CropControls
from stem_crop_tool.ui.image_view import ImageView


def test_ui_numeric_graphics_array_and_json_share_one_crop_rect(qtbot) -> None:
    source = np.arange(12 * 14, dtype=np.uint16).reshape(12, 14)
    rect = CropRect(3, 4, 6, 5)
    view = ImageView()
    controls = CropControls()
    qtbot.addWidget(view)
    qtbot.addWidget(controls)
    view.set_image(source)
    view.set_crop_enabled(True)
    controls.set_image_size(14, 12)
    view.crop_changed.connect(controls.set_rect)
    controls.rect_edited.connect(view.set_crop_rect)

    view.set_crop_rect(rect)
    cropped = crop_array(source, view.crop_rect)
    metadata = ImageMetadata("source.npy", "npy", source.shape, source.dtype)
    output = output_record(
        "crop.npy",
        ExportFormat.NPY,
        cropped.shape,
        cropped.dtype,
        slice_index=None,
    )
    sidecar = single_sidecar(
        metadata,
        view.crop_rect,
        NormalizationMode.NONE,
        output,
    )

    assert controls.crop_rect is view.crop_rect
    assert controls.x_spin.value() == rect.x
    assert controls.y_spin.value() == rect.y
    assert controls.width_spin.value() == rect.width
    assert controls.height_spin.value() == rect.height
    np.testing.assert_array_equal(cropped, source[4:9, 3:9])
    assert sidecar["crop"] == {"x": 3, "y": 4, "width": 6, "height": 5}
