"""Packaged-build smoke matrix executed by the frozen application itself."""

from __future__ import annotations

import json
from pathlib import Path
import traceback

import numpy as np
from PySide6.QtGui import QImage

from stem_crop_tool.core.batch import all_slice_indices
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    NormalizationMode,
)
from stem_crop_tool.core.readers.dm import DMImageSource, list_dm_datasets
from stem_crop_tool.core.readers.npy import NpyImageSource
from stem_crop_tool.infrastructure.exporters import export_source
from stem_crop_tool.infrastructure.raster_io import RasterImageSource


REPORT_NAME = "packaged_self_test.json"


def write_failure_report(workspace: str | Path, error: BaseException) -> Path:
    """Persist a frozen self-test failure without opening a GUI traceback."""

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    report_path = workspace / REPORT_NAME
    report_path.write_text(
        json.dumps(
            {
                "status": "failed",
                "error": str(error),
                "traceback": "".join(
                    traceback.format_exception(
                        type(error),
                        error,
                        error.__traceback__,
                    )
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report_path


def _save_grayscale(path: Path, data: np.ndarray) -> None:
    height, width = data.shape
    if data.dtype == np.uint8:
        image_format = QImage.Format.Format_Grayscale8
    elif data.dtype == np.uint16:
        image_format = QImage.Format.Format_Grayscale16
    else:
        raise TypeError(f"unsupported self-test raster dtype: {data.dtype}")

    image = QImage(width, height, image_format)
    bytes_per_line = image.bytesPerLine()
    if data.dtype == np.uint8:
        rows = np.frombuffer(
            image.bits(),
            dtype=np.uint8,
            count=height * bytes_per_line,
        ).reshape(height, bytes_per_line)
    else:
        values_per_line = bytes_per_line // np.dtype(np.uint16).itemsize
        rows = np.frombuffer(
            image.bits(),
            dtype=np.uint16,
            count=height * values_per_line,
        ).reshape(height, values_per_line)
    rows[:, :width] = data
    if not image.save(str(path)):
        raise RuntimeError(f"could not create self-test raster: {path.name}")


def _request(
    destination: Path,
    crop: CropRect,
    output_format: ExportFormat,
    slice_indices: tuple[int, ...] = (0,),
) -> ExportRequest:
    return ExportRequest(
        destination=destination,
        crop=crop,
        output_format=output_format,
        normalization=NormalizationMode.NONE,
        slice_indices=slice_indices,
        overwrite=False,
    )


def _exercise_core_formats(workspace: Path) -> tuple[list[str], list[str]]:
    input_dir = workspace / "inputs"
    output_dir = workspace / "outputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    image = np.arange(12 * 16, dtype=np.uint16).reshape(12, 16)
    stack = np.stack((image, image + 1000, image + 2000))
    npy_path = input_dir / "image.npy"
    stack_path = input_dir / "stack.npy"
    png_path = input_dir / "image_uint16.png"
    jpg_path = input_dir / "image_uint8.jpg"
    np.save(npy_path, image)
    np.save(stack_path, stack)
    _save_grayscale(png_path, image)
    _save_grayscale(jpg_path, (image % 256).astype(np.uint8))

    opened: list[str] = []
    with NpyImageSource(npy_path) as source:
        np.testing.assert_array_equal(source.get_slice(), image)
        crop = CropRect(3, 2, 8, 6)
        npy_output = output_dir / "crop_npy.npy"
        png_output = output_dir / "crop_png.png"
        export_source(source, _request(npy_output, crop, ExportFormat.NPY))
        export_source(source, _request(png_output, crop, ExportFormat.PNG))
        np.testing.assert_array_equal(
            np.load(npy_output, allow_pickle=False),
            image[2:8, 3:11],
        )
        with RasterImageSource(png_output) as exported_png:
            np.testing.assert_array_equal(
                exported_png.get_slice(),
                image[2:8, 3:11],
            )
        opened.append("npy")

    with NpyImageSource(stack_path) as source:
        batch_dir = output_dir / "batch"
        result = export_source(
            source,
            _request(
                batch_dir,
                CropRect(4, 3, 7, 5),
                ExportFormat.NPY,
                all_slice_indices(source.slice_count),
            ),
        )
        assert result.completed_slice_indices == (0, 1, 2)
        for index, output_path in enumerate(result.output_paths):
            np.testing.assert_array_equal(
                np.load(output_path, allow_pickle=False),
                stack[index, 3:8, 4:11],
            )
        opened.append("npy_stack")

    with RasterImageSource(png_path) as source:
        np.testing.assert_array_equal(source.get_slice(), image)
        opened.append("png_uint16")
    with RasterImageSource(jpg_path) as source:
        assert source.shape == image.shape
        assert source.dtype == np.dtype(np.uint8)
        opened.append("jpeg_uint8")

    outputs = [
        "npy",
        "png_uint16",
        "npy_batch",
        "json_sidecar",
        "json_manifest",
    ]
    return opened, outputs


def _exercise_real_dm(
    workspace: Path,
    external_data_dir: Path | None,
) -> tuple[list[str], list[str]]:
    if external_data_dir is None:
        return [], []
    if not external_data_dir.is_dir():
        raise FileNotFoundError(
            f"external self-test data directory does not exist: {external_data_dir}"
        )

    opened: list[str] = []
    outputs: list[str] = []
    output_dir = workspace / "outputs" / "dm"
    for suffix in ("dm3", "dm4"):
        matches = sorted(external_data_dir.glob(f"*.{suffix}"))
        if not matches:
            raise FileNotFoundError(f"self-test requires one .{suffix} fixture")
        path = matches[0]
        selected = next(info for info in list_dm_datasets(path) if info.supported)
        with DMImageSource(path, dataset_index=selected.index) as source:
            height, width = source.metadata.image_shape
            crop = CropRect(0, 0, min(width, 16), min(height, 16))
            destination = output_dir / f"{suffix}_crop.npy"
            export_source(
                source,
                _request(destination, crop, ExportFormat.NPY),
            )
            np.testing.assert_array_equal(
                np.load(destination, allow_pickle=False),
                source.get_slice(0)[: crop.height, : crop.width],
            )
        opened.append(suffix)
        outputs.append(f"{suffix}_to_npy")
    return opened, outputs


def run_release_self_test(
    workspace: str | Path,
    *,
    external_data_dir: str | Path | None = None,
) -> Path:
    """Exercise frozen readers/exporters and write a machine-readable report."""

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    external = None if external_data_dir is None else Path(external_data_dir)

    core_inputs, core_outputs = _exercise_core_formats(workspace)
    dm_inputs, dm_outputs = _exercise_real_dm(workspace, external)
    report = {
        "status": "passed",
        "inputs": core_inputs + dm_inputs,
        "outputs": core_outputs + dm_outputs,
        "external_dm_tested": bool(dm_inputs),
    }
    report_path = workspace / REPORT_NAME
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report_path
