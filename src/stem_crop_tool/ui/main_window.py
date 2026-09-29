"""Main application window for image display and stack navigation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from stem_crop_tool.core.readers.base import ImageDocument, ImageSource
from stem_crop_tool.core.readers.dm import DMDatasetInfo, list_dm_datasets
from stem_crop_tool.infrastructure.display import make_grayscale_qimage
from stem_crop_tool.infrastructure.source_loader import open_image_source
from stem_crop_tool.ui.image_view import ImageView
from stem_crop_tool.ui.stack_controls import StackControls
from stem_crop_tool.ui.workers import DatasetLister, OpenSourceWorker, SourceOpener


SUPPORTED_FILE_FILTER = (
    "Supported Images (*.npy *.png *.jpg *.jpeg *.dm3 *.dm4);;"
    "NumPy Arrays (*.npy);;PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;"
    "DigitalMicrograph Files (*.dm3 *.dm4)"
)


@dataclass(slots=True)
class _LoadJob:
    thread: QThread
    worker: OpenSourceWorker


class MainWindow(QMainWindow):
    """Open supported scientific images without blocking the GUI thread."""

    load_completed = Signal(bool)
    error_presented = Signal(str)

    def __init__(
        self,
        *,
        source_opener: SourceOpener = open_image_source,
        dataset_lister: DatasetLister = list_dm_datasets,
    ) -> None:
        super().__init__()
        self.setWindowTitle("STEMCropTool")
        self.resize(1100, 760)

        self.document = ImageDocument()
        self.current_slice_index = 0
        self.last_error: str | None = None
        self._source_opener = source_opener
        self._dataset_lister = dataset_lister
        self._request_counter = 0
        self._active_request_id: int | None = None
        self._jobs: dict[int, _LoadJob] = {}
        self._busy = False
        self._closing = False

        self.image_view = ImageView()
        self.stack_controls = StackControls()
        self.stack_controls.slice_changed.connect(self.set_current_slice)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.image_view, 1)
        layout.addWidget(self.stack_controls)
        self.setCentralWidget(central)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_status_area()
        self.image_view.zoom_changed.connect(self._update_zoom_status)
        self._update_actions()

    @property
    def current_source(self) -> ImageSource | None:
        return self.document.source

    @property
    def is_loading(self) -> bool:
        return self._busy

    @property
    def loading_job_count(self) -> int:
        return len(self._jobs)

    def _create_actions(self) -> None:
        self.open_action = QAction("&Open...", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_file)

        self.close_action = QAction("&Close Image", self)
        self.close_action.setShortcut(QKeySequence.StandardKey.Close)
        self.close_action.triggered.connect(self.close_document)

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

        self.fit_action = QAction("&Fit to Window", self)
        self.fit_action.setShortcut("F")
        self.fit_action.triggered.connect(self.image_view.fit_to_window)

        self.actual_pixels_action = QAction("&100%", self)
        self.actual_pixels_action.setShortcut("1")
        self.actual_pixels_action.triggered.connect(self.image_view.actual_pixels)

        self.reset_view_action = QAction("&Reset View", self)
        self.reset_view_action.setShortcut("R")
        self.reset_view_action.triggered.connect(self.image_view.reset_view)

        self.crop_action = QAction("Create Crop", self)
        self.crop_action.setEnabled(False)
        self.crop_action.setToolTip("Crop selection is added in Phase 5")

        self.export_action = QAction("Export...", self)
        self.export_action.setEnabled(False)
        self.export_action.setToolTip("Export workflow is added in Phase 6")

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.close_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.fit_action)
        view_menu.addAction(self.actual_pixels_action)
        view_menu.addAction(self.reset_view_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.close_action)
        toolbar.addSeparator()
        toolbar.addAction(self.fit_action)
        toolbar.addAction(self.actual_pixels_action)
        toolbar.addAction(self.reset_view_action)
        toolbar.addSeparator()
        toolbar.addAction(self.crop_action)
        toolbar.addAction(self.export_action)
        self.addToolBar(toolbar)

    def _create_status_area(self) -> None:
        self.source_status_label = QLabel("No image open")
        self.zoom_status_label = QLabel("Zoom: 100%")
        self.busy_indicator = QProgressBar()
        self.busy_indicator.setRange(0, 0)
        self.busy_indicator.setMaximumWidth(120)
        self.busy_indicator.setTextVisible(False)
        self.busy_indicator.hide()
        self.statusBar().addWidget(self.source_status_label, 1)
        self.statusBar().addPermanentWidget(self.zoom_status_label)
        self.statusBar().addPermanentWidget(self.busy_indicator)

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open STEM Image",
            "",
            SUPPORTED_FILE_FILTER,
        )
        if path:
            self.open_path(path)

    def open_path(
        self,
        path: str | Path,
        *,
        dataset_index: int | None = None,
    ) -> int:
        """Start one asynchronous source-open request and return its ID."""

        if self._closing:
            raise RuntimeError("the window is closing")
        self._request_counter += 1
        request_id = self._request_counter
        self._active_request_id = request_id
        self.last_error = None
        self._set_busy(True, f"Opening {Path(path).name}...")

        # QObject parentage keeps the QThread wrapper alive through its own
        # ``finished`` signal even after the Python-side job entry is removed.
        thread = QThread(self)
        thread.setProperty("request_id", request_id)
        worker = OpenSourceWorker(
            request_id,
            path,
            dataset_index=dataset_index,
            opener=self._source_opener,
            dataset_lister=self._dataset_lister,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.opened.connect(self._on_source_opened)
        worker.selection_required.connect(self._on_dataset_selection_required)
        worker.failed.connect(self._on_load_failed)
        worker.finished.connect(self._on_load_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._cleanup_finished_thread)
        thread.finished.connect(thread.deleteLater)
        self._jobs[request_id] = _LoadJob(thread=thread, worker=worker)
        thread.start()
        return request_id

    def _on_source_opened(self, request_id: int, source: ImageSource) -> None:
        if self._closing or request_id != self._active_request_id:
            source.close()
            return

        try:
            first_slice = source.get_slice(0)
            frame = make_grayscale_qimage(first_slice)
        except Exception as exc:
            source.close()
            self._present_error(f"Could not display '{source.metadata.source_name}': {exc}")
            self.load_completed.emit(False)
            return

        self.document.replace_source(source)
        self.current_slice_index = 0
        self.image_view.set_frame(frame, source_index=0)
        self.stack_controls.set_slice_count(source.slice_count)
        self.stack_controls.set_current_index(0)
        self.setWindowTitle(f"{source.metadata.source_name} — STEMCropTool")
        self._update_source_status()
        self._update_actions()
        self.load_completed.emit(True)

    def _on_dataset_selection_required(
        self,
        request_id: int,
        path: str,
        infos: tuple[DMDatasetInfo, ...],
    ) -> None:
        if self._closing or request_id != self._active_request_id:
            return
        if not infos:
            self._present_error("The DM file has no supported 2D or 3D dataset.")
            return

        labels = [self._dataset_label(info) for info in infos]
        selected, accepted = QInputDialog.getItem(
            self,
            "Select DM Dataset",
            "Dataset:",
            labels,
            0,
            False,
        )
        if accepted:
            selected_index = labels.index(selected)
            self.open_path(path, dataset_index=infos[selected_index].index)

    @staticmethod
    def _dataset_label(info: DMDatasetInfo) -> str:
        shape = " × ".join(str(value) for value in info.shape)
        return f"Dataset {info.index}: {shape}, {info.dtype}"

    def _on_load_failed(self, request_id: int, message: str) -> None:
        if self._closing or request_id != self._active_request_id:
            return
        self._present_error(message)
        self.load_completed.emit(False)

    def _on_load_finished(self, request_id: int) -> None:
        if not self._closing and request_id == self._active_request_id:
            self._active_request_id = None
            self._set_busy(False)

    @Slot()
    def _cleanup_finished_thread(self) -> None:
        thread = self.sender()
        if not isinstance(thread, QThread):
            return
        request_id = thread.property("request_id")
        if request_id is not None:
            self._jobs.pop(int(request_id), None)

    def set_current_slice(self, index: int) -> None:
        source = self.document.source
        if source is None:
            return
        index = int(index)
        if index == self.current_slice_index and self.image_view.source_index == index:
            return
        try:
            source_slice = source.get_slice(index)
            frame = make_grayscale_qimage(source_slice)
        except Exception as exc:
            self.stack_controls.set_current_index(self.current_slice_index)
            self._present_error(f"Could not display slice {index}: {exc}")
            return

        self.current_slice_index = index
        self.image_view.set_frame(frame, source_index=index, reset_view=False)
        self.stack_controls.set_current_index(index)
        self._update_source_status()

    def close_document(self) -> None:
        if self._busy:
            return
        self.document.close()
        self.current_slice_index = 0
        self.image_view.clear_image()
        self.stack_controls.set_slice_count(1)
        self.setWindowTitle("STEMCropTool")
        self.source_status_label.setText("No image open")
        self._update_actions()

    def _update_source_status(self) -> None:
        source = self.document.source
        if source is None:
            self.source_status_label.setText("No image open")
            return
        height, width = source.metadata.image_shape
        details = f"{source.metadata.source_name} | {width} × {height} | {source.dtype}"
        if source.slice_count > 1:
            details += f" | Slice {self.current_slice_index + 1} / {source.slice_count}"
        self.source_status_label.setText(details)

    def _update_zoom_status(self, factor: float) -> None:
        self.zoom_status_label.setText(f"Zoom: {factor * 100:.0f}%")

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = bool(busy)
        self.busy_indicator.setVisible(self._busy)
        if message:
            self.statusBar().showMessage(message)
        elif not self._busy:
            self.statusBar().clearMessage()
        self._update_actions()

    def _update_actions(self) -> None:
        has_source = self.document.source is not None
        self.open_action.setEnabled(not self._busy)
        self.close_action.setEnabled(has_source and not self._busy)
        self.fit_action.setEnabled(has_source)
        self.actual_pixels_action.setEnabled(has_source)
        self.reset_view_action.setEnabled(has_source)
        # Crop and export intentionally stay disabled until Phases 5 and 6.
        self.crop_action.setEnabled(False)
        self.export_action.setEnabled(False)

    def _present_error(self, message: str) -> None:
        self.last_error = str(message)
        self.error_presented.emit(self.last_error)
        QMessageBox.warning(self, "STEMCropTool", self.last_error)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._closing = True
        self._active_request_id = None
        for job in tuple(self._jobs.values()):
            job.worker.cancel()
        for job in tuple(self._jobs.values()):
            if job.thread.isRunning():
                job.thread.quit()
                job.thread.wait()
        # Deliver any source result queued immediately before shutdown; the
        # closing guard makes its handler close that source instead of adopting it.
        QCoreApplication.processEvents()
        self._jobs.clear()
        self.document.close()
        super().closeEvent(event)
