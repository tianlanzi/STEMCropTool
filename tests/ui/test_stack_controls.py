from __future__ import annotations

from stem_crop_tool.ui.stack_controls import StackControls


def test_stack_controls_are_hidden_for_2d_and_synchronized_for_stack(qtbot) -> None:
    controls = StackControls()
    qtbot.addWidget(controls)
    controls.show()
    controls.set_slice_count(1)
    assert not controls.isVisible()

    controls.set_slice_count(8)
    controls.show()
    assert controls.isVisible()
    assert controls.slider.maximum() == 7
    assert controls.spin_box.maximum() == 7

    with qtbot.waitSignal(controls.slice_changed) as emitted:
        controls.slider.setValue(5)

    assert emitted.args == [5]
    assert controls.spin_box.value() == 5
    assert controls.position_label.text() == "6 / 8"
