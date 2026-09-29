"""Graphics-view image display with zoom and pan controls."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from stem_crop_tool.infrastructure.display import DisplayFrame, make_grayscale_qimage


class ImageView(QGraphicsView):
    """Display one source slice without retaining or changing source values."""

    zoom_changed = Signal(float)

    MINIMUM_ZOOM = 0.02
    MAXIMUM_ZOOM = 128.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(
            Qt.TransformationMode.FastTransformation
        )
        self._scene.addItem(self._pixmap_item)
        self._frame: DisplayFrame | None = None
        self._source_index: int | None = None
        self._panning = False
        self._last_pan_position = QPoint()
        self._fit_mode = True

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRenderHints(self.renderHints())

    @property
    def source_index(self) -> int | None:
        return self._source_index

    @property
    def display_buffer(self):
        return None if self._frame is None else self._frame.buffer

    @property
    def zoom_factor(self) -> float:
        return float(self.transform().m11())

    @property
    def has_image(self) -> bool:
        return self._frame is not None

    def set_image(self, array, *, source_index: int = 0) -> None:
        self.set_frame(make_grayscale_qimage(array), source_index=source_index)

    def set_frame(
        self,
        frame: DisplayFrame,
        *,
        source_index: int = 0,
        reset_view: bool = True,
    ) -> None:
        pixmap = QPixmap.fromImage(frame.image)
        pixmap.setDevicePixelRatio(1.0)
        self._frame = frame
        self._source_index = int(source_index)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        if reset_view:
            self.fit_to_window()

    def clear_image(self) -> None:
        self._frame = None
        self._source_index = None
        self._pixmap_item.setPixmap(QPixmap())
        self._scene.setSceneRect(0.0, 0.0, 0.0, 0.0)
        self.resetTransform()
        self._fit_mode = True
        self.zoom_changed.emit(1.0)

    def actual_pixels(self) -> None:
        """Set one image pixel to one logical scene pixel before device scaling."""

        if not self.has_image:
            return
        self.resetTransform()
        self.centerOn(self._pixmap_item)
        self._fit_mode = False
        self.zoom_changed.emit(self.zoom_factor)

    def fit_to_window(self) -> None:
        if not self.has_image:
            return
        self.resetTransform()
        self.fitInView(
            self._pixmap_item.boundingRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self._fit_mode = True
        self.zoom_changed.emit(self.zoom_factor)

    def reset_view(self) -> None:
        """Restore the initial fit-to-window view."""

        self.fit_to_window()

    def zoom_by(self, factor: float) -> None:
        if not self.has_image or factor <= 0:
            return
        current = self.zoom_factor
        target = min(self.MAXIMUM_ZOOM, max(self.MINIMUM_ZOOM, current * factor))
        applied = target / current
        if applied == 1.0:
            return
        self.scale(applied, applied)
        self._fit_mode = False
        self.zoom_changed.emit(self.zoom_factor)

    def pan_by(self, dx: int, dy: int) -> None:
        """Move the viewport by logical scrollbar units (also used by tests)."""

        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - int(dx)
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(dy)
        )
        self._fit_mode = False

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self.zoom_by(1.25 if delta > 0 else 0.8)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self.has_image:
            self._panning = True
            self._last_pan_position = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning:
            position = event.position().toPoint()
            delta = position - self._last_pan_position
            self._last_pan_position = position
            self.pan_by(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._fit_mode and self.has_image:
            self.fit_to_window()
