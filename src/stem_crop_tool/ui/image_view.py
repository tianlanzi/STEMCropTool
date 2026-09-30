"""Graphics-view image display with zoom and pan controls."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from stem_crop_tool.core.crop import (
    ResizeHandle,
    rect_from_drag,
    resize_rect_from_handle,
    translate_rect,
    validate_rect_within,
)
from stem_crop_tool.core.models import CropRect
from stem_crop_tool.infrastructure.display import DisplayFrame, make_grayscale_qimage
from stem_crop_tool.ui.crop_item import CropItem


class ImageView(QGraphicsView):
    """Display one source slice without retaining or changing source values."""

    zoom_changed = Signal(float)
    crop_changed = Signal(object)

    MINIMUM_ZOOM = 0.02
    MAXIMUM_ZOOM = 128.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("image_view")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(
            Qt.TransformationMode.FastTransformation
        )
        self._scene.addItem(self._pixmap_item)
        self._frame: DisplayFrame | None = None
        self._source_index: int | None = None
        self._crop_item = CropItem(CropRect(0, 0, 1, 1))
        self._crop_item.hide()
        self._scene.addItem(self._crop_item)
        self._crop_rect: CropRect | None = None
        self._crop_enabled = False
        self._interaction_mode: str | None = None
        self._interaction_handle: ResizeHandle | None = None
        self._interaction_start = (0, 0)
        self._interaction_original: CropRect | None = None
        self._panning = False
        self._last_pan_position = QPoint()
        self._fit_mode = True

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setBackgroundBrush(QColor("#272c31"))
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setRenderHints(self.renderHints())
        self.empty_state = self._create_empty_state()
        self._position_empty_state()

    def _create_empty_state(self) -> QWidget:
        panel = QWidget(self.viewport())
        panel.setObjectName("empty_state")
        panel.setProperty("dropActive", False)
        panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        panel.setFixedSize(400, 210)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "app_icon.svg"
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(QSize(46, 46)))

        title = QLabel("Drop a STEM image here")
        title.setObjectName("empty_state_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("or choose Open from the toolbar")
        subtitle.setObjectName("empty_state_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats = QLabel("NPY  ·  PNG  ·  JPEG  ·  DM3  ·  DM4")
        formats.setObjectName("empty_state_formats")
        formats.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(7)
        layout.addStretch(1)
        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(5)
        layout.addWidget(formats)
        layout.addStretch(1)
        panel.show()
        return panel

    def _position_empty_state(self) -> None:
        if not hasattr(self, "empty_state"):
            return
        viewport_rect = self.viewport().rect()
        size = self.empty_state.size()
        x = max(0, (viewport_rect.width() - size.width()) // 2)
        y = max(0, (viewport_rect.height() - size.height()) // 2)
        self.empty_state.move(x, y)

    def set_drop_active(self, active: bool) -> None:
        """Highlight the empty view while a supported file is dragged over it."""

        active = bool(active)
        self.setProperty("dropActive", active)
        self.empty_state.setProperty("dropActive", active)
        self.setBackgroundBrush(QColor("#1f3b3d" if active else "#272c31"))
        for widget in (self, self.empty_state):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

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

    @property
    def crop_rect(self) -> CropRect | None:
        return self._crop_rect

    @property
    def image_shape(self) -> tuple[int, int] | None:
        if self._frame is None:
            return None
        return tuple(int(value) for value in self._frame.buffer.shape)

    def set_image(self, array, *, source_index: int = 0) -> None:
        self.set_frame(make_grayscale_qimage(array), source_index=source_index)

    def set_frame(
        self,
        frame: DisplayFrame,
        *,
        source_index: int = 0,
        reset_view: bool = True,
        preserve_crop: bool = False,
    ) -> None:
        previous_crop = self.crop_rect
        new_height, new_width = frame.buffer.shape
        if not preserve_crop:
            self.clear_crop()
        elif previous_crop is not None:
            try:
                validate_rect_within(previous_crop, new_width, new_height)
            except Exception:
                self.clear_crop()
        pixmap = QPixmap.fromImage(frame.image)
        pixmap.setDevicePixelRatio(1.0)
        self._frame = frame
        self._source_index = int(source_index)
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.empty_state.hide()
        if reset_view:
            self.fit_to_window()
        else:
            self._update_crop_scale()

    def clear_image(self) -> None:
        self.clear_crop()
        self._frame = None
        self._source_index = None
        self._pixmap_item.setPixmap(QPixmap())
        self._scene.setSceneRect(0.0, 0.0, 0.0, 0.0)
        self.resetTransform()
        self._fit_mode = True
        self.empty_state.show()
        self._position_empty_state()
        self.zoom_changed.emit(1.0)

    def set_crop_enabled(self, enabled: bool) -> None:
        self._crop_enabled = bool(enabled)
        if not self._crop_enabled:
            self._cancel_interaction()
            self.viewport().unsetCursor()

    def start_new_crop(self) -> None:
        if not self.has_image or not self._crop_enabled:
            return
        self.clear_crop()
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.setFocus()

    def set_crop_rect(self, rect: CropRect | None) -> None:
        if rect is None:
            self.clear_crop()
            return
        shape = self.image_shape
        if shape is None:
            raise RuntimeError("cannot set a crop without an image")
        height, width = shape
        validated = validate_rect_within(rect, width, height)
        self._crop_rect = validated
        self._crop_item.set_crop_rect(validated)
        self._crop_item.show()
        self._update_crop_scale()
        self.crop_changed.emit(validated)

    def clear_crop(self) -> None:
        if self._crop_rect is None:
            return
        self._crop_rect = None
        self._crop_item.hide()
        self._cancel_interaction()
        self.crop_changed.emit(None)

    def scene_to_pixel_boundary(self, scene_position: QPointF) -> tuple[int, int]:
        """Snap a scene point to the nearest bounded integer pixel boundary."""

        shape = self.image_shape
        if shape is None:
            raise RuntimeError("cannot map coordinates without an image")
        height, width = shape
        x = math.floor(float(scene_position.x()) + 0.5)
        y = math.floor(float(scene_position.y()) + 0.5)
        return min(max(x, 0), width), min(max(y, 0), height)

    def viewport_to_pixel_boundary(self, position: QPoint) -> tuple[int, int]:
        return self.scene_to_pixel_boundary(self.mapToScene(position))

    def actual_pixels(self) -> None:
        """Set one image pixel to one logical scene pixel before device scaling."""

        if not self.has_image:
            return
        self.resetTransform()
        self.centerOn(self._pixmap_item)
        self._fit_mode = False
        self._zoom_updated()

    def fit_to_window(self) -> None:
        if not self.has_image:
            return
        self.resetTransform()
        self.fitInView(
            self._pixmap_item.boundingRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self._fit_mode = True
        self._zoom_updated()

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
        self._zoom_updated()

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
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.has_image
            and self._crop_enabled
        ):
            scene_position = self.mapToScene(event.position().toPoint())
            if not self._image_scene_rect().contains(scene_position):
                event.ignore()
                return
            self.setFocus()
            self._interaction_start = self.scene_to_pixel_boundary(scene_position)
            self._interaction_original = self.crop_rect
            handle = (
                None
                if self._crop_rect is None
                else self._crop_item.handle_at(scene_position)
            )
            if handle is not None:
                self._interaction_mode = "resize"
                self._interaction_handle = handle
            elif self._crop_rect is not None and self._crop_item.contains_crop(
                scene_position
            ):
                self._interaction_mode = "move"
            else:
                self._interaction_mode = "create"
                self._interaction_original = None
                self._update_crop_interaction(scene_position, event.modifiers())
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
        if self._interaction_mode is not None:
            scene_position = self.mapToScene(event.position().toPoint())
            self._update_crop_interaction(scene_position, event.modifiers())
            event.accept()
            return
        self._update_hover_cursor(self.mapToScene(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.viewport().unsetCursor()
            event.accept()
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._interaction_mode is not None
        ):
            scene_position = self.mapToScene(event.position().toPoint())
            self._update_crop_interaction(scene_position, event.modifiers())
            self._cancel_interaction()
            self._update_hover_cursor(scene_position)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.clear_crop()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._position_empty_state()
        if self._fit_mode and self.has_image:
            self.fit_to_window()

    def _image_scene_rect(self) -> QRectF:
        shape = self.image_shape
        if shape is None:
            return QRectF()
        height, width = shape
        return QRectF(0.0, 0.0, float(width), float(height))

    def _update_crop_interaction(
        self,
        scene_position: QPointF,
        modifiers: Qt.KeyboardModifier,
    ) -> None:
        shape = self.image_shape
        if shape is None or self._interaction_mode is None:
            return
        height, width = shape
        end_x, end_y = self.scene_to_pixel_boundary(scene_position)
        start_x, start_y = self._interaction_start
        square = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if self._interaction_mode == "create":
            rect = rect_from_drag(
                start_x,
                start_y,
                end_x,
                end_y,
                width,
                height,
                square=square,
            )
        elif self._interaction_mode == "move":
            if self._interaction_original is None:
                return
            rect = translate_rect(
                self._interaction_original,
                end_x - start_x,
                end_y - start_y,
                width,
                height,
            )
        else:
            if self._interaction_original is None or self._interaction_handle is None:
                return
            rect = resize_rect_from_handle(
                self._interaction_original,
                self._interaction_handle,
                end_x,
                end_y,
                width,
                height,
                square=square,
            )
        self.set_crop_rect(rect)

    def _cancel_interaction(self) -> None:
        self._interaction_mode = None
        self._interaction_handle = None
        self._interaction_original = None

    def _update_crop_scale(self) -> None:
        if self._crop_rect is not None:
            self._crop_item.set_view_scale(self.zoom_factor)

    def _zoom_updated(self) -> None:
        self._update_crop_scale()
        self.zoom_changed.emit(self.zoom_factor)

    def _update_hover_cursor(self, scene_position: QPointF) -> None:
        if not self._crop_enabled or not self.has_image:
            self.viewport().unsetCursor()
            return
        if self._crop_rect is not None:
            handle = self._crop_item.handle_at(scene_position)
            if handle is not None:
                cursors = {
                    ResizeHandle.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
                    ResizeHandle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
                    ResizeHandle.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
                    ResizeHandle.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
                    ResizeHandle.LEFT: Qt.CursorShape.SizeHorCursor,
                    ResizeHandle.RIGHT: Qt.CursorShape.SizeHorCursor,
                    ResizeHandle.TOP: Qt.CursorShape.SizeVerCursor,
                    ResizeHandle.BOTTOM: Qt.CursorShape.SizeVerCursor,
                }
                self.viewport().setCursor(cursors[handle])
                return
            if self._crop_item.contains_crop(scene_position):
                self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
                return
        if self._image_scene_rect().contains(scene_position):
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.viewport().unsetCursor()
