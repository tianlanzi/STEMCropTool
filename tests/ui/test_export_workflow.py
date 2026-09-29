from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QDialog, QPushButton

import stem_crop_tool.ui.main_window as main_window_module
from stem_crop_tool.core.batch import all_slice_indices, inclusive_slice_range
from stem_crop_tool.core.exceptions import ExportValidationError
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    ImageMetadata,
    NormalizationMode,
)
from stem_crop_tool.infrastructure.exporters import export_source
from stem_crop_tool.ui.main_window import MainWindow, QMessageBox


class ArraySource:
    def __init__(self, name: str, array: np.ndarray, *, delay: float = 0.0) -> None:
        self.path = Path(name)
        self.array = np.asarray(array)
        self.shape = self.array.shape
        self.dtype = self.array.dtype
        self.ndim = self.array.ndim
        self.slice_count = self.shape[0] if self.ndim == 3 else 1
        self.metadata = ImageMetadata(name, "npy", self.shape, self.dtype)
        self.delay = delay
        self.requested: list[int] = []
        self.close_count = 0

    def get_slice(self, index: int = 0) -> np.ndarray:
        if self.delay:
            time.sleep(self.delay)
        self.requested.append(index)
        return self.array if self.ndim == 2 else self.array[index]

    def close(self) -> None:
        self.close_count += 1


def _window_for_source(source: ArraySource, qtbot, **kwargs) -> MainWindow:
    def opener(_path, **_open_kwargs):
        return source

    window = MainWindow(source_opener=opener, **kwargs)
    qtbot.addWidget(window)
    window.show()
    window.open_path(source.path)
    qtbot.waitUntil(lambda: not window.is_loading, timeout=5000)
    qtbot.waitUntil(lambda: window.loading_job_count == 0, timeout=5000)
    return window


def _wait_for_export(window: MainWindow, qtbot) -> None:
    qtbot.waitUntil(lambda: not window.is_exporting, timeout=10000)
    qtbot.waitUntil(lambda: window.export_job_count == 0, timeout=10000)


def _silence_messages(monkeypatch) -> None:
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)


def test_single_2d_export_is_started_from_export_action(
    tmp_path,
    qtbot,
    monkeypatch,
) -> None:
    _silence_messages(monkeypatch)
    data = np.arange(8 * 9, dtype=np.int16).reshape(8, 9)
    source = ArraySource("image.npy", data)
    window = _window_for_source(source, qtbot)
    crop = CropRect(2, 3, 4, 3)
    window.image_view.set_crop_rect(crop)
    destination = tmp_path / "crop.npy"
    request = ExportRequest(destination, crop, ExportFormat.NPY)

    class AcceptedDialog:
        def __init__(self, *_args, **_kwargs) -> None:
            self.request = request

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_module, "ExportDialog", AcceptedDialog)
    window.export_action.trigger()
    _wait_for_export(window, qtbot)

    np.testing.assert_array_equal(
        np.load(destination, allow_pickle=False),
        data[3:6, 2:6],
    )
    payload = json.loads(destination.with_suffix(".json").read_text("utf-8"))
    assert payload["crop"] == {"x": 2, "y": 3, "width": 4, "height": 3}
    assert window.last_export_result is not None
    assert window.export_action.isEnabled()


def test_stack_current_range_and_all_export_workflows(
    tmp_path,
    qtbot,
    monkeypatch,
) -> None:
    _silence_messages(monkeypatch)
    stack = np.arange(5 * 6 * 7, dtype=np.uint16).reshape(5, 6, 7)
    source = ArraySource("stack.npy", stack)
    window = _window_for_source(source, qtbot)
    crop = CropRect(1, 2, 4, 3)
    window.image_view.set_crop_rect(crop)
    window.set_current_slice(3)

    current_path = tmp_path / "current.npy"
    window.start_export(
        ExportRequest(current_path, crop, ExportFormat.NPY, slice_indices=(3,))
    )
    _wait_for_export(window, qtbot)
    np.testing.assert_array_equal(
        np.load(current_path, allow_pickle=False),
        stack[3, 2:5, 1:5],
    )

    range_directory = tmp_path / "range"
    window.start_export(
        ExportRequest(
            range_directory,
            crop,
            ExportFormat.NPY,
            slice_indices=inclusive_slice_range(1, 3, source.slice_count),
        )
    )
    _wait_for_export(window, qtbot)
    assert window.last_export_result is not None
    assert window.last_export_result.completed_slice_indices == (1, 2, 3)

    all_directory = tmp_path / "all"
    window.start_export(
        ExportRequest(
            all_directory,
            crop,
            ExportFormat.PNG,
            normalization=NormalizationMode.LOCAL_MINMAX,
            slice_indices=all_slice_indices(source.slice_count),
        )
    )
    _wait_for_export(window, qtbot)
    assert window.last_export_result is not None
    assert window.last_export_result.completed_slice_indices == tuple(range(5))
    manifest = json.loads((all_directory / "manifest.json").read_text("utf-8"))
    assert manifest["normalization"] == "local_minmax"
    assert manifest["completed_slice_indices"] == list(range(5))


def test_slow_batch_keeps_gui_responsive_and_cancels_between_slices(
    tmp_path,
    qtbot,
    monkeypatch,
) -> None:
    _silence_messages(monkeypatch)
    stack = np.arange(12 * 512 * 512, dtype=np.uint16).reshape(12, 512, 512)
    source = ArraySource("slow.npy", stack, delay=0.04)
    window = _window_for_source(source, qtbot)
    crop = CropRect(96, 112, 220, 180)
    window.image_view.set_crop_rect(crop)
    progress = []
    window.export_progressed.connect(progress.append)
    request = ExportRequest(
        tmp_path / "cancelled",
        crop,
        ExportFormat.NPY,
        slice_indices=all_slice_indices(source.slice_count),
    )

    window.start_export(request)
    assert not window.open_action.isEnabled()
    assert not window.crop_controls.isEnabled()
    assert not window.stack_controls.isEnabled()
    gui_tick = []
    QTimer.singleShot(0, lambda: gui_tick.append(True))
    qtbot.waitUntil(lambda: bool(gui_tick))
    qtbot.waitUntil(lambda: len(progress) >= 1, timeout=5000)
    progress_dialog = window.export_progress_dialog
    assert progress_dialog is not None
    assert progress_dialog.maximum() == source.slice_count
    assert progress_dialog.value() == progress[-1].completed
    assert f"slice {progress[-1].slice_index}" in progress_dialog.labelText()
    cancel_button = next(
        button
        for button in progress_dialog.findChildren(QPushButton)
        if button.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
    _wait_for_export(window, qtbot)

    result = window.last_export_result
    assert result is not None and result.cancelled
    assert 1 <= len(result.output_paths) < source.slice_count
    manifest = json.loads((tmp_path / "cancelled" / "manifest.json").read_text("utf-8"))
    assert manifest["cancelled"] is True
    assert len(manifest["completed_slice_indices"]) == len(result.output_paths)
    assert list((tmp_path / "cancelled").glob(".*.tmp")) == []
    assert window.open_action.isEnabled()
    assert window.crop_controls.isEnabled()


def test_export_uses_roi_snapshot_even_if_live_roi_changes(
    tmp_path,
    qtbot,
    monkeypatch,
) -> None:
    _silence_messages(monkeypatch)
    started = Event()
    release = Event()

    def gated_exporter(source, request, **kwargs):
        started.set()
        release.wait(timeout=3)
        return export_source(source, request, **kwargs)

    data = np.arange(10 * 12, dtype=np.uint16).reshape(10, 12)
    source = ArraySource("snapshot.npy", data)
    window = _window_for_source(source, qtbot, source_exporter=gated_exporter)
    original_crop = CropRect(1, 2, 4, 3)
    window.image_view.set_crop_rect(original_crop)
    destination = tmp_path / "snapshot.npy"
    request = ExportRequest(destination, original_crop, ExportFormat.NPY)
    window.start_export(request)
    qtbot.waitUntil(started.is_set)

    window.image_view.set_crop_rect(CropRect(5, 5, 2, 2))
    release.set()
    _wait_for_export(window, qtbot)

    np.testing.assert_array_equal(
        np.load(destination, allow_pickle=False),
        data[2:5, 1:5],
    )
    assert window.current_crop == CropRect(5, 5, 2, 2)


def test_worker_error_restores_actions_and_document(
    tmp_path,
    qtbot,
    monkeypatch,
) -> None:
    _silence_messages(monkeypatch)

    def failing_exporter(_source, _request, **_kwargs):
        raise ExportValidationError("planned export failure")

    source = ArraySource("failure.npy", np.ones((6, 6), dtype=np.uint8))
    window = _window_for_source(source, qtbot, source_exporter=failing_exporter)
    crop = CropRect(1, 1, 3, 3)
    window.image_view.set_crop_rect(crop)
    window.start_export(
        ExportRequest(tmp_path / "failure.npy", crop, ExportFormat.NPY)
    )
    _wait_for_export(window, qtbot)

    assert window.last_export_result is None
    assert window.last_export_error == "planned export failure"
    assert window.current_source is source
    assert window.export_action.isEnabled()
    assert window.crop_controls.isEnabled()
