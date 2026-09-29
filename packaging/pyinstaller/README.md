# PyInstaller Phase 0 smoke build

Run from the repository root with the dedicated project environment:

```powershell
& '.\.venv\python.exe' -m PyInstaller --noconfirm --clean '.\packaging\pyinstaller\STEMCropTool.spec'
```

The `--onedir` output is:

```text
dist\STEMCropTool\STEMCropTool.exe
```

Bounded, offscreen launch check:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:STEM_CROP_TOOL_SMOKE_TEST_MS = '500'
& '.\dist\STEMCropTool\STEMCropTool.exe'
if ($LASTEXITCODE -ne 0) { throw "Packaged smoke test failed: $LASTEXITCODE" }
Remove-Item Env:STEM_CROP_TOOL_SMOKE_TEST_MS
Remove-Item Env:QT_QPA_PLATFORM
```

This is an early packaging spike, not the Phase 8 release configuration. License
bundling, icons, version resources, clean-machine testing, and final plugin
pruning remain Phase 8 work.
