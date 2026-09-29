"""Input-format dispatch without exposing adapter details to the UI."""

from __future__ import annotations

from pathlib import Path

from stem_crop_tool.core.exceptions import UnsupportedFileFormatError
from stem_crop_tool.core.readers.base import ImageSource
from stem_crop_tool.core.readers.dm import DMImageSource
from stem_crop_tool.core.readers.npy import NpyImageSource
from stem_crop_tool.infrastructure.raster_io import RasterImageSource


SUPPORTED_INPUT_EXTENSIONS = frozenset(
    {".npy", ".png", ".jpg", ".jpeg", ".dm3", ".dm4"}
)


def open_image_source(
    path: str | Path,
    *,
    dataset_index: int | None = None,
) -> ImageSource:
    """Open a supported path through the appropriate source adapter."""

    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == ".npy":
        if dataset_index is not None:
            raise ValueError("dataset_index is only valid for DM files")
        return NpyImageSource(source_path)
    if suffix in {".png", ".jpg", ".jpeg"}:
        if dataset_index is not None:
            raise ValueError("dataset_index is only valid for DM files")
        return RasterImageSource(source_path)
    if suffix in {".dm3", ".dm4"}:
        return DMImageSource(source_path, dataset_index=dataset_index)
    raise UnsupportedFileFormatError(
        f"unsupported input format '{suffix or '<none>'}' for '{source_path.name}'"
    )
