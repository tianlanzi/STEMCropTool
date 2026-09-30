r"""Reproducible Phase 7 timing and batch-memory measurements.

Run from the repository root with the project-local Python environment:

    .\.venv\python.exe tools\phase7_benchmark.py \
        --data-dir "D:\work\STEM image crop tool\test data" \
        --output docs\phase7_benchmark.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
from typing import Callable, TypeVar

import numpy as np
import PySide6

from stem_crop_tool.core.batch import all_slice_indices
from stem_crop_tool.core.models import (
    CropRect,
    ExportFormat,
    ExportRequest,
    NormalizationMode,
)
from stem_crop_tool.core.readers.npy import NpyImageSource
from stem_crop_tool.infrastructure.display import make_grayscale_qimage
from stem_crop_tool.infrastructure.exporters import export_source
from stem_crop_tool.infrastructure.source_loader import open_image_source


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "external" / "manifest.json"
T = TypeVar("T")


def _median_seconds(action: Callable[[], T], repeat: int) -> tuple[float, T]:
    durations: list[float] = []
    result: T | None = None
    for _ in range(repeat):
        started = time.perf_counter()
        result = action()
        durations.append(time.perf_counter() - started)
    assert result is not None
    return statistics.median(durations), result


def _windows_rss_bytes() -> int:
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_process_memory_info.restype = ctypes.c_int
    handle = get_current_process()
    if not get_process_memory_info(
        handle,
        ctypes.byref(counters),
        counters.cb,
    ):
        raise OSError("GetProcessMemoryInfo failed")
    return int(counters.WorkingSetSize)


def _current_rss_bytes() -> int:
    if os.name == "nt":
        return _windows_rss_bytes()
    statm = Path("/proc/self/statm")
    if statm.is_file():
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * int(os.sysconf("SC_PAGE_SIZE"))
    return 0


def _total_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
    try:
        return int(os.sysconf("SC_PHYS_PAGES")) * int(
            os.sysconf("SC_PAGE_SIZE")
        )
    except (AttributeError, OSError, ValueError):
        return None


def _measure_peak_rss(action: Callable[[], T]) -> tuple[T, int, int]:
    baseline = _current_rss_bytes()
    peak = baseline
    stop = Event()

    def sample() -> None:
        nonlocal peak
        while not stop.wait(0.002):
            peak = max(peak, _current_rss_bytes())

    sampler = Thread(target=sample, daemon=True)
    sampler.start()
    try:
        result = action()
        peak = max(peak, _current_rss_bytes())
    finally:
        stop.set()
        sampler.join()
    return result, baseline, peak


def _load_manifest() -> list[dict[str, object]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return payload["fixtures"]


def _fixture(fixtures: list[dict[str, object]], kind: str) -> dict[str, object]:
    return next(item for item in fixtures if item["kind"] == kind)


def _startup_seconds(repeat: int) -> float:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["STEM_CROP_TOOL_SMOKE_TEST_MS"] = "1"

    def launch() -> int:
        completed = subprocess.run(
            [sys.executable, "-m", "stem_crop_tool"],
            cwd=ROOT,
            env=environment,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"application smoke process exited with {completed.returncode}"
            )
        return completed.returncode

    median, _ = _median_seconds(launch, repeat)
    return median


def _open_seconds(path: Path, repeat: int, dataset_index: int | None) -> float:
    def open_and_close() -> tuple[int, ...]:
        source = open_image_source(path, dataset_index=dataset_index)
        try:
            return source.shape
        finally:
            source.close()

    median, _ = _median_seconds(open_and_close, repeat)
    return median


def run(data_dir: Path, repeat: int) -> dict[str, object]:
    fixtures = _load_manifest()
    paths = {item["filename"]: data_dir / item["filename"] for item in fixtures}
    missing = [path.name for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing benchmark fixtures: {', '.join(missing)}")

    total_memory = _total_memory_bytes()
    results: dict[str, object] = {
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "total_memory_bytes": total_memory,
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyside6": PySide6.__version__,
        },
        "fixtures": [
            {
                "filename": item["filename"],
                "sha256": item["sha256"],
                "shape": item["shape"],
                "dtype": item["dtype"],
            }
            for item in fixtures
        ],
        "repeat": repeat,
        "startup_median_seconds": _startup_seconds(repeat),
    }

    open_results: dict[str, float] = {}
    for item in fixtures:
        dataset_index = (
            int(item["dataset_index"]) if item["kind"] == "dm_image" else None
        )
        open_results[str(item["filename"])] = _open_seconds(
            paths[item["filename"]], repeat, dataset_index
        )
    results["open_median_seconds"] = open_results

    stack_fixture = _fixture(fixtures, "npy_stack")
    stack_path = paths[stack_fixture["filename"]]
    with NpyImageSource(stack_path) as source:
        indices = tuple(range(source.slice_count)) * max(8, repeat)

        access_started = time.perf_counter()
        for index in indices:
            image = source.get_slice(index)
            _ = image[0, 0]
        access_seconds = time.perf_counter() - access_started

        display_samples: list[float] = []
        for index in range(source.slice_count):
            started = time.perf_counter()
            frame = make_grayscale_qimage(source.get_slice(index))
            display_samples.append(time.perf_counter() - started)
            assert frame.buffer.shape == source.metadata.image_shape

        with TemporaryDirectory(prefix="stem-crop-benchmark-") as raw_output:
            output_dir = Path(raw_output) / "batch"
            request = ExportRequest(
                destination=output_dir,
                crop=CropRect(0, 0, source.shape[-1], source.shape[-2]),
                output_format=ExportFormat.NPY,
                normalization=NormalizationMode.LOCAL_MINMAX,
                slice_indices=all_slice_indices(source.slice_count),
                overwrite=False,
            )
            batch_started = time.perf_counter()
            result, baseline_rss, peak_rss = _measure_peak_rss(
                lambda: export_source(source, request)
            )
            batch_seconds = time.perf_counter() - batch_started
            output_bytes = sum(path.stat().st_size for path in result.output_paths)

    results["stack"] = {
        "filename": stack_fixture["filename"],
        "slice_access_count": len(indices),
        "slice_access_mean_seconds": access_seconds / len(indices),
        "display_prepare_median_seconds": statistics.median(display_samples),
        "batch_seconds": batch_seconds,
        "batch_output_bytes": output_bytes,
        "batch_baseline_rss_bytes": baseline_rss,
        "batch_peak_rss_bytes": peak_rss,
        "batch_peak_delta_bytes": max(0, peak_rss - baseline_rss),
        "batch_completed_slices": len(result.completed_slice_indices),
    }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    payload = run(args.data_dir, args.repeat)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
