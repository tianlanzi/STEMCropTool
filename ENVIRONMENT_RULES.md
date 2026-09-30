# STEMCropTool environment rules

These rules are the source of truth for development commands in this
repository.

## Python environment

- Use 64-bit Python 3.12.
- Use the repository-local Conda prefix at `.venv`.
- On Windows, call the interpreter explicitly as `.venv\python.exe`.
- Do not install project dependencies into Conda `base`.
- Do not modify or use the user's shared `version_3_12` environment as the
  project runtime.
- Do not silently switch to Python 3.11, 3.13, or another interpreter.

Create the environment from the repository root when it does not exist:

```powershell
& 'C:\Users\Joseph\anaconda3\Scripts\conda.exe' create --prefix '.\.venv' python=3.12 pip -y
& '.\.venv\python.exe' -m pip install -e '.[dev]'
```

## Standard commands

Run tests:

```powershell
& '.\.venv\python.exe' -m pytest
```

Run the application:

```powershell
& '.\.venv\python.exe' -m stem_crop_tool
```

Build the Windows portable release candidate:

```powershell
& '.\.venv\python.exe' '.\packaging\pyinstaller\build_release.py'
```

The lower-level PyInstaller spec remains at
`packaging/pyinstaller/STEMCropTool.spec`; use the wrapper above so the license
bundle, clean-machine verifier, and ZIP are assembled consistently.

Follow `IMPLEMENTATION_PLAN.md` phase by phase. Do not implement work from a
later phase while an earlier phase is incomplete unless the user explicitly
changes the order.
