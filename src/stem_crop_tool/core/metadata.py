"""Deterministic JSON-ready metadata for single and batch exports."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ImageMetadata,
    NormalizationMode,
)


SCHEMA_VERSION = 1


def _source_record(metadata: ImageMetadata) -> dict[str, Any]:
    return {
        "filename": Path(metadata.source_name).name,
        "format": metadata.source_format,
        "shape": list(metadata.shape),
        "dtype": str(metadata.dtype),
        "dataset_index": metadata.dataset_index,
    }


def _crop_record(crop: CropRect) -> dict[str, int]:
    return {
        "x": crop.x,
        "y": crop.y,
        "width": crop.width,
        "height": crop.height,
    }


def _spatial_record(
    metadata: ImageMetadata,
    crop: CropRect,
) -> dict[str, list[float] | list[str] | None]:
    sizes = metadata.pixel_size_xy
    units = metadata.pixel_unit_xy
    physical_size: list[float] | None = None
    if sizes is not None and units is not None:
        physical_size = [crop.width * sizes[0], crop.height * sizes[1]]
    return {
        "pixel_size_xy": list(sizes) if sizes is not None else None,
        "pixel_unit_xy": list(units) if units is not None else None,
        "physical_crop_size_xy": physical_size,
    }


def output_record(
    output_path: str | Path,
    output_format: ExportFormat,
    shape: tuple[int, int],
    dtype: np.dtype,
    *,
    slice_index: int | None,
) -> dict[str, Any]:
    """Return a path-safe record describing one committed image output."""

    return {
        "filename": Path(output_path).name,
        "format": ExportFormat(output_format).value,
        "shape": list(shape),
        "dtype": str(np.dtype(dtype)),
        "slice_index": slice_index,
    }


def single_sidecar(
    metadata: ImageMetadata,
    crop: CropRect,
    normalization: NormalizationMode,
    output: dict[str, Any],
) -> dict[str, Any]:
    """Build metadata for one exported crop."""

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "single",
        "source": _source_record(metadata),
        "slice_index": output["slice_index"],
        "crop": _crop_record(crop),
        "normalization": NormalizationMode(normalization).value,
        "output": output,
        "spatial_calibration": _spatial_record(metadata, crop),
    }


def batch_manifest(
    metadata: ImageMetadata,
    crop: CropRect,
    normalization: NormalizationMode,
    requested_slice_indices: Sequence[int],
    outputs: Sequence[dict[str, Any]],
    *,
    cancelled: bool,
) -> dict[str, Any]:
    """Build one batch-level manifest for completed slice outputs."""

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "batch",
        "source": _source_record(metadata),
        "requested_slice_indices": list(requested_slice_indices),
        "completed_slice_indices": [item["slice_index"] for item in outputs],
        "cancelled": bool(cancelled),
        "crop": _crop_record(crop),
        "normalization": NormalizationMode(normalization).value,
        "outputs": list(outputs),
        "spatial_calibration": _spatial_record(metadata, crop),
    }
