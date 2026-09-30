# Windows portable release

Phase 8 uses PyInstaller `--onedir`. Build only from 64-bit Windows with the
repository-local Python 3.12 environment defined in `ENVIRONMENT_RULES.md`.

## Build

From the repository root:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\build_release.py'
```

The build script runs PyInstaller with `STEMCropTool.spec`, moves notices to a
visible top-level `licenses` directory, includes the clean-machine verifier, and
creates:

```text
dist\STEMCropTool\STEMCropTool.exe
dist\STEMCropTool-0.1.0-windows-x86_64.zip
```

The entire `STEMCropTool` directory must stay together. Copying only the EXE is
not supported.

## Local packaged validation

Run the packaged executable against the supplied real DM fixtures while hiding
the development Python/Conda paths:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\verify_release.py' `
  --test-data 'D:\work\STEM image crop tool\test data' `
  --startup-runs 5
```

The verifier checks version metadata, required notices, the exact Qt
module/plugin allowlist, artifact size and hash, bounded startup, and an
in-process frozen matrix covering NPY, 3D NPY, 16-bit PNG, JPEG, DM3, DM4, NPY
and PNG export, batch export, sidecars, and manifests. Its generated report is
written to `build\phase8_release_report.json` and is intentionally not tracked.

## Clean-machine validation

Extract the ZIP on a Windows 10/11 VM that does not have Python, Conda, Qt, or
the repository installed. Copy the external test-data directory to the VM, then
run from PowerShell:

```powershell
& '.\STEMCropTool\verify_clean_machine.ps1' `
  -TestData 'C:\path\to\test data'
```

The script sanitizes Python/Conda environment variables and reports the exact
input/output matrix. Also launch `STEMCropTool.exe` normally and manually check
the main window, icon, file dialog, one crop interaction, and export dialog.
Record the VM Windows version and the command result before marking Phase 8
complete.

## Packaging decisions

- Qt stays dynamically linked and replaceable under the LGPLv3 option.
- Only Qt Core, Gui, Widgets, five required plugins, and their runtime
  dependencies are included.
- The incompatible Conda ICU DLLs are deliberately excluded: the PySide6 wheel
  links against the Windows system ICU ABI.
- UPX is disabled for predictable binaries and simpler diagnostics.
- No installer is created until the portable directory passes clean-machine
  validation.
- Nuitka/pyside6-deploy comparison is deferred; PyInstaller is the release
  baseline.
