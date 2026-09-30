<p align="center">
  <img src="src/stem_crop_tool/assets/app_icon.svg" width="128" alt="STEMCropTool application icon">
</p>

<h1 align="center">STEMCropTool</h1>

<p align="center">
  A Windows desktop tool for pixel-exact cropping of grayscale STEM images
  and image stacks.
</p>

STEMCropTool provides a focused graphical workflow for opening scientific
images, selecting one exact rectangular region, and exporting that region from
a single image or an entire stack. It supports common grayscale raster files,
NumPy arrays, and DigitalMicrograph data without requiring users to install
Python.

The current release target is Windows. macOS packaging is deferred to a later
version.

## Highlights

- Open files through **File → Open** or drag them from Windows Explorer.
- Work in integer source-pixel coordinates, independent of display zoom.
- Create, move, resize, delete, and numerically edit one crop rectangle.
- Hold **Shift** while creating or resizing to constrain the crop to a square.
- Navigate `(Z, Y, X)` image stacks and reuse the same crop on selected slices.
- Export raw data or optionally normalize each exported crop to `[0, 1]`.
- Preserve raw NumPy dtypes and 8-bit/16-bit grayscale PNG values.
- Write reproducibility metadata alongside every export.
- Keep file loading and batch export off the GUI thread.

## Download and run on Windows

Download the latest Windows portable ZIP from
[GitHub Releases](https://github.com/tianlanzi/STEMCropTool/releases). The
release asset is named similarly to:

```text
STEMCropTool-0.1.0-windows-x86_64.zip
```

If the Releases page does not yet contain a ZIP asset, the portable preview
has not been published there; developers can still build it from source using
the instructions below.

Then:

1. Extract the complete ZIP to a normal folder.
2. Open the extracted `STEMCropTool` folder.
3. Double-click `STEMCropTool.exe`.
4. Keep `STEMCropTool.exe` and its `_internal` folder together.

Python, Conda, and Qt do not need to be installed. Do not run the EXE directly
inside the ZIP and do not copy only the EXE out of its folder.

The preview build is not code-signed, so Windows SmartScreen may display an
unknown-publisher warning. Confirm that the file came from this repository,
then select **More info → Run anyway** if you choose to continue.

> [!TIP]
> Start the application normally rather than with **Run as administrator**.
> Windows may block drag-and-drop from Explorer into an elevated application.

## Supported formats

### Input

| Format | Supported data |
| --- | --- |
| PNG | Grayscale 8-bit and 16-bit images |
| JPG / JPEG | Grayscale images |
| NPY | 2D `(Y, X)` images and 3D `(Z, Y, X)` stacks |
| DM3 / DM4 | Supported 2D images and 3D stacks |

Color and multi-channel raster images are rejected rather than silently
converted to grayscale. Arrays with more than three declared dimensions are
also rejected; singleton axes are not automatically removed.

### Output

| Format | Raw export | Normalized export |
| --- | --- | --- |
| NPY | Preserves the input dtype | `float32` in `[0, 1]` |
| PNG | Preserves `uint8` or `uint16` grayscale | `uint8` in `[0, 255]` |

Raw float, signed-integer, Boolean, complex, and unsupported integer PNG
exports are not silently rescaled or truncated. Use NPY to preserve those
supported source values, or enable normalization when PNG is required.

NPZ, TIFF, color images, and JPG/DM export are outside the current scope.

## How to use

### 1. Open an image

Choose **File → Open**, use `Ctrl+O`, or drag one supported file from Explorer
onto the application window. Drag-and-drop accepts one local file at a time.

For a 3D NPY or DM stack, use the slice controls below the image to select the
current slice. Axis 0 is treated as the slice axis.

### 2. Inspect the image

- Rotate the mouse wheel to zoom.
- Drag with the middle mouse button to pan.
- Use **Fit to Window**, **100%**, or **Reset View** from the toolbar or View
  menu.

Display contrast is calculated separately for viewing and never modifies the
source values or exported raw data.

### 3. Select a crop

- Drag on the image to create a rectangular crop.
- Hold **Shift** while creating or resizing for a square crop.
- Drag inside the rectangle to move it.
- Drag a handle to resize it.
- Enter exact `X`, `Y`, `Width`, and `Height` values in the crop controls.
- Use **Clear Crop** or the Delete key to remove the selection.

Coordinates use a top-left origin and exact integer source pixels. The same
crop is retained while switching stack slices.

### 4. Export

Select **Export**, then choose:

- NPY or PNG output;
- raw values or local min-max normalization;
- the current slice, an inclusive slice range, or all slices;
- an output file for one slice or an output directory for a batch;
- whether existing output files may be replaced.

Batch export applies the same crop to every selected slice and processes one
slice at a time. It can be cancelled without invalidating files that were
already completed.

## Normalization and quantitative data

Normalization is local to each exported crop:

```text
(crop - crop.min()) / (crop.max() - crop.min())
```

A constant crop becomes all zeros. A crop containing NaN or infinity cannot
be normalized and produces a clear error.

Each stack slice is normalized independently. This improves the contrast of
individual outputs but removes direct intensity comparability between slices.
Disable normalization when quantitative comparison or original values must be
preserved.

## Export metadata

A single export writes a same-stem JSON sidecar. A batch export writes one
`manifest.json`. Metadata includes the source filename, source shape and dtype,
slice index, crop coordinates, normalization mode, output shape and dtype, and
DM spatial calibration when available.

Unknown calibration values remain `null`; the application does not invent
physical units for PNG, JPEG, or NPY files.

## Current limitations

- The packaged application currently targets 64-bit Windows 10/11.
- The portable preview is not code-signed and does not include an installer.
- The packaged matrix has passed locally on Windows 11; validation on a
  separate clean Windows machine is still pending.
- macOS packaging is deferred to a later version.
- Only grayscale, real-valued 2D images and `(Z, Y, X)` stacks are supported;
  complex arrays are rejected.
- Real 2D DM3 and DM4 files have been validated. Real 3D DM stack support is
  still provisional because a representative fixture is not yet available.
- Only one crop rectangle can exist at a time.

## Development

Development and packaging use 64-bit Python 3.12 in a repository-local Conda
prefix. Do not install project dependencies into Conda `base` or a shared
environment.

From PowerShell in the repository root:

```powershell
& 'C:\Users\Joseph\anaconda3\Scripts\conda.exe' create `
  --prefix '.\.venv' python=3.12 pip -y
& '.\.venv\python.exe' -m pip install -e '.[dev]'
```

Run from source:

```powershell
& '.\.venv\python.exe' -m stem_crop_tool
```

Run the automated suite:

```powershell
& '.\.venv\python.exe' -m pytest
```

Real microscopy fixtures are intentionally not committed. To include the local
real-data integration tests:

```powershell
$env:STEM_CROP_TOOL_TEST_DATA = 'C:\path\to\test data'
& '.\.venv\python.exe' -m pytest
```

Build the portable Windows directory and ZIP:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\build_release.py'
```

The numerical core is independent of Qt. NPY and supported DM stacks use lazy,
memory-mapped access; Qt-specific display, file-dialog, and worker behavior is
kept in the infrastructure and UI layers.

## Documentation

- [Agent-oriented implementation plan](IMPLEMENTATION_PLAN.md)
- [Windows packaging and clean-machine checks](packaging/pyinstaller/README.md)
- [Phase 7 real-data and performance validation](docs/phase7_validation.md)
- [Phase 8 Windows release record](docs/phase8_windows_release.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Third-party notices and acknowledgements

The Windows distribution includes Python, NumPy, PySide6/Qt, the PyInstaller
bootloader, and a vendored DigitalMicrograph reader adapted from NCEMpy.
Applicable notices and dependency license texts are documented in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the
[`licenses/`](licenses/) directory.

## Reporting problems

Please open a [GitHub issue](https://github.com/tianlanzi/STEMCropTool/issues)
with the input format, array shape and dtype, the operation being performed,
and the exact error message. Do not upload private or unpublished microscopy
data unless you have permission to share it.
