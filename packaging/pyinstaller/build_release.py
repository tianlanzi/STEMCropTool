"""Build the reproducible Windows portable directory and ZIP artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from stem_crop_tool import __version__


ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().with_name("STEMCropTool.spec")
DIST_ROOT = ROOT / "dist"
DIST_DIR = DIST_ROOT / "STEMCropTool"
INTERNAL_DIR = DIST_DIR / "_internal"


def _move_release_notices() -> None:
    internal_notices = INTERNAL_DIR / "THIRD_PARTY_NOTICES.md"
    internal_licenses = INTERNAL_DIR / "licenses"
    if not internal_notices.is_file() or not internal_licenses.is_dir():
        raise FileNotFoundError("PyInstaller did not stage the release notices")

    shutil.move(str(internal_notices), DIST_DIR / internal_notices.name)
    root_licenses = DIST_DIR / "licenses"
    if root_licenses.exists():
        shutil.rmtree(root_licenses)
    shutil.move(str(internal_licenses), root_licenses)
    shutil.copy2(
        Path(__file__).resolve().with_name("verify_clean_machine.ps1"),
        DIST_DIR / "verify_clean_machine.ps1",
    )


def build_release(*, skip_zip: bool = False) -> Path | None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(SPEC),
        ],
        cwd=ROOT,
        check=True,
    )
    _move_release_notices()
    if skip_zip:
        return None

    archive_base = DIST_ROOT / f"STEMCropTool-{__version__}-windows-x86_64"
    archive_path = Path(f"{archive_base}.zip")
    archive_path.unlink(missing_ok=True)
    shutil.make_archive(
        str(archive_base),
        "zip",
        root_dir=DIST_ROOT,
        base_dir=DIST_DIR.name,
    )
    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-zip", action="store_true")
    args = parser.parse_args()
    archive = build_release(skip_zip=args.skip_zip)
    print(DIST_DIR)
    if archive is not None:
        print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
