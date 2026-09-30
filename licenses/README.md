# Release license bundle

This directory contains license texts committed with STEMCropTool and is copied
into every portable release:

- `GPL-3.0.txt` and `LGPL-3.0.txt` cover the selected PySide6/Shiboken6/Qt
  LGPLv3 distribution option.
- `NCEMPY_IO_MIT.txt` covers the vendored DigitalMicrograph reader.
- `qt-third-party/` contains notices for permissively licensed components used
  by the selected Qt runtime modules and image codecs.

The build spec also copies version-matched licenses directly from the active
project environment:

- CPython's `LICENSE_PYTHON.txt` to `licenses/python/`;
- NumPy's complete installed license tree to `licenses/numpy/`;
- PyInstaller's installed bootloader license to `licenses/pyinstaller/`.

`packaging/pyinstaller/verify_release.py` fails when any required release
license is absent. Keep `THIRD_PARTY_NOTICES.md` synchronized with changes to
runtime dependencies or the Qt module/plugin allowlist.
