"""Streaming PNG/NPY export engine and metadata sidecar writer."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage, QImageWriter

from stem_crop_tool.core.batch import (
    CancellationToken,
    ExportProgress,
    batch_item_filename,
)
from stem_crop_tool.core.crop import crop_array, validate_rect_within
from stem_crop_tool.core.dtypes import output_dtype_for
from stem_crop_tool.core.exceptions import ExportValidationError, ExportWriteError
from stem_crop_tool.core.metadata import (
    batch_manifest,
    output_record,
    single_sidecar,
)
from stem_crop_tool.core.models import (
    ExportFormat,
    ExportRequest,
    ExportResult,
    NormalizationMode,
)
from stem_crop_tool.core.normalize import normalize_local_minmax
from stem_crop_tool.core.readers.base import ImageSource, validate_slice_index
from stem_crop_tool.infrastructure.atomic_write import (
    atomic_output_path,
    ensure_paths_available,
    write_json_atomic,
)


ProgressCallback = Callable[[ExportProgress], None]


def single_sidecar_path(output_path: str | Path) -> Path:
    """Return the same-stem JSON path for one image output."""

    return Path(output_path).with_suffix(".json")


def batch_manifest_path(directory: str | Path) -> Path:
    """Return the batch-level manifest location."""

    return Path(directory) / "manifest.json"


def _prepare_output_array(
    crop: np.ndarray,
    output_format: ExportFormat,
    normalization: NormalizationMode,
) -> np.ndarray:
    target_dtype = output_dtype_for(crop.dtype, output_format, normalization)
    if normalization is NormalizationMode.LOCAL_MINMAX:
        normalized = normalize_local_minmax(crop)
        if output_format is ExportFormat.NPY:
            return normalized
        return np.rint(normalized * 255.0).astype(np.uint8)

    if output_format is ExportFormat.NPY:
        return crop
    return np.ascontiguousarray(crop, dtype=target_dtype)


def _encode_npy(path: Path, array: np.ndarray) -> None:
    try:
        with path.open("wb") as stream:
            np.save(stream, array, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ExportWriteError(f"could not write NPY output: {exc}") from exc


def _encode_png(path: Path, array: np.ndarray) -> None:
    contiguous = np.ascontiguousarray(array)
    height, width = contiguous.shape
    if contiguous.dtype == np.uint8:
        image_format = QImage.Format.Format_Grayscale8
    elif contiguous.dtype == np.uint16:
        image_format = QImage.Format.Format_Grayscale16
    else:
        raise ExportValidationError(
            f"PNG encoder received unsupported dtype {contiguous.dtype}"
        )

    image = QImage(
        contiguous.data,
        width,
        height,
        contiguous.strides[0],
        image_format,
    ).copy()
    writer = QImageWriter(str(path), b"png")
    if not writer.write(image):
        raise ExportWriteError(
            f"could not write PNG output: {writer.errorString()}"
        )


def _write_array_atomic(
    destination: Path,
    array: np.ndarray,
    output_format: ExportFormat,
    *,
    overwrite: bool,
) -> None:
    with atomic_output_path(destination, overwrite=overwrite) as temporary:
        if output_format is ExportFormat.NPY:
            _encode_npy(temporary, array)
        else:
            _encode_png(temporary, array)


def _validate_request(
    source: ImageSource,
    request: ExportRequest,
) -> tuple[int, ...]:
    validate_rect_within(
        request.crop,
        source.metadata.image_shape[1],
        source.metadata.image_shape[0],
    )
    indices = tuple(
        validate_slice_index(index, source.slice_count)
        for index in request.slice_indices
    )
    if source.ndim == 2 and indices != (0,):
        raise ExportValidationError("a 2D source can only export slice index 0")
    return indices


def _validate_single_destination(
    destination: Path,
    output_format: ExportFormat,
) -> None:
    expected_suffix = f".{output_format.value}"
    if destination.suffix.lower() != expected_suffix:
        raise ExportValidationError(
            f"single {output_format.value.upper()} export requires a "
            f"'{expected_suffix}' destination"
        )


def export_source(
    source: ImageSource,
    request: ExportRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> ExportResult:
    """Export selected crops without materializing a complete stack."""

    indices = _validate_request(source, request)
    output_format = request.output_format
    normalization = request.normalization
    cancellation = cancellation_token or CancellationToken()

    if len(indices) == 1:
        output_path = request.destination
        _validate_single_destination(output_path, output_format)
        sidecar_path = single_sidecar_path(output_path)
        ensure_paths_available(
            (output_path, sidecar_path),
            overwrite=request.overwrite,
        )
        if cancellation.is_cancelled:
            return ExportResult((), (), cancelled=True)

        index = indices[0]
        image = source.get_slice(index)
        prepared = _prepare_output_array(
            crop_array(image, request.crop),
            output_format,
            normalization,
        )
        _write_array_atomic(
            output_path,
            prepared,
            output_format,
            overwrite=request.overwrite,
        )
        record = output_record(
            output_path,
            output_format,
            tuple(int(size) for size in prepared.shape),
            prepared.dtype,
            slice_index=None if source.ndim == 2 else index,
        )
        write_json_atomic(
            sidecar_path,
            single_sidecar(
                source.metadata,
                request.crop,
                normalization,
                record,
            ),
            overwrite=request.overwrite,
        )
        if progress_callback is not None:
            progress_callback(ExportProgress(1, 1, index, output_path))
        return ExportResult((output_path,), (index,), cancelled=False)

    destination = request.destination
    if destination.exists() and not destination.is_dir():
        raise ExportValidationError(
            f"batch export destination is not a directory: {destination}"
        )
    output_paths = tuple(
        destination
        / batch_item_filename(source.metadata, index, output_format)
        for index in indices
    )
    manifest_path = batch_manifest_path(destination)
    ensure_paths_available(
        (*output_paths, manifest_path),
        overwrite=request.overwrite,
    )

    completed_paths: list[Path] = []
    completed_indices: list[int] = []
    records: list[dict[str, object]] = []
    total = len(indices)
    for index, output_path in zip(indices, output_paths, strict=True):
        if cancellation.is_cancelled:
            break
        image = source.get_slice(index)
        prepared = _prepare_output_array(
            crop_array(image, request.crop),
            output_format,
            normalization,
        )
        _write_array_atomic(
            output_path,
            prepared,
            output_format,
            overwrite=request.overwrite,
        )
        record = output_record(
            output_path,
            output_format,
            tuple(int(size) for size in prepared.shape),
            prepared.dtype,
            slice_index=index,
        )
        records.append(record)
        completed_paths.append(output_path)
        completed_indices.append(index)
        if progress_callback is not None:
            progress_callback(
                ExportProgress(len(completed_paths), total, index, output_path)
            )

    cancelled = cancellation.is_cancelled and len(completed_paths) < total
    write_json_atomic(
        manifest_path,
        batch_manifest(
            source.metadata,
            request.crop,
            normalization,
            indices,
            records,
            cancelled=cancelled,
        ),
        overwrite=request.overwrite,
    )
    return ExportResult(
        tuple(completed_paths),
        tuple(completed_indices),
        cancelled=cancelled,
    )
