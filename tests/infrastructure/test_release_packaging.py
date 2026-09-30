from __future__ import annotations

from pathlib import Path
import struct
import tomllib

from stem_crop_tool import __version__


ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "packaging" / "pyinstaller"


def test_release_version_is_synchronized() -> None:
    metadata = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert metadata["project"]["version"] == __version__

    version_info = (PACKAGING / "version_info.txt").read_text(encoding="utf-8")
    numeric_version = tuple(int(part) for part in __version__.split(".")) + (0,)
    assert f"filevers={numeric_version}" in version_info
    assert f"prodvers={numeric_version}" in version_info
    assert f"StringStruct('FileVersion', '{__version__}')" in version_info


def test_application_icon_contains_expected_resolutions() -> None:
    asset_dir = ROOT / "src" / "stem_crop_tool" / "assets"
    icon = (asset_dir / "app_icon.ico").read_bytes()
    reserved, image_type, image_count = struct.unpack_from("<HHH", icon)
    assert (reserved, image_type, image_count) == (0, 1, 7)

    sizes: set[int] = set()
    for index in range(image_count):
        width, height = struct.unpack_from("<BB", icon, 6 + index * 16)
        parsed_width = 256 if width == 0 else width
        parsed_height = 256 if height == 0 else height
        assert parsed_width == parsed_height
        sizes.add(parsed_width)
    assert sizes == {16, 24, 32, 48, 64, 128, 256}
    assert (asset_dir / "app_icon.svg").is_file()


def test_committed_release_license_bundle_is_present() -> None:
    required = {
        "GPL-3.0.txt",
        "LGPL-3.0.txt",
        "NCEMPY_IO_MIT.txt",
        "qt-third-party/DOUBLE_CONVERSION_LICENSE.txt",
        "qt-third-party/FREETYPE_FTL.txt",
        "qt-third-party/HARFBUZZ_COPYING.txt",
        "qt-third-party/ICU_LICENSE.txt",
        "qt-third-party/LIBJPEG_TURBO_LICENSE.md",
        "qt-third-party/LIBPNG_LICENSE.txt",
        "qt-third-party/PCRE2_COPYING.txt",
        "qt-third-party/ZLIB_LICENSE.txt",
    }
    assert all((ROOT / "licenses" / relative).is_file() for relative in required)
    assert (ROOT / "THIRD_PARTY_NOTICES.md").is_file()


def test_spec_preserves_portable_release_policies() -> None:
    spec = (PACKAGING / "STEMCropTool.spec").read_text(encoding="utf-8")
    assert 'name="STEMCropTool"' in spec
    assert "console=False" in spec
    assert spec.count("upx=False") == 2
    assert "icon=str(ICON_PATH)" in spec
    assert "version=str(VERSION_FILE)" in spec
    assert '"pyside6/qt6core.dll"' in spec
    assert '"pyside6/qt6gui.dll"' in spec
    assert '"pyside6/qt6widgets.dll"' in spec
    assert 'leaf in {"icudt78.dll", "icuuc.dll", "opengl32sw.dll"}' in spec
