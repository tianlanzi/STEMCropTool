from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

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
from stem_crop_tool.ui.main_window import MainWindow


TEST_DATA_ENV = "STEM_CROP_TOOL_TEST_DATA"
MANIFEST_PATH = (
    Path(__file__).parents[1] / "fixtures" / "external" / "manifest.json"
)


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _external_root() -> Path:
    raw_root = os.environ.get(TEST_DATA_ENV)
    if not raw_root:
        pytest.skip(f"set {TEST_DATA_ENV} to run external real-data tests")
    root = Path(raw_root)
    if not root.is_dir():
        pytest.skip(f"external test-data directory does not exist: {root}")
    return root


def _fixture(kind: str) -> dict[str, object]:
    matches = [
        entry
        for entry in _manifest()["fixtures"]
        if entry["kind"] == kind
    ]
    assert len(matches) == 1
    return matches[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_samples(array: np.ndarray, fixture: dict[str, object]) -> None:
    for sample in fixture["samples"]:
        index = tuple(int(value) for value in sample["index"])
        np.testing.assert_allclose(array[index], sample["value"], rtol=0, atol=0)


def test_external_fixture_inventory_matches_recorded_identity() -> None:
    root = _external_root()
    manifest = _manifest()

    assert manifest["schema_version"] == 1
    for fixture in manifest["fixtures"]:
        path = root / fixture["filename"]
        assert path.is_file(), f"missing recorded external fixture: {path.name}"
        assert path.stat().st_size == fixture["size_bytes"]
        assert _sha256(path) == fixture["sha256"]


def test_real_npy_image_and_stack_match_recorded_values() -> None:
    root = _external_root()
    for kind in ("npy_image", "npy_stack"):
        fixture = _fixture(kind)
        with NpyImageSource(root / fixture["filename"]) as source:
            assert isinstance(source._array, np.memmap)
            assert source.shape == tuple(fixture["shape"])
            assert source.dtype == np.dtype(fixture["dtype"])
            array = source._array
            assert array is not None
            _assert_samples(array, fixture)


def test_real_npy_stack_batch_crop_is_ordered_and_exact(tmp_path) -> None:
    root = _external_root()
    fixture = _fixture("npy_stack")
    source_path = root / fixture["filename"]
    destination = tmp_path / "batch"
    crop = CropRect(100, 120, 64, 80)

    with NpyImageSource(source_path) as source:
        request = ExportRequest(
            destination=destination,
            crop=crop,
            output_format=ExportFormat.NPY,
            normalization=NormalizationMode.NONE,
            slice_indices=all_slice_indices(source.slice_count),
            overwrite=False,
        )
        result = export_source(source, request)
        assert result.completed_slice_indices == tuple(range(8))
        assert len(result.output_paths) == 8
        for index, output_path in enumerate(result.output_paths):
            actual = np.load(output_path, allow_pickle=False)
            expected = source.get_slice(index)[120:200, 100:164]
            np.testing.assert_array_equal(actual, expected)

    payload = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert payload["completed_slice_indices"] == list(range(8))
    assert payload["cancelled"] is False


def test_real_dm3_and_dm4_match_motif_learn_reference() -> None:
    root = _external_root()
    dm_fixtures = [
        fixture
        for fixture in _manifest()["fixtures"]
        if fixture["kind"] == "dm_image"
    ]
    assert {Path(item["filename"]).suffix.lower() for item in dm_fixtures} == {
        ".dm3",
        ".dm4",
    }

    for fixture in dm_fixtures:
        path = root / fixture["filename"]
        infos = list_dm_datasets(path)
        selected = next(
            info for info in infos if info.index == fixture["dataset_index"]
        )
        assert selected.supported
        assert selected.shape == tuple(fixture["shape"])
        assert selected.dtype == np.dtype(fixture["dtype"])

        with DMImageSource(path, dataset_index=selected.index) as source:
            assert isinstance(source._array, np.memmap)
            assert source.shape == tuple(fixture["shape"])
            assert source.dtype == np.dtype(fixture["dtype"])
            np.testing.assert_allclose(
                source.metadata.pixel_size_xy,
                fixture["pixel_size_xy"],
                rtol=0,
                atol=0,
            )
            assert source.metadata.pixel_unit_xy == tuple(
                fixture["pixel_unit_xy"]
            )
            _assert_samples(source.get_slice(0), fixture)


def test_real_dm3_and_dm4_open_in_gui(qtbot) -> None:
    root = _external_root()
    dm_fixtures = [
        fixture
        for fixture in _manifest()["fixtures"]
        if fixture["kind"] == "dm_image"
    ]

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    for fixture in dm_fixtures:
        path = root / fixture["filename"]
        window.open_path(path, dataset_index=int(fixture["dataset_index"]))
        qtbot.waitUntil(lambda: not window.is_loading, timeout=10000)
        qtbot.waitUntil(lambda: window.loading_job_count == 0, timeout=10000)
        assert window.current_source is not None
        assert window.current_source.metadata.source_name == path.name
        assert window.image_view.source_index == 0
