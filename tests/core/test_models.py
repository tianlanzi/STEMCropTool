from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from stem_crop_tool.core.exceptions import (
    InvalidCropRectError,
    UnsupportedArrayShapeError,
    UnsupportedDTypeError,
)
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    ExportResult,
    ImageMetadata,
    NormalizationMode,
)


def test_crop_rect_uses_half_open_bounds_and_is_immutable() -> None:
    rect = CropRect(x=3, y=4, width=5, height=6)

    assert rect.x1 == 8
    assert rect.y1 == 10
    assert rect.slices == (slice(4, 10), slice(3, 8))
    with pytest.raises(FrozenInstanceError):
        rect.x = 1


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-1, 2)])
def test_crop_rect_rejects_non_positive_size(width: int, height: int) -> None:
    with pytest.raises(InvalidCropRectError):
        CropRect(0, 0, width, height)


@pytest.mark.parametrize("value", [1.5, True, "1"])
def test_crop_rect_rejects_non_integer_coordinates(value: object) -> None:
    with pytest.raises(TypeError):
        CropRect(value, 0, 1, 1)


def test_image_metadata_describes_2d_and_3d_sources() -> None:
    image = ImageMetadata("image.npy", "NPY", (20, 30), np.uint16)
    stack = ImageMetadata("stack.dm4", "DM4", (7, 20, 30), "float32")

    assert image.source_format == "npy"
    assert image.slice_count == 1
    assert image.image_shape == (20, 30)
    assert image.dtype == np.dtype(np.uint16)
    assert stack.slice_count == 7
    assert stack.image_shape == (20, 30)


@pytest.mark.parametrize("shape", [(5,), (1, 2, 3, 4), (2, 0)])
def test_image_metadata_rejects_unsupported_shapes(shape: tuple[int, ...]) -> None:
    with pytest.raises(UnsupportedArrayShapeError):
        ImageMetadata("image.npy", "npy", shape, np.float32)


def test_image_metadata_rejects_complex_dtype() -> None:
    with pytest.raises(UnsupportedDTypeError):
        ImageMetadata("image.npy", "npy", (2, 2), np.complex64)


def test_image_metadata_validates_calibration() -> None:
    metadata = ImageMetadata(
        "image.dm4",
        "dm4",
        (10, 20),
        np.float32,
        pixel_size_xy=(0.02, 0.03),
        pixel_unit_xy=("nm", "nm"),
    )

    assert metadata.pixel_size_xy == (0.02, 0.03)
    with pytest.raises(ValueError):
        ImageMetadata(
            "image.dm4", "dm4", (10, 20), np.float32, pixel_size_xy=(0.02,)
        )


def test_export_request_coerces_stable_value_types() -> None:
    request = ExportRequest(
        destination="output",
        crop=CropRect(1, 2, 3, 4),
        output_format="npy",
        normalization="local_minmax",
        slice_indices=(1, 3, 5),
    )

    assert request.destination == Path("output")
    assert request.output_format is ExportFormat.NPY
    assert request.normalization is NormalizationMode.LOCAL_MINMAX
    assert request.slice_indices == (1, 3, 5)


@pytest.mark.parametrize("indices", [(), (2, 2), (2, 1), (-1,)])
def test_export_request_rejects_invalid_slice_indices(
    indices: tuple[int, ...],
) -> None:
    with pytest.raises(ValueError):
        ExportRequest(
            destination="output",
            crop=CropRect(0, 0, 1, 1),
            output_format=ExportFormat.NPY,
            slice_indices=indices,
        )


def test_export_result_requires_one_path_per_completed_slice() -> None:
    result = ExportResult(("a.npy", "b.npy"), (0, 1))

    assert result.output_paths == (Path("a.npy"), Path("b.npy"))
    with pytest.raises(ValueError):
        ExportResult(("a.npy",), (0, 1))
