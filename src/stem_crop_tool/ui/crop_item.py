"""Visual representation and hit testing for one integer crop rectangle."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from stem_crop_tool.core.crop import ResizeHandle
from stem_crop_tool.core.models import CropRect


class CropItem(QGraphicsObject):
    """Paint one crop and its eight resize handles in source coordinates."""

    HANDLE_PIXELS = 9.0
    CENTER_CROSS_ARM_PIXELS = 7.0

    def __init__(self, rect: CropRect) -> None:
        super().__init__()
        self._rect = rect
        self._handle_size = self.HANDLE_PIXELS
        self._center_cross_arm = self.CENTER_CROSS_ARM_PIXELS
        self.setZValue(10.0)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    @property
    def crop_rect(self) -> CropRect:
        return self._rect

    def set_crop_rect(self, rect: CropRect) -> None:
        if rect == self._rect:
            return
        self.prepareGeometryChange()
        self._rect = rect
        self.update()

    def set_view_scale(self, scale: float) -> None:
        scale = max(float(scale), 1e-9)
        size = self.HANDLE_PIXELS / scale
        if size == self._handle_size:
            return
        self.prepareGeometryChange()
        self._handle_size = size
        self._center_cross_arm = self.CENTER_CROSS_ARM_PIXELS / scale
        self.update()

    def crop_qrect(self) -> QRectF:
        rect = self._rect
        return QRectF(float(rect.x), float(rect.y), float(rect.width), float(rect.height))

    def handle_centers(self) -> dict[ResizeHandle, QPointF]:
        rect = self._rect
        left = float(rect.x)
        right = float(rect.x1)
        top = float(rect.y)
        bottom = float(rect.y1)
        center_x = (left + right) / 2.0
        center_y = (top + bottom) / 2.0
        return {
            ResizeHandle.TOP_LEFT: QPointF(left, top),
            ResizeHandle.TOP: QPointF(center_x, top),
            ResizeHandle.TOP_RIGHT: QPointF(right, top),
            ResizeHandle.RIGHT: QPointF(right, center_y),
            ResizeHandle.BOTTOM_RIGHT: QPointF(right, bottom),
            ResizeHandle.BOTTOM: QPointF(center_x, bottom),
            ResizeHandle.BOTTOM_LEFT: QPointF(left, bottom),
            ResizeHandle.LEFT: QPointF(left, center_y),
        }

    def crop_center(self) -> QPointF:
        """Return the exact geometric center in source-pixel coordinates."""

        rect = self._rect
        return QPointF(rect.x + rect.width / 2.0, rect.y + rect.height / 2.0)

    def center_cross_lines(self) -> tuple[QLineF, QLineF]:
        """Return constant-view-size horizontal and vertical center arms."""

        center = self.crop_center()
        arm = self._center_cross_arm
        return (
            QLineF(center.x() - arm, center.y(), center.x() + arm, center.y()),
            QLineF(center.x(), center.y() - arm, center.x(), center.y() + arm),
        )

    def handle_rects(self) -> dict[ResizeHandle, QRectF]:
        half = self._handle_size / 2.0
        return {
            handle: QRectF(
                center.x() - half,
                center.y() - half,
                self._handle_size,
                self._handle_size,
            )
            for handle, center in self.handle_centers().items()
        }

    def handle_at(self, scene_position: QPointF) -> ResizeHandle | None:
        handle_rects = self.handle_rects()
        candidates = [
            (handle, center)
            for handle, center in self.handle_centers().items()
            if handle_rects[handle].contains(scene_position)
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (
                item[1].x() - scene_position.x()
            ) ** 2
            + (item[1].y() - scene_position.y()) ** 2,
        )[0]

    def contains_crop(self, scene_position: QPointF) -> bool:
        return self.crop_qrect().contains(scene_position)

    def boundingRect(self) -> QRectF:  # noqa: N802
        margin = max(self._handle_size / 2.0, self._center_cross_arm) + 2.0
        return self.crop_qrect().adjusted(-margin, -margin, margin, margin)

    def paint(
        self,
        painter: QPainter,
        _option: QStyleOptionGraphicsItem,
        _widget: QWidget | None = None,
    ) -> None:
        border = QPen(QColor(255, 210, 0), 2.0)
        border.setCosmetic(True)
        painter.setPen(border)
        painter.setBrush(QBrush(QColor(255, 210, 0, 28)))
        painter.drawRect(self.crop_qrect())

        center_shadow = QPen(QColor(20, 20, 20, 210), 4.0)
        center_shadow.setCosmetic(True)
        painter.setPen(center_shadow)
        painter.drawLines(self.center_cross_lines())
        center_pen = QPen(QColor(255, 55, 55), 2.0)
        center_pen.setCosmetic(True)
        painter.setPen(center_pen)
        painter.drawLines(self.center_cross_lines())

        handle_pen = QPen(QColor(30, 30, 30), 1.0)
        handle_pen.setCosmetic(True)
        painter.setPen(handle_pen)
        painter.setBrush(QBrush(QColor(255, 225, 70)))
        for handle_rect in self.handle_rects().values():
            painter.drawRect(handle_rect)
