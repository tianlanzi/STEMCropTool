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
    assert not controls.export_button.isEnabled()
    assert not controls.clear_button.isEnabled()

    controls.set_rect(CropRect(1, 2, 3, 4))
    assert controls.x_spin.isEnabled()
    assert controls.export_button.isEnabled()
    controls.clear_image()
    assert not controls.isEnabled()


def test_export_button_emits_only_with_a_selection(qtbot) -> None:
    controls = CropControls()
    qtbot.addWidget(controls)
    controls.set_image_size(20, 30)
    controls.set_rect(CropRect(1, 2, 3, 4))

    with qtbot.waitSignal(controls.export_requested):
        controls.export_button.click()


def test_field_labels_stay_with_their_inputs_in_a_wide_window(qtbot) -> None:
    controls = CropControls()
    controls.resize(2400, 100)
    controls.set_image_size(2048, 2048)
    qtbot.addWidget(controls)
    controls.show()
    qtbot.waitUntil(controls.isVisible)

    pairs = (
        (controls.x_label, controls.x_spin),
        (controls.y_label, controls.y_spin),
        (controls.width_label, controls.width_spin),
        (controls.height_label, controls.height_spin),
    )
    for label, spin in pairs:
        own_gap = spin.geometry().left() - label.geometry().right() - 1
        assert 0 <= own_gap <= 8
        assert label.buddy() is spin

    for (_, previous_spin), (next_label, _) in zip(pairs, pairs[1:]):
        between_groups = (
            next_label.geometry().left() - previous_spin.geometry().right() - 1
        )
        assert between_groups >= 18
