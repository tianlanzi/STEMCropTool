# Third-Party Notices

This notice describes the components included in the STEMCropTool 0.1.0
Windows portable distribution produced from the repository-local Python 3.12
environment. Exact runtime versions for the validated build are recorded in
`IMPLEMENTATION_PLAN.md` and the Phase 8 release report.

## Python

The distribution includes the CPython runtime and portions of its standard
library. The exact Python license installed with the build interpreter is
included under `licenses/python/LICENSE_PYTHON.txt`.

## PySide6, Shiboken6, and Qt 6

The application uses PySide6 and Shiboken6 under the GNU Lesser General Public
License version 3 option. It ships Qt as separate, dynamically loaded DLLs; Qt
is not statically linked into `STEMCropTool.exe`. Recipients may replace those
DLLs with compatible modified builds and may reverse engineer the application
as necessary to debug modifications to the LGPL-covered libraries.

The portable build intentionally contains only Qt Core, Gui, and Widgets, plus
the Windows and offscreen platform plugins, the JPEG and ICO image plugins, and
the modern Windows style plugin. The GNU GPL v3 and LGPL v3 texts are included
as `licenses/GPL-3.0.txt` and `licenses/LGPL-3.0.txt`.

Corresponding Qt/PySide source for the exact binary version can be obtained
from the Qt for Python and Qt source archives published at
https://download.qt.io/official_releases/QtForPython/ and
https://download.qt.io/official_releases/qt/.

Qt binaries may incorporate or accompany permissively licensed components.
The release license bundle includes notices for the components relevant to the
selected Qt modules and codecs, including ICU, libjpeg-turbo, libpng, HarfBuzz,
FreeType, zlib, double-conversion, and PCRE2, under
`licenses/qt-third-party/`.

## NumPy

The distribution includes NumPy. Its installed wheel's complete license tree,
including bundled binary-library notices, is copied at build time to
`licenses/numpy/`.

## Vendored NCEMpy DigitalMicrograph reader

`src/stem_crop_tool/vendor/ncempy_dm.py` is adapted from `ncempy/io/dm.py` in
openNCEM. The selected MIT license and attribution are included as
`licenses/NCEMPY_IO_MIT.txt`; the vendored source header records upstream and
immediate-source commits plus local modifications.

## PyInstaller

The Windows executable uses the PyInstaller bootloader. PyInstaller is licensed
under GPL-2.0-or-later with its bootloader exception, which permits distribution
of applications built with the bootloader. Its installed `COPYING.txt` is
copied at build time to `licenses/pyinstaller/`.

## Development-only dependencies

pytest and pytest-qt are used only for development and validation. They are
excluded from the portable distribution.
