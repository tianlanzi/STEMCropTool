from __future__ import annotations

import numpy as np
import pytest

from stem_crop_tool.ui.image_view import ImageView


def test_actual_pixels_zoom_and_pan_preserve_source(qtbot) -> None:
    source = np.arange(400 * 500, dtype=np.float32).reshape(400, 500)
    original = source.copy()
    view = ImageView()
    view.resize(240, 180)
    qtbot.addWidget(view)
    view.show()

    view.set_image(source, source_index=3)
    view.actual_pixels()

    assert view.zoom_factor == pytest.approx(1.0)
    assert view.source_index == 3
    view.zoom_by(2.0)
    view.pan_by(30, -20)
    np.testing.assert_array_equal(source, original)
    assert view.source_index == 3

    view.reset_view()
    assert view.zoom_factor > 0


def test_replacing_stack_frame_can_preserve_view_transform(qtbot) -> None:
    view = ImageView()
    view.resize(200, 150)
    qtbot.addWidget(view)
    view.show()
    view.set_image(np.zeros((300, 400), dtype=np.uint8), source_index=0)
    view.actual_pixels()
    view.zoom_by(1.5)
    zoom = view.zoom_factor

    from stem_crop_tool.infrastructure.display import make_grayscale_qimage

    view.set_frame(
        make_grayscale_qimage(np.ones((300, 400), dtype=np.uint8)),
        source_index=1,
        reset_view=False,
    )

    assert view.source_index == 1
    assert view.zoom_factor == pytest.approx(zoom)
