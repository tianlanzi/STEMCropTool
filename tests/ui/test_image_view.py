from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF, Qt

from stem_crop_tool.core.models import CropRect
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


@pytest.mark.parametrize("zoom", [1.0, 2.0, 4.0])
def test_mouse_created_crop_is_exact_at_multiple_zoom_levels(qtbot, zoom) -> None:
    view = ImageView()
    view.resize(320, 260)
    qtbot.addWidget(view)
    view.show()
    view.set_image(np.zeros((100, 120), dtype=np.uint8))
    view.set_crop_enabled(True)
    view.actual_pixels()
    view.zoom_by(zoom)

    start = view.mapFromScene(QPointF(10, 12))
    end = view.mapFromScene(QPointF(37, 41))
    expected_start = view.viewport_to_pixel_boundary(start)
    expected_end = view.viewport_to_pixel_boundary(end)

    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)

    x0, x1 = sorted((expected_start[0], expected_end[0]))
    y0, y1 = sorted((expected_start[1], expected_end[1]))
    assert view.crop_rect == CropRect(x0, y0, x1 - x0, y1 - y0)


def test_reverse_drag_move_resize_and_delete_are_pixel_exact(qtbot) -> None:
    view = ImageView()
    view.resize(360, 300)
    qtbot.addWidget(view)
    view.show()
    view.set_image(np.zeros((160, 180), dtype=np.uint8))
    view.set_crop_enabled(True)
    view.actual_pixels()
    view.zoom_by(2.0)

    start = view.mapFromScene(QPointF(80, 90))
    end = view.mapFromScene(QPointF(30, 40))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert view.crop_rect == CropRect(30, 40, 50, 50)

    move_start = view.mapFromScene(QPointF(55, 65))
    move_end = view.mapFromScene(QPointF(5, 5))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=move_start)
    qtbot.mouseMove(view.viewport(), move_end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=move_end)
    assert view.crop_rect == CropRect(0, 0, 50, 50)

    resize_start = view.mapFromScene(QPointF(50, 50))
    resize_end = view.mapFromScene(QPointF(75, 60))
    qtbot.mousePress(view.viewport(), Qt.MouseButton.LeftButton, pos=resize_start)
    qtbot.mouseMove(view.viewport(), resize_end)
    qtbot.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=resize_end)
    assert view.crop_rect == CropRect(0, 0, 75, 60)

    qtbot.keyClick(view, Qt.Key.Key_Delete)
    assert view.crop_rect is None


def test_shift_creation_and_resize_are_bounded_squares(qtbot) -> None:
    view = ImageView()
    view.resize(300, 260)
    qtbot.addWidget(view)
    view.show()
    view.set_image(np.zeros((100, 100), dtype=np.uint8))
    view.set_crop_enabled(True)
    view.actual_pixels()
    view.zoom_by(2.0)

    start = view.mapFromScene(QPointF(85, 80))
    end = view.mapFromScene(QPointF(130, 95))
    qtbot.mousePress(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        start,
    )
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        end,
    )
    assert view.crop_rect == CropRect(85, 80, 15, 15)

    resize_start = view.mapFromScene(QPointF(85, 80))
    resize_end = view.mapFromScene(QPointF(60, 75))
    qtbot.mousePress(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        resize_start,
    )
    qtbot.mouseMove(view.viewport(), resize_end)
    qtbot.mouseRelease(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        resize_end,
    )
    assert view.crop_rect is not None
    assert view.crop_rect.width == view.crop_rect.height
    assert view.crop_rect.x >= 0 and view.crop_rect.y >= 0
