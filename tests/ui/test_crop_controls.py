from __future__ import annotations

from stem_crop_tool.core.models import CropRect
from stem_crop_tool.ui.crop_controls import CropControls


def test_numeric_fields_emit_one_bounded_rect_without_feedback(qtbot) -> None:
    controls = CropControls()
    qtbot.addWidget(controls)
    controls.set_image_size(10, 10)
    controls.set_rect(CropRect(2, 3, 6, 5))

    with qtbot.waitSignal(controls.rect_edited) as emitted:
        controls.x_spin.setValue(8)

    assert emitted.args == [CropRect(8, 3, 2, 5)]
    controls.set_rect(emitted.args[0])
    assert controls.crop_rect == CropRect(8, 3, 2, 5)
    assert controls.width_spin.maximum() == 2
    assert "x=8" in controls.summary_label.text()


def test_numeric_fields_disable_without_selection_or_image(qtbot) -> None:
    controls = CropControls()
    qtbot.addWidget(controls)
    assert not controls.isEnabled()

    controls.set_image_size(20, 30)
    assert controls.isEnabled()
    assert not controls.x_spin.isEnabled()
    assert not controls.clear_button.isEnabled()

    controls.set_rect(CropRect(1, 2, 3, 4))
    assert controls.x_spin.isEnabled()
    controls.clear_image()
    assert not controls.isEnabled()
