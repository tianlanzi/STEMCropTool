from __future__ import annotations

from pathlib import Path
from threading import Event

import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage

from stem_crop_tool.core.exceptions import DatasetSelectionRequiredError
from stem_crop_tool.core.models import CropRect, ImageMetadata
from stem_crop_tool.core.readers.dm import DMDatasetInfo
from stem_crop_tool.ui.crop_item import CropItem
from stem_crop_tool.ui.main_window import (
    MainWindow,
    QMessageBox,
    QInputDialog,
    SUPPORTED_FILE_FILTER,
)


class TrackedSource:
    def __init__(self, name: str, data: np.ndarray) -> None:
        self.path = Path(name)
        self._data = np.asarray(data)
        self.shape = self._data.shape
        self.dtype = self._data.dtype
        self.ndim = self._data.ndim
        self.slice_count = self.shape[0] if self.ndim == 3 else 1
        self.metadata = ImageMetadata(name, "npy", self.shape, self.dtype)
        self.requested_indices: list[int] = []
        self.close_count = 0

    def get_slice(self, index: int = 0) -> np.ndarray:
        self.requested_indices.append(index)
        result = self._data if self.ndim == 2 else self._data[index]
        result.flags.writeable = False
        return result

    def close(self) -> None:
        self.close_count += 1


def _wait_for_idle(window: MainWindow, qtbot) -> None:
    qtbot.waitUntil(lambda: not window.is_loading, timeout=5000)
    qtbot.waitUntil(lambda: window.loading_job_count == 0, timeout=5000)


def _file_mime_data(*paths: Path) -> QMimeData:
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    return mime_data


def _drag_enter_event(mime_data: QMimeData) -> QDragEnterEvent:
    return QDragEnterEvent(
        QPoint(20, 20),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _drop_event(mime_data: QMimeData) -> QDropEvent:
    return QDropEvent(
        QPointF(20, 20),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_supported_file_filter_is_exact_initial_scope() -> None:
    for extension in ("*.npy", "*.png", "*.jpg", "*.jpeg", "*.dm3", "*.dm4"):
        assert extension in SUPPORTED_FILE_FILTER
    for excluded in ("*.npz", "*.tif", "*.tiff"):
        assert excluded not in SUPPORTED_FILE_FILTER


def test_single_supported_file_drop_opens_through_normal_worker(
    tmp_path,
    qtbot,
) -> None:
    path = tmp_path / "dropped.npy"
    expected = np.arange(30, dtype=np.uint16).reshape(5, 6)
    np.save(path, expected)
    mime_data = _file_mime_data(path)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.acceptDrops()
    assert not window.image_view.acceptDrops()
    assert not window.image_view.viewport().acceptDrops()

    drag_event = _drag_enter_event(mime_data)
    window.dragEnterEvent(drag_event)
    assert drag_event.isAccepted()
    assert path.name in window.statusBar().currentMessage()

    drop_event = _drop_event(mime_data)
    window.dropEvent(drop_event)
    assert drop_event.isAccepted()
    _wait_for_idle(window, qtbot)

    assert window.current_source is not None
    assert window.current_source.path == path
    np.testing.assert_array_equal(window.current_source.get_slice(), expected)


def test_file_drop_rejects_multiple_unsupported_and_missing_paths(
    tmp_path,
    qtbot,
) -> None:
    supported_a = tmp_path / "a.npy"
    supported_b = tmp_path / "b.npy"
    unsupported = tmp_path / "notes.txt"
    np.save(supported_a, np.zeros((2, 2), dtype=np.uint8))
    np.save(supported_b, np.ones((2, 2), dtype=np.uint8))
    unsupported.write_text("not an image", encoding="utf-8")

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    payloads = (
        _file_mime_data(supported_a, supported_b),
        _file_mime_data(unsupported),
        _file_mime_data(tmp_path / "missing.npy"),
    )
    for mime_data in payloads:
        drag_event = _drag_enter_event(mime_data)
        window.dragEnterEvent(drag_event)
        assert not drag_event.isAccepted()

        drop_event = _drop_event(mime_data)
        window.dropEvent(drop_event)
        assert not drop_event.isAccepted()

    assert window.current_source is None
    assert window.loading_job_count == 0


def test_window_opens_2d_and_3d_npy_and_switches_lazily(tmp_path, qtbot) -> None:
    image_path = tmp_path / "image.npy"
    stack_path = tmp_path / "stack.npy"
    np.save(image_path, np.arange(20, dtype=np.uint16).reshape(4, 5))
    stack = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
    np.save(stack_path, stack)

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.open_path(image_path)
    _wait_for_idle(window, qtbot)
    assert window.current_source is not None
    assert window.current_source.shape == (4, 5)
    assert not window.stack_controls.isVisible()
    assert window.image_view.source_index == 0

    old_source = window.current_source
    window.open_path(stack_path)
    _wait_for_idle(window, qtbot)
    assert getattr(old_source, "closed")
    assert window.current_source is not None
    assert window.current_source.shape == (3, 4, 5)
    assert window.stack_controls.isVisible()

    window.stack_controls.spin_box.setValue(2)
    assert window.current_slice_index == 2
    assert window.image_view.source_index == 2
    expected = np.rint((stack[2] - stack[2].min()) / np.ptp(stack[2]) * 255).astype(
        np.uint8
    )
    np.testing.assert_array_equal(window.image_view.display_buffer, expected)


@pytest.mark.parametrize("suffix", [".png", ".jpg"])
def test_window_opens_supported_grayscale_rasters(tmp_path, qtbot, suffix) -> None:
    path = tmp_path / f"image{suffix}"
    image = QImage(6, 4, QImage.Format.Format_Grayscale8)
    image.fill(73)
    assert image.save(str(path))

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_path(path)
    _wait_for_idle(window, qtbot)

    assert window.current_source is not None
    assert window.current_source.shape == (4, 6)
    assert window.image_view.display_buffer.shape == (4, 6)
    assert not window.stack_controls.isVisible()


def test_failed_open_preserves_existing_document(tmp_path, qtbot, monkeypatch) -> None:
    path = tmp_path / "valid.npy"
    np.save(path, np.arange(9, dtype=np.uint8).reshape(3, 3))
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.open_path(path)
    _wait_for_idle(window, qtbot)
    original_source = window.current_source
    original_buffer = window.image_view.display_buffer.copy()

    window.open_path(tmp_path / "missing.npy")
    _wait_for_idle(window, qtbot)

    assert window.current_source is original_source
    assert not getattr(original_source, "closed")
    np.testing.assert_array_equal(window.image_view.display_buffer, original_buffer)
    assert window.last_error is not None
    assert "could not open" in window.last_error.lower()


def test_opening_runs_off_gui_thread_and_keeps_event_loop_responsive(
    tmp_path,
    qtbot,
) -> None:
    gate = Event()
    worker_started = Event()
    source = TrackedSource("slow.npy", np.arange(16, dtype=np.uint8).reshape(4, 4))
    dropped_path = tmp_path / "during-load.npy"
    np.save(dropped_path, np.zeros((2, 2), dtype=np.uint8))

    def slow_opener(_path, **_kwargs):
        worker_started.set()
        gate.wait(timeout=3)
        return source

    window = MainWindow(source_opener=slow_opener)
    qtbot.addWidget(window)
    window.show()
    window.open_path("slow.npy")
    qtbot.waitUntil(worker_started.is_set)

    gui_tick = []
    QTimer.singleShot(0, lambda: gui_tick.append(True))
    qtbot.waitUntil(lambda: bool(gui_tick))
    assert window.is_loading

    mime_data = _file_mime_data(dropped_path)
    drag_event = _drag_enter_event(mime_data)
    window.dragEnterEvent(drag_event)
    assert not drag_event.isAccepted()
    drop_event = _drop_event(mime_data)
    window.dropEvent(drop_event)
    assert not drop_event.isAccepted()

    gate.set()
    _wait_for_idle(window, qtbot)
    assert window.current_source is source


def test_rapid_repeated_opens_keep_latest_and_cleanup_workers(qtbot) -> None:
    first_started = Event()
    release_first = Event()
    first = TrackedSource("first.npy", np.zeros((2, 2), dtype=np.uint8))
    second = TrackedSource("second.npy", np.ones((2, 2), dtype=np.uint8))

    def opener(path, **_kwargs):
        if Path(path).name == "first.npy":
            first_started.set()
            release_first.wait(timeout=3)
            return first
        return second

    window = MainWindow(source_opener=opener)
    qtbot.addWidget(window)
    window.show()
    window.open_path("first.npy")
    qtbot.waitUntil(first_started.is_set)
    window.open_path("second.npy")
    qtbot.waitUntil(lambda: window.current_source is second)
    release_first.set()
    _wait_for_idle(window, qtbot)

    assert window.current_source is second
    assert first.close_count == 1
    assert second.close_count == 0
    assert window.loading_job_count == 0


def test_slice_navigation_retains_zoom_and_does_not_modify_stack(qtbot) -> None:
    stack = np.arange(2 * 300 * 400, dtype=np.float32).reshape(2, 300, 400)
    original = stack.copy()
    source = TrackedSource("stack.npy", stack)

    def opener(_path, **_kwargs):
        return source

    window = MainWindow(source_opener=opener)
    window.resize(300, 240)
    qtbot.addWidget(window)
    window.show()
    window.open_path("stack.npy")
    _wait_for_idle(window, qtbot)

    window.image_view.actual_pixels()
    window.image_view.zoom_by(1.5)
    zoom = window.image_view.zoom_factor
    window.image_view.pan_by(20, 10)
    window.image_view.set_crop_rect(CropRect(12, 15, 40, 50))
    window.set_current_slice(1)

    assert window.image_view.zoom_factor == zoom
    assert window.current_crop == CropRect(12, 15, 40, 50)
    assert source.requested_indices == [0, 1]
    np.testing.assert_array_equal(stack, original)


def test_numeric_crop_sync_clear_and_file_reopen_reset(tmp_path, qtbot) -> None:
    first_path = tmp_path / "first.npy"
    second_path = tmp_path / "second.npy"
    np.save(first_path, np.zeros((100, 120), dtype=np.uint16))
    np.save(second_path, np.zeros((40, 50), dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.open_path(first_path)
    _wait_for_idle(window, qtbot)

    assert window.current_crop is None
    assert not window.clear_crop_action.isEnabled()
    assert not window.export_action.isEnabled()
    window.image_view.set_crop_rect(CropRect(10, 20, 30, 40))
    assert window.crop_controls.x_spin.value() == 10
    assert window.crop_controls.height_spin.value() == 40
    assert window.clear_crop_action.isEnabled()
    assert "x=10" in window.crop_status_label.text()

    window.crop_controls.x_spin.setValue(100)
    assert window.current_crop == CropRect(100, 20, 20, 40)
    window.image_view.set_crop_rect(CropRect(1, 2, 3, 4))
    assert len(
        [item for item in window.image_view.scene().items() if isinstance(item, CropItem)]
    ) == 1

    window.open_path(second_path)
    _wait_for_idle(window, qtbot)
    assert window.current_crop is None
    assert not window.crop_controls.x_spin.isEnabled()
    assert not window.clear_crop_action.isEnabled()

    window.image_view.set_crop_rect(CropRect(2, 3, 4, 5))
    window.crop_controls.new_button.click()
    assert window.current_crop is None
    window.image_view.set_crop_rect(CropRect(2, 3, 4, 5))
    window.clear_crop_action.trigger()
    assert window.current_crop is None
    assert not window.crop_controls.x_spin.isEnabled()


def test_dm_multiple_dataset_selection_reopens_selected_dataset(
    qtbot,
    monkeypatch,
) -> None:
    source = TrackedSource("multi.dm4", np.ones((3, 4), dtype=np.uint16))
    requested: list[int | None] = []

    def opener(_path, *, dataset_index=None):
        requested.append(dataset_index)
        if dataset_index is None:
            raise DatasetSelectionRequiredError((0, 2))
        assert dataset_index == 2
        return source

    infos = (
        DMDatasetInfo(0, 0, (2, 2), np.dtype(np.uint8)),
        DMDatasetInfo(2, 2, (3, 4), np.dtype(np.uint16)),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args: (args[3][1], True),
    )
    window = MainWindow(source_opener=opener, dataset_lister=lambda _path: infos)
    qtbot.addWidget(window)
    window.show()

    window.open_path("multi.dm4")
    _wait_for_idle(window, qtbot)

    assert requested == [None, 2]
    assert window.current_source is source
