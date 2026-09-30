# STEMCropTool

STEMCropTool is a Windows desktop application for pixel-exact cropping of
grayscale STEM images and image stacks. Its architecture remains suitable for
future cross-platform work, but macOS packaging is deferred to a later version.

Phases 0 through 6 of the [implementation plan](IMPLEMENTATION_PLAN.md) are
complete. Phase 7 has completed every available validation but still awaits a
real 3D DM fixture. Phase 8 has a locally validated Windows release candidate
and awaits its final independent-VM check. The application provides lazy
readers for NPY, PNG, JPEG, DM3, and DM4 data; zoom/pan and stack navigation; a
movable, resizable pixel-exact crop; and background single or batch export to
raw/normalized NPY and PNG. Exports include JSON sidecars or batch manifests
and can be cancelled from the UI.

The reader layer preserves source dtype and declared dimensionality. NPY and DM
stacks are memory-mapped, grayscale PNG supports exact 8-bit and 16-bit values,
color rasters are rejected, and DM calibration/tags remain available through
the adapter. Real 2D DM3 and DM4 samples have been validated; real 3D DM stack
support remains explicitly provisional until such a fixture is available.

Exports use exact integer source-pixel crops. Batch jobs apply the same crop to
each selected slice and process one slice at a time. Existing files are never
replaced unless the request explicitly enables overwrite, and incomplete
current outputs use same-directory temporary files that are removed after
failure. Single exports write a same-stem JSON sidecar; batch exports write one
`manifest.json`.

## Development environment

The initial release targets 64-bit Python 3.12. Use a dedicated Conda prefix in
the repository; do not install project dependencies into Conda `base` or a
shared environment.

From PowerShell in the repository root:

```powershell
& 'C:\Users\Joseph\anaconda3\Scripts\conda.exe' create --prefix '.\.venv' python=3.12 pip -y
& '.\.venv\python.exe' -m pip install -e '.[dev]'
```

All commands below use the explicit project interpreter and do not require
activating the environment.

## Run the application shell

```powershell
& '.\.venv\python.exe' -m stem_crop_tool
```

Open one supported image through **File → Open** or drag a single `.npy`,
`.png`, `.jpg`, `.jpeg`, `.dm3`, or `.dm4` file from Explorer onto the
application window. File drops use the same background reader, validation, and
DM dataset-selection workflow as the Open command.

## Run tests

```powershell
& '.\.venv\python.exe' -m pytest
```

External microscopy samples are not committed. To include local real-data
integration tests, point `STEM_CROP_TOOL_TEST_DATA` at the fixture directory
before running pytest. The expected fixture identities and reference values are
documented in `tests/fixtures/external/manifest.json`.

Phase 7 validation results and the reproducible performance command are in
`docs/phase7_validation.md`. Real 2D DM3 and DM4 data are validated against the
local motif-learn reference reader. Real 3D DM stack support remains provisional
because no representative fixture is currently available.

## Build the Windows portable release

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\build_release.py'
```

This creates both `dist\STEMCropTool\` and
`dist\STEMCropTool-0.1.0-windows-x86_64.zip`. Keep the entire portable
directory together; the EXE is not standalone.

Validate the frozen input/export matrix, including the local real DM3/DM4
fixtures, while hiding the development Python and Conda environment:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\verify_release.py' `
  --test-data 'D:\work\STEM image crop tool\test data' `
  --startup-runs 5
```

Full build, clean-machine, and licensing instructions are in
[`packaging/pyinstaller/README.md`](packaging/pyinstaller/README.md). The local
Phase 8 evidence and remaining independent-VM gate are recorded in
[`docs/phase8_windows_release.md`](docs/phase8_windows_release.md).

For a bounded, non-interactive source or packaged smoke check, set
`STEM_CROP_TOOL_SMOKE_TEST_MS` to a positive number of milliseconds and set
`QT_QPA_PLATFORM=offscreen`. The application will start its event loop and exit
automatically after the specified interval.

## Scope

Development must proceed phase by phase according to
`IMPLEMENTATION_PLAN.md`. Do not implement later-phase functionality while an
earlier phase is incomplete.
