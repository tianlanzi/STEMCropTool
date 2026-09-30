# Phase 8 Windows release record

Recorded on 2026-09-30 (Asia/Shanghai) with the repository-local 64-bit Python
3.12 environment. This document describes a local release candidate, not a
completed public release.

## Build and artifact

The release is built reproducibly from the repository root with:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\build_release.py'
```

It produces a PyInstaller `--onedir` portable directory and a versioned ZIP:

```text
dist\STEMCropTool\
dist\STEMCropTool-0.1.0-windows-x86_64.zip
```

The exact size, file count, hashes, and startup measurements below are filled
from the final `build\phase8_release_report.json` generated during this phase.

<!-- RELEASE_METRICS_START -->
- Distribution: 167 files, 99,082,940 bytes (94.49 MiB)
- Executable SHA-256:
  `f79c0dee9fcb285ab97fce1c3447ad5c29a0bc593de81262f3b47a48cd5a287e`
- ZIP: 38,840,822 bytes (37.04 MiB)
- ZIP SHA-256:
  `b7b0b78c05c811d505a7ac13f75739321450da7f9a3a2296bb3ce622bbf75355`
- Packaged startup: 0.455 seconds median over five offscreen runs
- Frozen real-data self-test: 2.610 seconds
<!-- RELEASE_METRICS_END -->

## Local isolated-environment validation

The local verifier removes Conda, Python, and virtual-environment variables,
restricts PATH to the Windows system directories, and uses Qt's offscreen
platform. It checks:

- PE file version metadata;
- required application and dependency license material;
- the exact Qt Core/Gui/Widgets DLL and plugin allowlist;
- absence of the incompatible Conda ICU and unnecessary software OpenGL DLLs;
- bounded application startup;
- 2D NPY, 3D NPY, 16-bit PNG, JPEG, real DM3, and real DM4 input;
- exact raw NPY and 16-bit PNG export;
- same-ROI NPY stack batch export;
- JSON sidecar and batch manifest creation.

Run it with:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\verify_release.py' `
  --test-data 'D:\work\STEM image crop tool\test data' `
  --startup-runs 5
```

This isolated local matrix passes. During packaging, an early build failed
with Windows error 127 because Conda ICU DLLs exported version-suffixed symbols
that did not satisfy the PySide6 Qt6Core ABI. The final spec deliberately
excludes those DLLs and succeeds using the Windows system ICU ABI. A separate
bounded launch with the native Windows Qt platform plugin and the same
sanitized PATH also exits successfully.

## Independent-machine gate

Phase 8 remains in progress until the ZIP is extracted and checked on an
independent Windows 10/11 VM without Python, Conda, Qt, or this repository.
On that VM:

1. Run `verify_clean_machine.ps1 -TestData <fixture-directory>` from beside the
   extracted `STEMCropTool` directory.
2. Confirm that its report includes all six input types and both real DM files.
3. Launch `STEMCropTool.exe` normally.
4. Open one supplied file, create/move/resize a crop, and open the export
   dialog.
5. Export one crop and confirm the output plus JSON metadata.
6. Record the Windows version and outcome here before marking Phase 8 complete.

No installer is created until this gate passes. The absence of a real 3D DM
fixture remains the separately documented Phase 7 limitation. After this
Windows gate passes, the initial version has no macOS release requirement;
macOS packaging has been moved to a later product version.
