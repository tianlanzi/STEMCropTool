# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from importlib.metadata import distribution
import sys


PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
ENTRY_POINT = SOURCE_ROOT / "stem_crop_tool" / "__main__.py"
ICON_PATH = SOURCE_ROOT / "stem_crop_tool" / "assets" / "app_icon.ico"
LICENSE_ROOT = PROJECT_ROOT / "licenses"
VERSION_FILE = Path(SPECPATH) / "version_info.txt"


def distribution_license_data(distribution_name, destination):
    """Collect the exact license tree installed for one build dependency."""

    package = distribution(distribution_name)
    result = []
    for entry in package.files or ():
        normalized = entry.as_posix()
        marker = ".dist-info/licenses/"
        if marker not in normalized:
            continue
        relative = normalized.split(marker, 1)[1]
        source = Path(package.locate_file(entry))
        result.append((str(source), str(Path(destination) / Path(relative).parent)))
    return result


datas = [
    (str(ICON_PATH), "stem_crop_tool/assets"),
    (str(PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(LICENSE_ROOT), "licenses"),
    (str(Path(sys.prefix) / "LICENSE_PYTHON.txt"), "licenses/python"),
]
datas += distribution_license_data("numpy", "licenses/numpy")
datas += distribution_license_data("pyinstaller", "licenses/pyinstaller")
binaries = [(str(Path(sys.prefix) / "Library" / "bin" / "ffi.dll"), ".")]


ALLOWED_QT_PLUGINS = {
    "pyside6/plugins/imageformats/qico.dll",
    "pyside6/plugins/imageformats/qjpeg.dll",
    "pyside6/plugins/platforms/qoffscreen.dll",
    "pyside6/plugins/platforms/qwindows.dll",
    "pyside6/plugins/styles/qmodernwindowsstyle.dll",
}
ALLOWED_QT_MODULES = {
    "pyside6/qt6core.dll",
    "pyside6/qt6gui.dll",
    "pyside6/qt6widgets.dll",
    "pyside6/qtcore.pyd",
    "pyside6/qtgui.pyd",
    "pyside6/qtwidgets.pyd",
}


def keep_required_qt_entry(entry):
    destination = entry[0].replace("\\", "/").lower()
    leaf = destination.rsplit("/", 1)[-1]
    if leaf in {"icudt78.dll", "icuuc.dll", "opengl32sw.dll"}:
        return False
    if destination.startswith("pyside6/plugins/"):
        return destination in ALLOWED_QT_PLUGINS
    if destination.startswith(("pyside6/qml/", "pyside6/translations/")):
        return False
    if destination.startswith("pyside6/") and (
        (leaf.startswith("qt6") and leaf.endswith(".dll"))
        or (leaf.startswith("qt") and leaf.endswith(".pyd"))
    ):
        return destination in ALLOWED_QT_MODULES
    return True


analysis = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(SOURCE_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "PIL",
        "matplotlib",
        "pytest",
        "scipy",
        "skimage",
        "sklearn",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)

analysis.binaries = [
    entry for entry in analysis.binaries if keep_required_qt_entry(entry)
]
analysis.datas = [entry for entry in analysis.datas if keep_required_qt_entry(entry)]

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="STEMCropTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
    version=str(VERSION_FILE),
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="STEMCropTool",
)
