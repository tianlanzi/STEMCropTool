"""Verify a locally built Windows portable release and write a JSON report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
from tempfile import TemporaryDirectory
import time

import pefile

from stem_crop_tool import __version__
from stem_crop_tool.app import (
    EXTERNAL_TEST_DATA_ENV,
    RELEASE_SELF_TEST_DIR_ENV,
    SMOKE_TEST_TIMEOUT_ENV,
)
from stem_crop_tool.release_self_test import REPORT_NAME


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIST = ROOT / "dist" / "STEMCropTool"
REQUIRED_LICENSES = (
    "GPL-3.0.txt",
    "LGPL-3.0.txt",
    "NCEMPY_IO_MIT.txt",
    "python/LICENSE_PYTHON.txt",
    "numpy/LICENSE.txt",
    "pyinstaller/COPYING.txt",
)
EXPECTED_QT_MODULES = {"qt6core.dll", "qt6gui.dll", "qt6widgets.dll"}
EXPECTED_QT_PLUGINS = {
    "plugins/imageformats/qico.dll",
    "plugins/imageformats/qjpeg.dll",
    "plugins/platforms/qoffscreen.dll",
    "plugins/platforms/qwindows.dll",
    "plugins/styles/qmodernwindowsstyle.dll",
}
FORBIDDEN_RUNTIME_NAMES = {"icudt78.dll", "icuuc.dll", "opengl32sw.dll"}


def _sanitized_environment() -> dict[str, str]:
    """Return an environment that cannot borrow Python/Conda project files."""

    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("CONDA", "PYTHON", "VIRTUAL_ENV")):
            environment.pop(key, None)
    system_root = Path(environment.get("SystemRoot", r"C:\Windows"))
    environment["PATH"] = os.pathsep.join(
        (str(system_root / "System32"), str(system_root))
    )
    return environment


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _run(executable: Path, environment: dict[str, str], timeout: int = 60) -> float:
    started = time.perf_counter()
    completed = subprocess.run(
        [str(executable)],
        cwd=executable.parent,
        env=environment,
        check=False,
        timeout=timeout,
    )
    duration = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"packaged executable exited with {completed.returncode}"
        )
    return duration


def _file_version(executable: Path) -> str:
    image = pefile.PE(str(executable), fast_load=True)
    image.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
    )
    for group in getattr(image, "FileInfo", []):
        for entry in group:
            if entry.Key == b"StringFileInfo":
                for table in entry.StringTable:
                    value = table.entries.get(b"FileVersion")
                    if value:
                        return value.decode("utf-8")
    raise AssertionError("FileVersion metadata is missing")


def verify_release(
    dist_dir: Path,
    *,
    test_data_dir: Path | None,
    startup_runs: int,
) -> dict[str, object]:
    executable = dist_dir / "STEMCropTool.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if not (dist_dir / "THIRD_PARTY_NOTICES.md").is_file():
        raise AssertionError("THIRD_PARTY_NOTICES.md is missing")
    for relative in REQUIRED_LICENSES:
        if not (dist_dir / "licenses" / relative).is_file():
            raise AssertionError(f"required license is missing: {relative}")

    internal = dist_dir / "_internal"
    qt_root = internal / "PySide6"
    qt_modules = {
        path.name.lower() for path in qt_root.glob("Qt6*.dll")
    }
    if qt_modules != EXPECTED_QT_MODULES:
        raise AssertionError(f"unexpected Qt module set: {sorted(qt_modules)}")
    qt_plugins = {
        path.relative_to(qt_root).as_posix().lower()
        for path in (qt_root / "plugins").rglob("*.dll")
    }
    if qt_plugins != EXPECTED_QT_PLUGINS:
        raise AssertionError(f"unexpected Qt plugin set: {sorted(qt_plugins)}")
    runtime_names = {
        path.name.lower() for path in internal.rglob("*") if path.is_file()
    }
    forbidden_found = runtime_names & FORBIDDEN_RUNTIME_NAMES
    if forbidden_found:
        raise AssertionError(
            f"unnecessary or incompatible runtime files: {sorted(forbidden_found)}"
        )

    environment = _sanitized_environment()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    with TemporaryDirectory(prefix="stem-crop-packaged-test-") as raw_workspace:
        workspace = Path(raw_workspace)
        environment[RELEASE_SELF_TEST_DIR_ENV] = str(workspace)
        environment.pop(SMOKE_TEST_TIMEOUT_ENV, None)
        if test_data_dir is None:
            environment.pop(EXTERNAL_TEST_DATA_ENV, None)
        else:
            environment[EXTERNAL_TEST_DATA_ENV] = str(test_data_dir)
        self_test_seconds = _run(executable, environment)
        self_test = json.loads(
            (workspace / REPORT_NAME).read_text(encoding="utf-8")
        )

    environment.pop(RELEASE_SELF_TEST_DIR_ENV, None)
    environment.pop(EXTERNAL_TEST_DATA_ENV, None)
    environment[SMOKE_TEST_TIMEOUT_ENV] = "1"
    startup_seconds = [
        _run(executable, environment) for _ in range(startup_runs)
    ]

    files = tuple(path for path in dist_dir.rglob("*") if path.is_file())
    archive = dist_dir.parent / f"STEMCropTool-{__version__}-windows-x86_64.zip"
    return {
        "status": "passed",
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": platform.platform(),
        "clean_machine_verified": False,
        "sanitized_environment_verified": True,
        "version": _file_version(executable),
        "executable_sha256": _sha256(executable),
        "distribution_file_count": len(files),
        "distribution_bytes": sum(path.stat().st_size for path in files),
        "archive_path": str(archive) if archive.is_file() else None,
        "archive_bytes": archive.stat().st_size if archive.is_file() else None,
        "archive_sha256": _sha256(archive) if archive.is_file() else None,
        "startup_runs": startup_runs,
        "startup_median_seconds": statistics.median(startup_seconds),
        "self_test_seconds": self_test_seconds,
        "self_test": self_test,
        "qt_modules": sorted(qt_modules),
        "qt_plugins": sorted(qt_plugins),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST)
    parser.add_argument("--test-data", type=Path)
    parser.add_argument("--startup-runs", type=int, default=5)
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "build" / "phase8_release_report.json",
    )
    args = parser.parse_args()
    if args.startup_runs < 1:
        parser.error("--startup-runs must be at least 1")

    report = verify_release(
        args.dist,
        test_data_dir=args.test_data,
        startup_runs=args.startup_runs,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
