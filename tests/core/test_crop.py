import numpy as np
import pytest

from stem_crop_tool.core.crop import (
    ResizeHandle,
    clamp_rect,
    crop_array,
    rect_from_drag,
    rect_from_fields,
    resize_rect,
    resize_rect_from_handle,
    translate_rect,
    validate_rect_within,
)
from stem_crop_tool.core.exceptions import (
    InvalidCropRectError,
    UnsupportedArrayShapeError,
)
from stem_crop_tool.core.models import CropRect


@pytest.mark.parametrize(
    "start,end",
    [
        ((2, 3), (7, 9)),
        ((7, 3), (2, 9)),
        ((2, 9), (7, 3)),
        ((7, 9), (2, 3)),
    ],
)
def test_rect_from_drag_normalizes_every_direction(
    start: tuple[int, int], end: tuple[int, int]
) -> None:
    rect = rect_from_drag(*start, *end, image_width=20, image_height=20)

    assert rect == CropRect(2, 3, 5, 6)


def test_rect_from_drag_clamps_to_all_edges() -> None:
    rect = rect_from_drag(-5, -6, 40, 50, image_width=10, image_height=12)

    assert rect == CropRect(0, 0, 10, 12)


@pytest.mark.parametrize(
    "point,expected",
    [
        ((0, 0), CropRect(0, 0, 1, 1)),
        ((10, 12), CropRect(9, 11, 1, 1)),
        ((4, 5), CropRect(4, 5, 1, 1)),
    ],
)
def test_zero_length_drag_creates_minimum_pixel(
    point: tuple[int, int], expected: CropRect
) -> None:
    assert rect_from_drag(*point, *point, 10, 12) == expected


def test_square_drag_uses_dominant_delta() -> None:
    rect = rect_from_drag(2, 3, 8, 7, 20, 20, square=True)

    assert rect == CropRect(2, 3, 6, 6)


def test_square_drag_shrinks_at_image_edge() -> None:
    rect = rect_from_drag(8, 8, 15, 10, 10, 10, square=True)
    reverse = rect_from_drag(2, 2, -5, 0, 10, 10, square=True)

    assert rect == CropRect(8, 8, 2, 2)
    assert reverse == CropRect(0, 0, 2, 2)


@pytest.mark.parametrize("square", [False, True])
def test_drag_rect_invariants_across_many_out_of_bounds_points(square: bool) -> None:
    rng = np.random.default_rng(20260929)

    for _ in range(500):
        start_x, end_x = rng.integers(-30, 51, size=2)
        start_y, end_y = rng.integers(-20, 41, size=2)
        rect = rect_from_drag(
            int(start_x),
            int(start_y),
            int(end_x),
            int(end_y),
            image_width=20,
            image_height=15,
            square=square,
        )

        assert rect.width >= 1
        assert rect.height >= 1
        assert 0 <= rect.x < rect.x1 <= 20
        assert 0 <= rect.y < rect.y1 <= 15
        if square:
            assert rect.width == rect.height


@pytest.mark.parametrize(
    "rect,expected",
    [
        (CropRect(-4, 2, 3, 4), CropRect(0, 2, 3, 4)),
        (CropRect(9, 2, 4, 4), CropRect(6, 2, 4, 4)),
        (CropRect(2, -4, 4, 3), CropRect(2, 0, 4, 3)),
        (CropRect(2, 9, 4, 4), CropRect(2, 6, 4, 4)),
        (CropRect(-2, -2, 20, 30), CropRect(0, 0, 10, 10)),
    ],
)
def test_clamp_rect_handles_all_edges(rect: CropRect, expected: CropRect) -> None:
    assert clamp_rect(rect, 10, 10) == expected


def test_translate_rect_preserves_size_and_stays_in_bounds() -> None:
    rect = CropRect(2, 3, 4, 5)

    assert translate_rect(rect, 20, -20, 10, 10) == CropRect(6, 0, 4, 5)


@pytest.mark.parametrize(
    "delta,expected",
    [
        ((-100, 0), CropRect(0, 3, 4, 5)),
        ((100, 0), CropRect(6, 3, 4, 5)),
        ((0, -100), CropRect(2, 0, 4, 5)),
        ((0, 100), CropRect(2, 5, 4, 5)),
    ],
)
def test_translate_rect_clamps_at_every_edge(
    delta: tuple[int, int], expected: CropRect
) -> None:
    assert translate_rect(CropRect(2, 3, 4, 5), *delta, 10, 10) == expected


def test_resize_rect_enforces_minimum_and_bounds() -> None:
    rect = CropRect(7, 8, 2, 2)

    assert resize_rect(rect, 0, -4, 10, 10) == CropRect(7, 8, 1, 1)
    assert resize_rect(rect, 8, 8, 10, 10) == CropRect(7, 8, 3, 2)
    assert resize_rect(rect, 8, 1, 10, 10, square=True) == CropRect(7, 8, 2, 2)


def test_numeric_fields_preserve_position_and_shrink_size_at_edges() -> None:
    assert rect_from_fields(8, 7, 9, 9, 10, 10) == CropRect(8, 7, 2, 3)
    assert rect_from_fields(-5, 20, 0, -2, 10, 10) == CropRect(0, 9, 1, 1)


@pytest.mark.parametrize(
    "handle,boundary,expected",
    [
        (ResizeHandle.LEFT, (-20, 5), CropRect(0, 3, 8, 4)),
        (ResizeHandle.RIGHT, (20, 5), CropRect(4, 3, 6, 4)),
        (ResizeHandle.TOP, (5, -20), CropRect(4, 0, 4, 7)),
        (ResizeHandle.BOTTOM, (5, 20), CropRect(4, 3, 4, 7)),
        (ResizeHandle.TOP_LEFT, (1, 1), CropRect(1, 1, 7, 6)),
        (ResizeHandle.TOP_RIGHT, (9, 1), CropRect(4, 1, 5, 6)),
        (ResizeHandle.BOTTOM_RIGHT, (9, 9), CropRect(4, 3, 5, 6)),
        (ResizeHandle.BOTTOM_LEFT, (1, 9), CropRect(1, 3, 7, 6)),
    ],
)
def test_resize_from_every_handle_stays_bounded(
    handle: ResizeHandle,
    boundary: tuple[int, int],
    expected: CropRect,
) -> None:
    rect = CropRect(4, 3, 4, 4)
    assert resize_rect_from_handle(rect, handle, *boundary, 10, 10) == expected


def test_shift_resize_from_corner_and_edge_produces_bounded_square() -> None:
    rect = CropRect(6, 5, 3, 3)

    corner = resize_rect_from_handle(
        rect,
        ResizeHandle.TOP_LEFT,
        -5,
        2,
        10,
        10,
        square=True,
    )
    edge = resize_rect_from_handle(
        rect,
        ResizeHandle.RIGHT,
        20,
        5,
        10,
        10,
        square=True,
    )

    assert corner == CropRect(1, 0, 8, 8)
    assert edge == CropRect(6, 5, 4, 4)


def test_validate_rect_within_rejects_out_of_bounds() -> None:
    with pytest.raises(InvalidCropRectError):
        validate_rect_within(CropRect(8, 8, 3, 3), 10, 10)


def test_crop_array_matches_half_open_numpy_slice() -> None:
    image = np.arange(8 * 9, dtype=np.uint16).reshape(8, 9)
    rect = CropRect(2, 3, 4, 2)

    cropped = crop_array(image, rect)

    np.testing.assert_array_equal(cropped, image[3:5, 2:6])
    assert cropped.shape == (rect.height, rect.width)
    assert np.shares_memory(cropped, image)


def test_crop_array_rejects_non_2d_input() -> None:
    with pytest.raises(UnsupportedArrayShapeError):
        crop_array(np.zeros((2, 3, 4)), CropRect(0, 0, 1, 1))
