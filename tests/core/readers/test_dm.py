from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import stem_crop_tool.core.readers.dm as dm_reader
from stem_crop_tool.core.exceptions import (
    DatasetSelectionRequiredError,
    NoSupportedDatasetError,
    SourceClosedError,
    SourceOpenError,
)
from stem_crop_tool.core.readers.dm import DMImageSource, list_dm_datasets
from stem_crop_tool.vendor.ncempy_dm import fileDM


class FakeDMReader:
    def __init__(
        self,
        path: Path,
        *,
        data_shapes: list[int],
        x_sizes: list[int],
        y_sizes: list[int],
        z_sizes: list[int],
        z2_sizes: list[int],
        data_types: list[int],
        thumbnail: bool = False,
    ) -> None:
        self.file_path = path
        self.dataShape = data_shapes
        self.xSize = x_sizes
        self.ySize = y_sizes
        self.zSize = z_sizes
        self.zSize2 = z2_sizes
        self.dataType = data_types
        self.numObjects = len(data_shapes)
        self.thumbnail = thumbnail
        self.scale = [1.5] * sum(data_shapes)
        self.scaleUnit = ["nm"] * sum(data_shapes)
        self.origin = [0.0] * sum(data_shapes)
        self.allTags = {"test.tag": 7}
        self.closed = False

    def _DM2NPDataType(self, code: int):
        return {6: np.uint8, 10: np.uint16, 11: np.uint32}[int(code)]

    def getMemmap(self, index: int) -> np.memmap:
        raw = index + int(self.thumbnail)
        ndim = self.dataShape[raw]
        if ndim == 2:
            shape = (self.ySize[raw], self.xSize[raw])
        elif ndim == 3:
            shape = (self.zSize[raw], self.ySize[raw], self.xSize[raw])
        else:
            shape = (
                self.zSize2[raw],
                self.zSize[raw],
                self.ySize[raw],
                self.xSize[raw],
            )
        return np.memmap(
            self.file_path,
            dtype=self._DM2NPDataType(self.dataType[raw]),
            mode="r",
            shape=shape,
        )

    def close(self) -> None:
        self.closed = True


def test_vendor_destructor_is_safe_without_a_file_handle() -> None:
    reader = object.__new__(fileDM)
    reader._v = False
    reader.close()
    reader.__del__()


def test_vendor_memmap_preserves_singleton_declared_4d_shape(tmp_path) -> None:
    path = tmp_path / "pixels.bin"
    np.arange(24, dtype=np.uint8).tofile(path)
    reader = object.__new__(fileDM)
    reader.file_path = path
    reader.numObjects = 1
    reader.thumbnail = False
    reader.dataShape = [4]
    reader.xSize = [4]
    reader.ySize = [3]
    reader.zSize = [2]
    reader.zSize2 = [1]
    reader.dataType = [6]
    reader.dataOffset = [0]
    reader._DM2NPDataTypes = {6: np.uint8}

    mapped = reader.getMemmap(0)
    try:
        assert mapped.shape == (1, 2, 3, 4)
    finally:
        mapped._mmap.close()


def test_vendor_dataset_indices_do_not_skip_non_thumbnail_data(tmp_path) -> None:
    path = tmp_path / "pixels.bin"
    np.arange(8, dtype=np.uint8).tofile(path)
    reader = object.__new__(fileDM)
    reader.file_path = path
    reader.numObjects = 2
    reader.thumbnail = False
    reader.dataShape = [2, 2]
    reader.xSize = [2, 2]
    reader.ySize = [2, 2]
    reader.zSize = [1, 1]
    reader.zSize2 = [1, 1]
    reader.dataType = [6, 6]
    reader.dataOffset = [0, 4]
    reader._DM2NPDataTypes = {6: np.uint8}

    first = reader.getMemmap(0)
    second = reader.getMemmap(1)
    try:
        np.testing.assert_array_equal(first, [[0, 1], [2, 3]])
        np.testing.assert_array_equal(second, [[4, 5], [6, 7]])
    finally:
        first._mmap.close()
        second._mmap.close()


def test_dm_enumeration_skips_thumbnail_and_keeps_4d_declaration(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "fake.dm4"
    path.write_bytes(b"unused")
    fake = FakeDMReader(
        path,
        data_shapes=[2, 4, 2],
        x_sizes=[64, 5, 7],
        y_sizes=[64, 4, 6],
        z_sizes=[1, 1, 1],
        z2_sizes=[1, 1, 1],
        data_types=[6, 6, 10],
        thumbnail=True,
    )
    monkeypatch.setattr(dm_reader, "_open_reader", lambda _: fake)

    infos = list_dm_datasets(path)

    assert [info.raw_index for info in infos] == [1, 2]
    assert infos[0].shape == (1, 1, 4, 5)
    assert not infos[0].supported
    assert "declared 4D" in (infos[0].unsupported_reason or "")
    assert infos[1].shape == (6, 7)
    assert infos[1].supported
    assert fake.closed


def test_dm_requires_selection_for_multiple_supported_datasets(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "multiple.dm3"
    path.write_bytes(np.zeros(32, dtype=np.uint8).tobytes())
    fake = FakeDMReader(
        path,
        data_shapes=[2, 2],
        x_sizes=[4, 4],
        y_sizes=[4, 4],
        z_sizes=[1, 1],
        z2_sizes=[1, 1],
        data_types=[6, 6],
    )
    monkeypatch.setattr(dm_reader, "_open_reader", lambda _: fake)

    with pytest.raises(DatasetSelectionRequiredError) as error:
        DMImageSource(path)

    assert error.value.dataset_indices == (0, 1)
    assert fake.closed


def test_dm_source_exposes_lazy_3d_slices_and_calibration(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "stack.dm4"
    expected = np.arange(24, dtype=np.uint16).reshape(2, 3, 4)
    expected.tofile(path)
    fake = FakeDMReader(
        path,
        data_shapes=[3],
        x_sizes=[4],
        y_sizes=[3],
        z_sizes=[2],
        z2_sizes=[1],
        data_types=[10],
    )
    monkeypatch.setattr(dm_reader, "_open_reader", lambda _: fake)

    source = DMImageSource(path)
    try:
        assert isinstance(source._array, np.memmap)
        assert source.shape == (2, 3, 4)
        assert source.slice_count == 2
        assert source.metadata.pixel_size_xy == (1.5, 1.5)
        assert source.metadata.pixel_unit_xy == ("nm", "nm")
        assert source.all_tags["test.tag"] == 7
        np.testing.assert_array_equal(source.get_slice(1), expected[1])
    finally:
        source.close()

    with pytest.raises(SourceClosedError):
        source.get_slice()


def test_dm_rejects_singleton_4d_dataset(tmp_path, monkeypatch) -> None:
    path = tmp_path / "four_dimensional.dm4"
    path.write_bytes(b"unused")
    fake = FakeDMReader(
        path,
        data_shapes=[4],
        x_sizes=[4],
        y_sizes=[3],
        z_sizes=[2],
        z2_sizes=[1],
        data_types=[6],
    )
    monkeypatch.setattr(dm_reader, "_open_reader", lambda _: fake)

    with pytest.raises(NoSupportedDatasetError, match="declared 4D"):
        DMImageSource(path)


def test_dm_shape_mismatch_closes_mapping_and_reader(tmp_path, monkeypatch) -> None:
    path = tmp_path / "mismatch.dm4"
    path.write_bytes(np.arange(4, dtype=np.uint8).tobytes())
    fake = FakeDMReader(
        path,
        data_shapes=[2],
        x_sizes=[2],
        y_sizes=[2],
        z_sizes=[1],
        z2_sizes=[1],
        data_types=[6],
    )
    mapped = np.memmap(path, dtype=np.uint8, mode="r", shape=(1, 4))
    fake.getMemmap = lambda _index: mapped
    monkeypatch.setattr(dm_reader, "_open_reader", lambda _: fake)

    with pytest.raises(SourceOpenError, match="shape does not match"):
        DMImageSource(path)

    assert mapped._mmap.closed
    assert fake.closed


def test_malformed_dm_file_has_user_facing_open_error(tmp_path) -> None:
    path = tmp_path / "broken.dm4"
    path.write_bytes(b"not a DM file")

    with pytest.raises(SourceOpenError, match="could not open DM file"):
        list_dm_datasets(path)
