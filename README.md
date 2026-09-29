# STEMCropTool

STEMCropTool is a planned cross-platform desktop application for pixel-exact
cropping of grayscale STEM images and image stacks.

The repository is currently at **Phase 0** of the
[implementation plan](IMPLEMENTATION_PLAN.md): it contains only the application
shell, test setup, and early Windows packaging configuration. Scientific file
reading, crop operations, and export are intentionally not implemented yet.

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
