# STEMCropTool

STEMCropTool is a planned cross-platform desktop application for pixel-exact
cropping of grayscale STEM images and image stacks.

Phases 0 through 3 of the [implementation plan](IMPLEMENTATION_PLAN.md) are
complete. The repository contains the application shell, early Windows
packaging configuration, a Qt-independent tested core, and lazy readers for
NPY, PNG, JPEG, DM3, and DM4 data. It also contains a tested streaming export
engine for raw/normalized NPY and PNG output, JSON sidecars, and batch
manifests. The interactive file-open and crop UI are intentionally reserved for
later phases.

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

## Run tests

```powershell
& '.\.venv\python.exe' -m pytest
```

External DM samples are not committed. To include local real-data integration
tests, point `STEM_CROP_TOOL_TEST_DATA` at the directory containing the DM3 and
DM4 files before running pytest.

## Build the Windows smoke package

```powershell
& '.\.venv\python.exe' -m PyInstaller --noconfirm --clean '.\packaging\pyinstaller\STEMCropTool.spec'
```

The unpacked application is written to `dist\STEMCropTool\`.

For a bounded, non-interactive source or packaged smoke check, set
`STEM_CROP_TOOL_SMOKE_TEST_MS` to a positive number of milliseconds and set
`QT_QPA_PLATFORM=offscreen`. The application will start its event loop and exit
automatically after the specified interval.

## Scope

Development must proceed phase by phase according to
`IMPLEMENTATION_PLAN.md`. Do not implement later-phase functionality while an
earlier phase is incomplete.
