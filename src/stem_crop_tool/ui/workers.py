"""Qt worker adapters for operations that must not block the GUI thread."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Signal

from stem_crop_tool.core.batch import CancellationToken, ExportProgress
from stem_crop_tool.core.exceptions import DatasetSelectionRequiredError, STEMCropError
from stem_crop_tool.core.models import ExportRequest, ExportResult
from stem_crop_tool.core.readers.base import ImageSource
from stem_crop_tool.core.readers.dm import DMDatasetInfo, list_dm_datasets
from stem_crop_tool.infrastructure.exporters import export_source
from stem_crop_tool.infrastructure.source_loader import open_image_source


LOGGER = logging.getLogger(__name__)

SourceOpener = Callable[..., ImageSource]
DatasetLister = Callable[[str | Path], tuple[DMDatasetInfo, ...]]
ExportFunction = Callable[..., ExportResult]


class OpenSourceWorker(QThread):
    """Open one image source and transfer ownership to the GUI on success."""

    opened = Signal(int, object)
    selection_required = Signal(int, str, object)
    failed = Signal(int, str)
    def __init__(
        self,
        request_id: int,
        path: str | Path,
        *,
        dataset_index: int | None = None,
        opener: SourceOpener = open_image_source,
        dataset_lister: DatasetLister = list_dm_datasets,
    ) -> None:
        super().__init__()
        self.request_id = int(request_id)
        self.path = Path(path)
        self.dataset_index = dataset_index
        self._opener = opener
        self._dataset_lister = dataset_lister
        self._cancelled = Event()

    def cancel(self) -> None:
        """Request that any newly opened resource be closed instead of emitted."""

        self._cancelled.set()

    def run(self) -> None:
        source: ImageSource | None = None
        try:
            if self._cancelled.is_set():
                return
            source = self._opener(self.path, dataset_index=self.dataset_index)
            if self._cancelled.is_set():
                source.close()
                source = None
                return
            self.opened.emit(self.request_id, source)
            source = None
        except DatasetSelectionRequiredError:
            if self._cancelled.is_set():
                return
            try:
                infos = tuple(
                    info for info in self._dataset_lister(self.path) if info.supported
                )
            except STEMCropError as exc:
                self.failed.emit(self.request_id, str(exc))
            except Exception:
                LOGGER.exception("Unexpected failure while listing DM datasets")
                self.failed.emit(
                    self.request_id,
                    f"Could not inspect DM datasets in '{self.path.name}'.",
                )
            else:
                if self._cancelled.is_set():
                    return
                self.selection_required.emit(
                    self.request_id,
                    str(self.path),
                    infos,
                )
        except STEMCropError as exc:
            if not self._cancelled.is_set():
                self.failed.emit(self.request_id, str(exc))
        except Exception:
            LOGGER.exception("Unexpected failure while opening %s", self.path)
            if not self._cancelled.is_set():
                self.failed.emit(
                    self.request_id,
                    f"Could not open '{self.path.name}'. See the application log for details.",
                )
        finally:
            if source is not None:
                source.close()


class ExportWorker(QThread):
    """Run one immutable export request with cooperative cancellation."""

    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        source: ImageSource,
        request: ExportRequest,
        *,
        exporter: ExportFunction = export_source,
    ) -> None:
        super().__init__()
        self.source = source
        self.request = request
        self._exporter = exporter
        self._cancellation = CancellationToken()

    def cancel(self) -> None:
        self._cancellation.cancel()

    def _report_progress(self, progress: ExportProgress) -> None:
        self.progress.emit(progress)

    def run(self) -> None:
        try:
            result = self._exporter(
                self.source,
                self.request,
                progress_callback=self._report_progress,
                cancellation_token=self._cancellation,
            )
        except STEMCropError as exc:
            self.failed.emit(str(exc))
        except Exception:
            LOGGER.exception("Unexpected failure while exporting crop")
            self.failed.emit(
                "The export failed unexpectedly. See the application log for details."
            )
        else:
            self.succeeded.emit(result)
