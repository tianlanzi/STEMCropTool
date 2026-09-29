import numpy as np

from stem_crop_tool.core.metadata import (
    batch_manifest,
    output_record,
    single_sidecar,
)
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ImageMetadata,
    NormalizationMode,
)


def test_single_metadata_uses_filenames_and_physical_xy_size(tmp_path) -> None:
    metadata = ImageMetadata(
        str(tmp_path / "private" / "folder" / "sample.dm4"),
        "dm4",
        (8, 100, 200),
        np.uint32,
        dataset_index=2,
        pixel_size_xy=(0.02, 0.03),
        pixel_unit_xy=("nm", "nm"),
    )
    crop = CropRect(4, 5, 10, 20)
    output = output_record(
        tmp_path / "exports" / "crop.npy",
        ExportFormat.NPY,
        (20, 10),
        np.uint32,
        slice_index=3,
    )

    payload = single_sidecar(
        metadata,
        crop,
        NormalizationMode.NONE,
        output,
    )

    assert payload["source"]["filename"] == "sample.dm4"
    assert "private" not in str(payload)
    assert payload["output"]["filename"] == "crop.npy"
    assert payload["spatial_calibration"]["physical_crop_size_xy"] == [
        0.2,
        0.6,
    ]


def test_batch_metadata_uses_null_unknown_calibration() -> None:
    metadata = ImageMetadata("stack.npy", "npy", (3, 4, 5), np.float32)
    output = output_record(
        "stack_z0001_crop.npy",
        ExportFormat.NPY,
        (2, 2),
        np.float32,
        slice_index=1,
    )

    payload = batch_manifest(
        metadata,
        CropRect(0, 0, 2, 2),
        NormalizationMode.LOCAL_MINMAX,
        (0, 1, 2),
        (output,),
        cancelled=True,
    )

    assert payload["requested_slice_indices"] == [0, 1, 2]
    assert payload["completed_slice_indices"] == [1]
    assert payload["cancelled"] is True
    assert payload["spatial_calibration"] == {
        "pixel_size_xy": None,
        "pixel_unit_xy": None,
        "physical_crop_size_xy": None,
    }
