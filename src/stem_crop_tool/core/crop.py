"""Pixel-exact crop rectangle creation and array extraction."""

from __future__ import annotations

from numbers import Integral
from enum import StrEnum

import numpy as np

from stem_crop_tool.core.exceptions import (
    InvalidCropRectError,
    UnsupportedArrayShapeError,
)
from stem_crop_tool.core.models import CropRect


class ResizeHandle(StrEnum):
    """Edges and corners from which an existing crop can be resized."""

    TOP_LEFT = "top_left"
    TOP = "top"
    TOP_RIGHT = "top_right"
    RIGHT = "right"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM = "bottom"
    BOTTOM_LEFT = "bottom_left"
    LEFT = "left"


def _integer(value: Integral, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{field_name} must be an integer")
    return int(value)


def _image_bounds(image_width: int, image_height: int) -> tuple[int, int]:
    width = _integer(image_width, "image_width")
    height = _integer(image_height, "image_height")
    if width < 1 or height < 1:
        raise UnsupportedArrayShapeError(
            "image width and height must both be at least 1"
        )
    return width, height


def _clamp(value: int, lower: int, upper: int) -> int:
    return min(max(value, lower), upper)


def _interval_from_drag(start: int, end: int, limit: int) -> tuple[int, int]:
    start = _clamp(start, 0, limit)
    end = _clamp(end, 0, limit)
    lower, upper = sorted((start, end))
    if lower == upper:
        if upper < limit:
            upper += 1
        else:
            lower -= 1
    return lower, upper


def _direction_with_capacity(
    start: int,
    raw_start: int,
    raw_end: int,
    limit: int,
) -> tuple[int, int]:
    direction = 1 if raw_end >= raw_start else -1
    capacity = limit - start if direction > 0 else start
    if capacity == 0:
        direction *= -1
        capacity = limit - start if direction > 0 else start
    return direction, capacity


def rect_from_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    image_width: int,
    image_height: int,
    *,
    square: bool = False,
) -> CropRect:
    """Create a bounded rectangle from integer pixel-boundary drag coordinates."""

    width, height = _image_bounds(image_width, image_height)
    raw_start_x = _integer(start_x, "start_x")
    raw_start_y = _integer(start_y, "start_y")
    raw_end_x = _integer(end_x, "end_x")
    raw_end_y = _integer(end_y, "end_y")

    if not square:
        x0, x1 = _interval_from_drag(raw_start_x, raw_end_x, width)
        y0, y1 = _interval_from_drag(raw_start_y, raw_end_y, height)
        return CropRect(x0, y0, x1 - x0, y1 - y0)

    bounded_start_x = _clamp(raw_start_x, 0, width)
    bounded_start_y = _clamp(raw_start_y, 0, height)
    direction_x, capacity_x = _direction_with_capacity(
        bounded_start_x, raw_start_x, raw_end_x, width
    )
    direction_y, capacity_y = _direction_with_capacity(
        bounded_start_y, raw_start_y, raw_end_y, height
    )
    requested_side = max(
        abs(raw_end_x - raw_start_x),
        abs(raw_end_y - raw_start_y),
        1,
    )
    side = min(requested_side, capacity_x, capacity_y)
    if side < 1:
        raise InvalidCropRectError("the square crop has no area inside the image")

    opposite_x = bounded_start_x + direction_x * side
    opposite_y = bounded_start_y + direction_y * side
    x0, x1 = sorted((bounded_start_x, opposite_x))
    y0, y1 = sorted((bounded_start_y, opposite_y))
    return CropRect(x0, y0, x1 - x0, y1 - y0)


def clamp_rect(
    rect: CropRect,
    image_width: int,
    image_height: int,
) -> CropRect:
    """Shift and, only when necessary, shrink a rectangle into image bounds."""

    width, height = _image_bounds(image_width, image_height)
    clamped_width = min(rect.width, width)
    clamped_height = min(rect.height, height)
    clamped_x = _clamp(rect.x, 0, width - clamped_width)
    clamped_y = _clamp(rect.y, 0, height - clamped_height)
    return CropRect(clamped_x, clamped_y, clamped_width, clamped_height)


def translate_rect(
    rect: CropRect,
    delta_x: int,
    delta_y: int,
    image_width: int,
    image_height: int,
) -> CropRect:
    """Translate a rectangle while preserving its size inside the image."""

    delta_x = _integer(delta_x, "delta_x")
    delta_y = _integer(delta_y, "delta_y")
    moved = CropRect(rect.x + delta_x, rect.y + delta_y, rect.width, rect.height)
    return clamp_rect(moved, image_width, image_height)


def resize_rect(
    rect: CropRect,
    new_width: int,
    new_height: int,
    image_width: int,
    image_height: int,
    *,
    square: bool = False,
) -> CropRect:
    """Resize from the top-left anchor and clamp the result inside the image."""

    width, height = _image_bounds(image_width, image_height)
    anchored = clamp_rect(rect, width, height)
    requested_width = max(_integer(new_width, "new_width"), 1)
    requested_height = max(_integer(new_height, "new_height"), 1)
    maximum_width = width - anchored.x
    maximum_height = height - anchored.y

    if square:
        side = min(
            max(requested_width, requested_height),
            maximum_width,
            maximum_height,
        )
        return CropRect(anchored.x, anchored.y, side, side)

    return CropRect(
        anchored.x,
        anchored.y,
        min(requested_width, maximum_width),
        min(requested_height, maximum_height),
    )


def rect_from_fields(
    x: int,
    y: int,
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> CropRect:
    """Build a bounded crop from numeric fields, preserving x/y when possible.

    Coordinates are clamped first. Width and height are then limited to the
    remaining image extent, so typing a new position never silently moves that
    position backward merely to preserve an old size.
    """

    bound_width, bound_height = _image_bounds(image_width, image_height)
    bounded_x = _clamp(_integer(x, "x"), 0, bound_width - 1)
    bounded_y = _clamp(_integer(y, "y"), 0, bound_height - 1)
    bounded_width = _clamp(
        _integer(width, "width"),
        1,
        bound_width - bounded_x,
    )
    bounded_height = _clamp(
        _integer(height, "height"),
        1,
        bound_height - bounded_y,
    )
    return CropRect(bounded_x, bounded_y, bounded_width, bounded_height)


def resize_rect_from_handle(
    rect: CropRect,
    handle: ResizeHandle | str,
    boundary_x: int,
    boundary_y: int,
    image_width: int,
    image_height: int,
    *,
    square: bool = False,
) -> CropRect:
    """Resize one crop edge/corner to an integer pixel boundary.

    Corner resizing fixes the opposite corner. For Shift-constrained edge
    resizing, the opposite edge and the top/left perpendicular edge are fixed.
    This makes square behavior deterministic even for single-axis handles.
    """

    bound_width, bound_height = _image_bounds(image_width, image_height)
    current = validate_rect_within(rect, bound_width, bound_height)
    selected = ResizeHandle(handle)
    x = _clamp(_integer(boundary_x, "boundary_x"), 0, bound_width)
    y = _clamp(_integer(boundary_y, "boundary_y"), 0, bound_height)

    corner_anchors = {
        ResizeHandle.TOP_LEFT: (current.x1, current.y1),
        ResizeHandle.TOP_RIGHT: (current.x, current.y1),
        ResizeHandle.BOTTOM_RIGHT: (current.x, current.y),
        ResizeHandle.BOTTOM_LEFT: (current.x1, current.y),
    }
    anchor = corner_anchors.get(selected)
    if anchor is not None:
        return rect_from_drag(
            anchor[0],
            anchor[1],
            x,
            y,
            bound_width,
            bound_height,
            square=square,
        )

    if square:
        if selected is ResizeHandle.LEFT:
            side = max(abs(current.x1 - x), 1)
            return rect_from_drag(
                current.x1,
                current.y,
                x,
                current.y + side,
                bound_width,
                bound_height,
                square=True,
            )
        if selected is ResizeHandle.RIGHT:
            side = max(abs(x - current.x), 1)
            return rect_from_drag(
                current.x,
                current.y,
                x,
                current.y + side,
                bound_width,
                bound_height,
                square=True,
            )
        if selected is ResizeHandle.TOP:
            side = max(abs(current.y1 - y), 1)
            return rect_from_drag(
                current.x,
                current.y1,
                current.x + side,
                y,
                bound_width,
                bound_height,
                square=True,
            )
        side = max(abs(y - current.y), 1)
        return rect_from_drag(
            current.x,
            current.y,
            current.x + side,
            y,
            bound_width,
            bound_height,
            square=True,
        )

    if selected is ResizeHandle.LEFT:
        new_x = min(x, current.x1 - 1)
        return CropRect(new_x, current.y, current.x1 - new_x, current.height)
    if selected is ResizeHandle.RIGHT:
        new_x1 = max(x, current.x + 1)
        return CropRect(current.x, current.y, new_x1 - current.x, current.height)
    if selected is ResizeHandle.TOP:
        new_y = min(y, current.y1 - 1)
        return CropRect(current.x, new_y, current.width, current.y1 - new_y)

    new_y1 = max(y, current.y + 1)
    return CropRect(current.x, current.y, current.width, new_y1 - current.y)


def validate_rect_within(
    rect: CropRect,
    image_width: int,
    image_height: int,
) -> CropRect:
    """Return the rectangle or raise when it is not fully inside the image."""

    width, height = _image_bounds(image_width, image_height)
    if rect.x < 0 or rect.y < 0 or rect.x1 > width or rect.y1 > height:
        raise InvalidCropRectError(
            f"crop {rect} is outside image bounds (width={width}, height={height})"
        )
    return rect


def crop_array(image: np.ndarray, rect: CropRect) -> np.ndarray:
    """Return the exact 2D NumPy view selected by ``rect``."""

    array = np.asarray(image)
    if array.ndim != 2:
        raise UnsupportedArrayShapeError(
            f"crop_array requires a 2D image, received {array.ndim}D"
        )
    validate_rect_within(rect, array.shape[1], array.shape[0])
    return array[rect.slices]
