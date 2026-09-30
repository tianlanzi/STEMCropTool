# External STEM fixtures

The real microscopy fixtures are intentionally not committed. Put local files
in one directory and point `STEM_CROP_TOOL_TEST_DATA` at it before running the
test suite:

```powershell
$env:STEM_CROP_TOOL_TEST_DATA = 'D:\work\STEM image crop tool\test data'
& '.\.venv\python.exe' -m pytest
```

`manifest.json` records the expected filename, byte count, SHA-256 digest,
shape, dtype, calibration, and a few trusted pixel values for the supplied
fixtures. The DM expectations were generated independently with
`motif-learn/mtflearn/io/_dm_ncempy.py` at the commit recorded in the manifest.
Tests skip cleanly when the environment variable is absent and fail when a
same-named local fixture does not match its recorded identity.

A real 3D DM stack is not currently available. Synthetic reader tests cover
the 3D code path, but DM stack support remains provisional until a real fixture
can be added here and validated for slice order and lazy access.
