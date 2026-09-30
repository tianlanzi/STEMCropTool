"""Main application window for image display and stack navigation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QMimeData,
    QSize,
    QThread,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from stem_crop_tool.core.readers.base import ImageDocument, ImageSource
from stem_crop_tool.core.readers.dm import DMDatasetInfo, list_dm_datasets
from stem_crop_tool.core.models import CropRect, ExportRequest, ExportResult
from stem_crop_tool.infrastructure.display import make_grayscale_qimage
from stem_crop_tool.infrastructure.source_loader import (
    SUPPORTED_INPUT_EXTENSIONS,
    open_image_source,
)
from stem_crop_tool.ui.crop_controls import CropControls
from stem_crop_tool.ui.export_dialog import ExportDialog
from stem_crop_tool.ui.image_view import ImageView
from stem_crop_tool.ui.stack_controls import StackControls
from stem_crop_tool.ui.workers import (
    DatasetLister,
    ExportFunction,
    ExportWorker,
    OpenSourceWorker,
    SourceOpener,
)


SUPPORTED_FILE_FILTER = (
    "Supported Images (*.npy *.png *.jpg *.jpeg *.dm3 *.dm4);;"
    "NumPy Arrays (*.npy);;PNG Images (*.png);;JPEG Images (*.jpg *.jpeg);;"
    "DigitalMicrograph Files (*.dm3 *.dm4)"
)


@dataclass(slots=True)
class _LoadJob:
    worker: OpenSourceWorker


@dataclass(slots=True)
class _ExportJob:
    worker: ExportWorker


class MainWindow(QMainWindow):
    """Open supported scientific images without blocking the GUI thread."""

    load_completed = Signal(bool)
    error_presented = Signal(str)
    export_progressed = Signal(object)
    export_completed = Signal(object)
    export_failed = Signal(str)

    def __init__(
        self,
        *,
        source_opener: SourceOpener = open_image_source,
        dataset_lister: DatasetLister = list_dm_datasets,
        source_exporter: ExportFunction | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("STEMCropTool")
        self.resize(1100, 760)

        self.document = ImageDocument()
        self.current_slice_index = 0
        self.last_error: str | None = None
        self._source_opener = source_opener
        self._dataset_lister = dataset_lister
        self._source_exporter = source_exporter
        self._request_counter = 0
        self._active_request_id: int | None = None
        self._jobs: dict[int, _LoadJob] = {}
        self._export_job: _ExportJob | None = None
        self._export_active = False
        self._active_export_request: ExportRequest | None = None
        self.export_progress_dialog: QProgressDialog | None = None
        self.last_export_result: ExportResult | None = None
        self.last_export_error: str | None = None
        self._busy = False
        self._closing = False

        self.image_view = ImageView()
        # QGraphicsView accepts drops by default and would consume Explorer
        # file drops before the main window can route them through open_path().
        self.image_view.setAcceptDrops(False)
        self.image_view.viewport().setAcceptDrops(False)
        self.setAcceptDrops(True)
        self.stack_controls = StackControls()
        self.crop_controls = CropControls()
        self.stack_controls.slice_changed.connect(self.set_current_slice)
        self.image_view.crop_changed.connect(self._on_crop_changed)
        self.crop_controls.rect_edited.connect(self.image_view.set_crop_rect)
        self.crop_controls.export_requested.connect(self.show_export_dialog)
        self.crop_controls.clear_requested.connect(self.image_view.clear_crop)

        central = QWidget()
        central.setObjectName("central_panel")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 7)
        layout.setSpacing(7)
        layout.addWidget(self.image_view, 1)
        layout.addWidget(self.stack_controls)
        layout.addWidget(self.crop_controls)
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

    @property
    def is_exporting(self) -> bool:
        return self._export_active

    @property
    def export_job_count(self) -> int:
        return int(self._export_job is not None)

    @property
    def current_crop(self) -> CropRect | None:
        return self.image_view.crop_rect

    def _create_actions(self) -> None:
        self.open_action = QAction("&Open...", self)
        self.open_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setToolTip("Open an image or stack (Ctrl+O)")
        self.open_action.triggered.connect(self.choose_file)

        self.close_action = QAction("&Close Image", self)
        self.close_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton)
        )
        self.close_action.setShortcut(QKeySequence.StandardKey.Close)
        self.close_action.setToolTip("Close the current image (Ctrl+W)")
        self.close_action.triggered.connect(self.close_document)

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

        self.fit_action = QAction("&Fit to Window", self)
        self.fit_action.setShortcut("F")
        self.fit_action.setToolTip("Fit the image to the window (F)")
        self.fit_action.triggered.connect(self.image_view.fit_to_window)

        self.actual_pixels_action = QAction("&100%", self)
        self.actual_pixels_action.setShortcut("1")
        self.actual_pixels_action.setToolTip("Show one screen pixel per image pixel (1)")
        self.actual_pixels_action.triggered.connect(self.image_view.actual_pixels)

        self.reset_view_action = QAction("&Reset View", self)
        self.reset_view_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.reset_view_action.setShortcut("R")
        self.reset_view_action.setToolTip("Reset zoom and position (R)")
        self.reset_view_action.triggered.connect(self.image_view.reset_view)

        self.clear_crop_action = QAction("&Clear Crop", self)
        self.clear_crop_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self.clear_crop_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.clear_crop_action.setToolTip("Remove the current crop (Delete)")
        self.clear_crop_action.triggered.connect(self.image_view.clear_crop)

        self.export_action = QAction("Export...", self)
        self.export_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self.export_action.setShortcut(QKeySequence.StandardKey.Save)
        self.export_action.triggered.connect(self.show_export_dialog)

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

        crop_menu = self.menuBar().addMenu("&Crop")
        crop_menu.addAction(self.clear_crop_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.close_action)
        toolbar.addSeparator()
        toolbar.addAction(self.fit_action)
        toolbar.addAction(self.actual_pixels_action)
        toolbar.addAction(self.reset_view_action)
        toolbar.addSeparator()
        toolbar.addAction(self.clear_crop_action)
        toolbar.addAction(self.export_action)
        self.addToolBar(toolbar)

    def _create_status_area(self) -> None:
        self.source_status_label = QLabel("Ready")
        self.zoom_status_label = QLabel("Zoom: 100%")
        self.crop_status_label = QLabel("Crop: none")
        self.busy_indicator = QProgressBar()
        self.busy_indicator.setRange(0, 0)
        self.busy_indicator.setMaximumWidth(120)
        self.busy_indicator.setTextVisible(False)
        self.busy_indicator.hide()
        self.statusBar().addWidget(self.source_status_label, 1)
        self.statusBar().addPermanentWidget(self.crop_status_label)
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

    @staticmethod
    def _supported_drop_path(mime_data: QMimeData) -> Path | None:
        """Return the only supported local file in a drag payload."""

        if not mime_data.hasUrls():
            return None
        urls = mime_data.urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
            return None
        return path

    def _file_drop_is_available(self) -> bool:
        return not self._closing and not self._busy and not self._export_active

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        path = self._supported_drop_path(event.mimeData())
        if path is not None and self._file_drop_is_available():
            event.acceptProposedAction()
            self.image_view.set_drop_active(True)
            self.statusBar().showMessage(f"Drop to open {path.name}")
        else:
            self.image_view.set_drop_active(False)
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        path = self._supported_drop_path(event.mimeData())
        if path is not None and self._file_drop_is_available():
            event.acceptProposedAction()
        else:
            self.image_view.set_drop_active(False)
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self.image_view.set_drop_active(False)
        if not self._busy:
            self.statusBar().clearMessage()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self.image_view.set_drop_active(False)
        path = self._supported_drop_path(event.mimeData())
        if path is None or not self._file_drop_is_available():
            event.ignore()
            return
        event.acceptProposedAction()
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
        if self._export_active:
            raise RuntimeError("cannot open a source while an export is running")
        self._request_counter += 1
        request_id = self._request_counter
        self._active_request_id = request_id
        self.last_error = None
        self._set_busy(True, f"Opening {Path(path).name}...")

        worker = OpenSourceWorker(
            request_id,
            path,
            dataset_index=dataset_index,
            opener=self._source_opener,
            dataset_lister=self._dataset_lister,
        )
        worker.setParent(self)
        worker.setProperty("request_id", request_id)
        worker.opened.connect(self._on_source_opened)
        worker.selection_required.connect(self._on_dataset_selection_required)
        worker.failed.connect(self._on_load_failed)
        worker.finished.connect(self._cleanup_finished_thread)
        worker.finished.connect(worker.deleteLater)
        self._jobs[request_id] = _LoadJob(worker=worker)
        worker.start()
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
        height, width = source.metadata.image_shape
        self.crop_controls.set_image_size(width, height)
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
            self._on_load_finished(int(request_id))
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
        self.image_view.set_frame(
            frame,
            source_index=index,
            reset_view=False,
            preserve_crop=True,
        )
        self.stack_controls.set_current_index(index)
        self._update_source_status()

    def close_document(self) -> None:
        if self._busy or self._export_active:
            return
        self.document.close()
        self.current_slice_index = 0
        self.image_view.clear_image()
        self.crop_controls.clear_image()
        self.stack_controls.set_slice_count(1)
        self.setWindowTitle("STEMCropTool")
        self.source_status_label.setText("Ready")
        self.crop_status_label.setText("Crop: none")
        self._update_actions()

    def _on_crop_changed(self, rect: CropRect | None) -> None:
        self.crop_controls.set_rect(rect)
        if rect is None:
            self.crop_status_label.setText("Crop: none")
        else:
            self.crop_status_label.setText(
                f"Crop: x={rect.x}, y={rect.y}, {rect.width} × {rect.height}"
            )
        self._update_actions()

    def _update_source_status(self) -> None:
        source = self.document.source
        if source is None:
            self.source_status_label.setText("Ready")
            return
        height, width = source.metadata.image_shape
        details = f"{source.metadata.source_name} | {width} × {height} | {source.dtype}"
        if source.slice_count > 1:
            details += f" | Slice {self.current_slice_index + 1} / {source.slice_count}"
        self.source_status_label.setText(details)

    def _update_zoom_status(self, factor: float) -> None:
        self.zoom_status_label.setText(f"Zoom: {factor * 100:.0f}%")

    def show_export_dialog(self) -> None:
        source = self.document.source
        crop = self.current_crop
        if source is None or crop is None or self._busy or self._export_active:
            return
        dialog = ExportDialog(
            source.metadata,
            crop,
            self.current_slice_index,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.request is not None:
            self.start_export(dialog.request)

    def start_export(self, request: ExportRequest) -> None:
        """Start an asynchronous export from an immutable request snapshot."""

        source = self.document.source
        if source is None:
            raise RuntimeError("no image source is open")
        if self._busy or self._export_active:
            raise RuntimeError("another load or export operation is active")

        self.last_export_result = None
        self.last_export_error = None
        self._active_export_request = request
        total = len(request.slice_indices)
        progress_dialog = QProgressDialog(
            "Preparing export...",
            "Cancel",
            0,
            total,
            self,
        )
        progress_dialog.setWindowTitle("Export Crop")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.canceled.connect(self.cancel_export)
        self.export_progress_dialog = progress_dialog

        worker_kwargs = {}
        if self._source_exporter is not None:
            worker_kwargs["exporter"] = self._source_exporter
        worker = ExportWorker(source, request, **worker_kwargs)
        worker.setParent(self)
        worker.progress.connect(self._on_export_progress)
        worker.succeeded.connect(self._on_export_succeeded)
        worker.failed.connect(self._on_export_failed)
        worker.finished.connect(self._on_export_worker_finished)
        worker.finished.connect(self._cleanup_export_thread)
        worker.finished.connect(worker.deleteLater)
        self._export_job = _ExportJob(worker=worker)
        self._export_active = True
        self._update_actions()
        progress_dialog.show()
        worker.start()

    def cancel_export(self) -> None:
        job = self._export_job
        if job is None or not self._export_active:
            return
        job.worker.cancel()
        if self.export_progress_dialog is not None:
            self.export_progress_dialog.setLabelText(
                "Cancelling after the current slice..."
            )

    @Slot(object)
    def _on_export_progress(self, progress) -> None:
        if self._closing:
            return
        dialog = self.export_progress_dialog
        if dialog is not None:
            dialog.setMaximum(progress.total)
            dialog.setValue(progress.completed)
            dialog.setLabelText(
                f"Exported {progress.completed} / {progress.total} — "
                f"slice {progress.slice_index}"
            )
        self.export_progressed.emit(progress)

    @Slot(object)
    def _on_export_succeeded(self, result: ExportResult) -> None:
        self.last_export_result = result
        self.export_completed.emit(result)
        if self._closing:
            return
        total = (
            len(self._active_export_request.slice_indices)
            if self._active_export_request
            else 0
        )
        if result.cancelled:
            QMessageBox.information(
                self,
                "Export Cancelled",
                f"Export cancelled after {len(result.output_paths)} / {total} "
                "files. Completed files remain valid.",
            )
        else:
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(result.output_paths)} file(s) successfully.",
            )

    @Slot(str)
    def _on_export_failed(self, message: str) -> None:
        self.last_export_error = str(message)
        self.export_failed.emit(self.last_export_error)
        if not self._closing:
            self._present_error(self.last_export_error)

    @Slot()
    def _on_export_worker_finished(self) -> None:
        self._export_active = False
        dialog = self.export_progress_dialog
        self.export_progress_dialog = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
        self._active_export_request = None
        if not self._closing:
            self._update_actions()

    @Slot()
    def _cleanup_export_thread(self) -> None:
        self._export_job = None

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
        operation_active = self._busy or self._export_active
        self.open_action.setEnabled(not operation_active)
        self.close_action.setEnabled(has_source and not operation_active)
        self.fit_action.setEnabled(has_source)
        self.actual_pixels_action.setEnabled(has_source)
        self.reset_view_action.setEnabled(has_source)
        crop_enabled = has_source and not operation_active
        self.clear_crop_action.setEnabled(crop_enabled and self.current_crop is not None)
        self.image_view.set_crop_enabled(crop_enabled)
        self.crop_controls.setEnabled(crop_enabled)
        self.crop_controls.export_button.setEnabled(
            crop_enabled and self.current_crop is not None
        )
        self.crop_controls.setVisible(has_source)
        self.stack_controls.setEnabled(has_source and not operation_active)
        self.crop_status_label.setVisible(has_source)
        self.zoom_status_label.setVisible(has_source)
        self.export_action.setEnabled(
            has_source and self.current_crop is not None and not operation_active
        )
        if self.current_crop is None:
            self.export_action.setToolTip("Select a crop before exporting")
        else:
            self.export_action.setToolTip("Export the selected crop")

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
            if job.worker.isRunning():
                job.worker.wait()
        export_job = self._export_job
        if export_job is not None:
            export_job.worker.cancel()
            if export_job.worker.isRunning():
                export_job.worker.wait()
        # Deliver any source result queued immediately before shutdown; the
        # closing guard makes its handler close that source instead of adopting it.
        QCoreApplication.processEvents()
        self._jobs.clear()
        self.document.close()
        super().closeEvent(event)
