from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import stem_crop_tool.infrastructure.exporters as exporters
from stem_crop_tool.core.batch import CancellationToken, inclusive_slice_range
from stem_crop_tool.core.exceptions import (
    OutputExistsError,
    UnsupportedDTypeError,
)
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    ImageMetadata,
    NormalizationMode,
)
from stem_crop_tool.infrastructure.exporters import export_source
from stem_crop_tool.infrastructure.raster_io import RasterImageSource


class ArraySource:
    def __init__(
        self,
        array: np.ndarray,
        *,
        source_name: str = "source.npy",
        pixel_size_xy: tuple[float, float] | None = None,
        pixel_unit_xy: tuple[str, str] | None = None,
    ) -> None:
        self.array = array
        self.shape = array.shape
        self.dtype = array.dtype
        self.ndim = array.ndim
        self.slice_count = array.shape[0] if array.ndim == 3 else 1
        self.metadata = ImageMetadata(
            source_name,
            Path(source_name).suffix.lstrip(".") or "npy",
            array.shape,
            array.dtype,
            pixel_size_xy=pixel_size_xy,
            pixel_unit_xy=pixel_unit_xy,
        )
        self.requested: list[int] = []

    def get_slice(self, index: int = 0) -> np.ndarray:
        self.requested.append(index)
        return self.array if self.ndim == 2 else self.array[index]

    def close(self) -> None:
        pass


def _request(
    destination: Path,
    *,
    output_format: ExportFormat,
    crop: CropRect = CropRect(1, 1, 2, 2),
    normalization: NormalizationMode = NormalizationMode.NONE,
    slice_indices: tuple[int, ...] = (0,),
    overwrite: bool = False,
) -> ExportRequest:
    return ExportRequest(
        destination=destination,
        crop=crop,
        output_format=output_format,
        normalization=normalization,
        slice_indices=slice_indices,
        overwrite=overwrite,
    )


def test_raw_npy_export_preserves_exact_crop_dtype_and_values(tmp_path) -> None:
    data = np.arange(30, dtype=np.int16).reshape(5, 6)
    source = ArraySource(data)
    destination = tmp_path / "crop.npy"

    result = export_source(
        source,
        _request(destination, output_format=ExportFormat.NPY),
    )

    actual = np.load(destination, allow_pickle=False)
    np.testing.assert_array_equal(actual, data[1:3, 1:3])
    assert actual.dtype == data.dtype
    assert result.output_paths == (destination,)
    sidecar = json.loads((tmp_path / "crop.json").read_text(encoding="utf-8"))
    assert sidecar["source"]["filename"] == "source.npy"
    assert sidecar["slice_index"] is None
    assert sidecar["output"]["dtype"] == "int16"


def test_normalized_npy_is_independent_float32_local_minmax(tmp_path) -> None:
    data = np.array(
        [[100.0, 100.0, 100.0], [-5.0, 0.0, 5.0], [9.0, 9.0, 9.0]],
        dtype=np.float64,
    )
    source = ArraySource(data)
    destination = tmp_path / "normalized.npy"

    export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.NPY,
            crop=CropRect(0, 1, 3, 1),
            normalization=NormalizationMode.LOCAL_MINMAX,
        ),
    )

    actual = np.load(destination, allow_pickle=False)
    np.testing.assert_array_equal(actual, [[0.0, 0.5, 1.0]])
    assert actual.dtype == np.float32
    assert data[1].tolist() == [-5.0, 0.0, 5.0]


def test_raw_npy_preserves_non_native_endian_dtype(tmp_path) -> None:
    data = np.arange(12, dtype=">u2").reshape(3, 4)
    source = ArraySource(data)
    destination = tmp_path / "big_endian.npy"

    export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.NPY,
            crop=CropRect(0, 0, 4, 3),
        ),
    )

    actual = np.load(destination, allow_pickle=False)
    np.testing.assert_array_equal(actual, data)
    assert actual.dtype == data.dtype


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_raw_png_round_trip_preserves_values_and_bit_depth(tmp_path, dtype) -> None:
    if dtype == np.uint8:
        data = np.array(
            [[0, 1, 2, 3], [4, 127, 255, 8], [9, 16, 64, 254]],
            dtype=dtype,
        )
    else:
        data = np.array(
            [[0, 1, 2, 3], [4, 127, 255, 8], [9, 256, 1024, 65535]],
            dtype=dtype,
        )
    source = ArraySource(data)
    destination = tmp_path / "crop.png"

    export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.PNG,
            crop=CropRect(0, 0, 4, 3),
        ),
    )

    with RasterImageSource(destination) as exported:
        np.testing.assert_array_equal(exported.get_slice(), data)
        assert exported.dtype == np.dtype(dtype)


def test_normalized_png_uses_rounded_uint8_range(tmp_path) -> None:
    data = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
    source = ArraySource(data)
    destination = tmp_path / "normalized.png"

    export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.PNG,
            crop=CropRect(0, 0, 3, 1),
            normalization=NormalizationMode.LOCAL_MINMAX,
        ),
    )

    with RasterImageSource(destination) as exported:
        np.testing.assert_array_equal(
            exported.get_slice(),
            np.array([[0, 128, 255]], dtype=np.uint8),
        )


def test_raw_png_preserves_big_endian_uint16_values(tmp_path) -> None:
    data = np.array([[1, 256], [1024, 65535]], dtype=">u2")
    source = ArraySource(data)
    destination = tmp_path / "big_endian.png"

    export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.PNG,
            crop=CropRect(0, 0, 2, 2),
        ),
    )

    with RasterImageSource(destination) as exported:
        np.testing.assert_array_equal(
            exported.get_slice(), data.astype(np.uint16)
        )
        assert exported.dtype == np.dtype(np.uint16)


def test_raw_float_png_is_rejected_without_creating_files(tmp_path) -> None:
    source = ArraySource(np.ones((3, 3), dtype=np.float32))
    destination = tmp_path / "crop.png"

    with pytest.raises(UnsupportedDTypeError, match="enable normalization"):
        export_source(
            source,
            _request(destination, output_format=ExportFormat.PNG),
        )

    assert not destination.exists()
    assert not (tmp_path / "crop.json").exists()


def test_single_sidecar_records_physical_size_without_absolute_paths(tmp_path) -> None:
    source = ArraySource(
        np.arange(30, dtype=np.uint16).reshape(5, 6),
        source_name=str(tmp_path / "private" / "sample.dm4"),
        pixel_size_xy=(0.2, 0.5),
        pixel_unit_xy=("nm", "nm"),
    )
    destination = tmp_path / "crop.npy"

    export_source(
        source,
        _request(destination, output_format=ExportFormat.NPY),
    )

    payload = json.loads((tmp_path / "crop.json").read_text(encoding="utf-8"))
    assert payload["source"]["filename"] == "sample.dm4"
    assert "private" not in json.dumps(payload)
    assert payload["spatial_calibration"]["physical_crop_size_xy"] == [
        0.4,
        1.0,
    ]


def test_batch_range_streams_in_order_and_writes_one_manifest(tmp_path) -> None:
    stack = np.arange(5 * 4 * 6, dtype=np.uint16).reshape(5, 4, 6)
    source = ArraySource(stack, source_name="stack.npy")
    destination = tmp_path / "batch"
    progress = []

    result = export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.NPY,
            slice_indices=inclusive_slice_range(1, 3, source.slice_count),
        ),
        progress_callback=progress.append,
    )

    expected_names = [
        "stack_z0001_crop.npy",
        "stack_z0002_crop.npy",
        "stack_z0003_crop.npy",
    ]
    assert [path.name for path in result.output_paths] == expected_names
    assert source.requested == [1, 2, 3]
    assert [item.completed for item in progress] == [1, 2, 3]
    for index, name in zip((1, 2, 3), expected_names, strict=True):
        np.testing.assert_array_equal(
            np.load(destination / name, allow_pickle=False),
            stack[index, 1:3, 1:3],
        )
    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["requested_slice_indices"] == [1, 2, 3]
    assert manifest["completed_slice_indices"] == [1, 2, 3]
    assert manifest["cancelled"] is False
    assert [item["filename"] for item in manifest["outputs"]] == expected_names


def test_batch_cancellation_keeps_completed_output_and_records_manifest(tmp_path) -> None:
    stack = np.arange(4 * 3 * 3, dtype=np.uint8).reshape(4, 3, 3)
    source = ArraySource(stack, source_name="stack.npy")
    destination = tmp_path / "batch"
    token = CancellationToken()

    def cancel_after_first(progress) -> None:
        if progress.completed == 1:
            token.cancel()

    result = export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.NPY,
            crop=CropRect(0, 0, 2, 2),
            slice_indices=(0, 1, 2, 3),
        ),
        progress_callback=cancel_after_first,
        cancellation_token=token,
    )

    assert result.cancelled is True
    assert result.completed_slice_indices == (0,)
    assert source.requested == [0]
    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["cancelled"] is True
    assert manifest["completed_slice_indices"] == [0]
    assert list(destination.glob(".*.tmp")) == []


def test_batch_normalizes_each_crop_independently(tmp_path) -> None:
    stack = np.array(
        [
            [[0.0, 5.0, 10.0]],
            [[100.0, 150.0, 200.0]],
        ],
        dtype=np.float32,
    )
    source = ArraySource(stack, source_name="stack.npy")
    destination = tmp_path / "batch"

    result = export_source(
        source,
        _request(
            destination,
            output_format=ExportFormat.NPY,
            crop=CropRect(0, 0, 3, 1),
            normalization=NormalizationMode.LOCAL_MINMAX,
            slice_indices=(0, 1),
        ),
    )

    for output_path in result.output_paths:
        np.testing.assert_array_equal(
            np.load(output_path, allow_pickle=False),
            np.array([[0.0, 0.5, 1.0]], dtype=np.float32),
        )


def test_existing_batch_target_blocks_before_any_output_is_written(tmp_path) -> None:
    stack = np.zeros((3, 3, 3), dtype=np.uint8)
    source = ArraySource(stack, source_name="stack.npy")
    destination = tmp_path / "batch"
    destination.mkdir()
    conflict = destination / "stack_z0001_crop.npy"
    conflict.write_bytes(b"existing")

    with pytest.raises(OutputExistsError):
        export_source(
            source,
            _request(
                destination,
                output_format=ExportFormat.NPY,
                slice_indices=(0, 1),
            ),
        )

    assert source.requested == []
    assert conflict.read_bytes() == b"existing"
    assert not (destination / "stack_z0000_crop.npy").exists()


def test_existing_single_sidecar_blocks_before_image_write(tmp_path) -> None:
    source = ArraySource(np.arange(9, dtype=np.uint8).reshape(3, 3))
    destination = tmp_path / "crop.npy"
    sidecar = tmp_path / "crop.json"
    sidecar.write_text("existing", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        export_source(
            source,
            _request(destination, output_format=ExportFormat.NPY),
        )

    assert source.requested == []
    assert not destination.exists()
    assert sidecar.read_text(encoding="utf-8") == "existing"


def test_simulated_encoder_failure_removes_partial_temporary_file(
    tmp_path, monkeypatch
) -> None:
    source = ArraySource(np.arange(9, dtype=np.uint8).reshape(3, 3))
    destination = tmp_path / "crop.npy"

    def fail(path: Path, _: np.ndarray) -> None:
        path.write_bytes(b"partial")
        raise RuntimeError("simulated encoder failure")

    monkeypatch.setattr(exporters, "_encode_npy", fail)
    with pytest.raises(RuntimeError, match="simulated encoder"):
        export_source(
            source,
            _request(destination, output_format=ExportFormat.NPY),
        )

    assert not destination.exists()
    assert not (tmp_path / "crop.json").exists()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_mid_batch_failure_keeps_completed_files_and_removes_partial_one(
    tmp_path, monkeypatch
) -> None:
    stack = np.arange(3 * 3 * 3, dtype=np.uint8).reshape(3, 3, 3)
    source = ArraySource(stack, source_name="stack.npy")
    destination = tmp_path / "batch"
    original = exporters._encode_npy
    calls = 0

    def fail_second(path: Path, array: np.ndarray) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            path.write_bytes(b"partial")
            raise RuntimeError("simulated second-slice failure")
        original(path, array)

    monkeypatch.setattr(exporters, "_encode_npy", fail_second)
    with pytest.raises(RuntimeError, match="second-slice"):
        export_source(
            source,
            _request(
                destination,
                output_format=ExportFormat.NPY,
                slice_indices=(0, 1, 2),
            ),
        )

    assert (destination / "stack_z0000_crop.npy").is_file()
    assert not (destination / "stack_z0001_crop.npy").exists()
    assert not (destination / "manifest.json").exists()
    assert list(destination.glob(".*.tmp")) == []
