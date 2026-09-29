from __future__ import annotations

from PySide6.QtCore import QPointF

from stem_crop_tool.core.crop import ResizeHandle
from stem_crop_tool.core.models import CropRect
from stem_crop_tool.ui.crop_item import CropItem


def test_crop_item_exposes_all_handle_centers_and_hit_testing(qtbot) -> None:
    item = CropItem(CropRect(10, 20, 30, 40))
    item.set_view_scale(2.0)

    centers = item.handle_centers()

    assert set(centers) == set(ResizeHandle)
    assert centers[ResizeHandle.TOP_LEFT] == QPointF(10, 20)
    assert centers[ResizeHandle.BOTTOM_RIGHT] == QPointF(40, 60)
    assert item.handle_at(QPointF(40, 60)) is ResizeHandle.BOTTOM_RIGHT
    assert item.contains_crop(QPointF(25, 35))
    assert not item.contains_crop(QPointF(5, 5))


def test_crop_item_keeps_handles_constant_in_view_pixels() -> None:
    item = CropItem(CropRect(1, 2, 3, 4))
    item.set_view_scale(0.5)
    size_at_half = item.handle_rects()[ResizeHandle.TOP_LEFT].width()
    item.set_view_scale(4.0)
    size_at_four = item.handle_rects()[ResizeHandle.TOP_LEFT].width()

    assert size_at_half * 0.5 == CropItem.HANDLE_PIXELS
    assert size_at_four * 4.0 == CropItem.HANDLE_PIXELS
