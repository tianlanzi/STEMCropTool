# Phase 7 validation record

Recorded on 2026-09-30 (Asia/Shanghai) with the repository-local Python 3.12
environment. Real fixture identity and expected values are defined in
`tests/fixtures/external/manifest.json`; the image data itself is not committed.

## System and runtime

- Computer: MECHREVO Jiaolong Series MRID6
- CPU: AMD Ryzen 7 7745HX, 8 cores / 16 logical processors
- RAM: 16,412,872,704 bytes (15.3 GiB reported by Windows)
- OS: 64-bit Windows 11, build 10.0.26200
- Python: 3.12.14
- NumPy: 2.5.3
- PySide6: 6.11.2

## Real-data reference validation

- The supplied DM3 is a calibrated `uint32` image with shape `(2048, 2048)`.
- The supplied DM4 is a calibrated `uint32` image with shape `(1024, 1024)`.
- DM shape, dtype, calibration, and three pixel locations per image match the
  local motif-learn `_dm_ncempy.py` reader at commit
  `fd1565605d96a380c6cc8061c8b573084c7b5915`.
- The supplied NPY stack is `float32` with shape `(8, 512, 512)`. All eight
  slices pass an exact, same-ROI batch-crop comparison in ascending axis-0
  order.
- Synthetic codec tests verify exact unnormalized `uint16` PNG round trips.
- File-backed constant and non-finite NPY tests verify safe display behavior,
  zero-valued constant normalization, and explicit rejection of non-finite
  normalization.

## Performance measurements

Command:

```powershell
& '.\.venv\python.exe' '.\tools\phase7_benchmark.py' `
  --data-dir 'D:\work\STEM image crop tool\test data' --repeat 5
```

The values below are local, warm-cache measurements and are not general
hardware guarantees. Durations are medians where applicable.

| Operation | Fixture | Result |
| --- | --- | ---: |
| Offscreen application startup | application | 424.9 ms |
| Open 2D NPY | `(430, 430)` float32 | 0.390 ms |
| Open DM3 | `(2048, 2048)` uint32 | 23.67 ms |
| Open DM4 | `(1024, 1024)` uint32 | 27.59 ms |
| Open NPY stack | `(8, 512, 512)` float32 | 0.380 ms |
| Lazy stack slice access | 64 accesses | 0.0024 ms/access |
| Slice display preparation | eight 512x512 slices | 2.95 ms/slice |
| Normalize and export full stack | eight 512x512 NPY outputs | 73.8 ms |

The batch produced 8,389,632 bytes of output. Process working set increased
from 61,243,392 to a sampled peak of 62,365,696 bytes (1,122,304-byte delta).
This is approximately one 512x512 float32 slice and does not scale with the
eight-slice output volume. An automated logical-stack test additionally checks
that no more than two generated source slices are alive at an iteration
boundary.

## Robustness coverage

Automated tests cover corrupted and truncated NPY/DM/raster inputs, invalid
destinations, overwrite conflicts, permission failure, simulated full disk,
encoder failure, cancellation, temporary-file cleanup, source mapping cleanup,
and GUI recovery after worker failure. Repeated UI/worker test runs are recorded
in `IMPLEMENTATION_PLAN.md`.

## Remaining external blocker

No real 3D DM stack is available. Synthetic tests exercise lazy 3D DM mapping,
slice selection, calibration, and batch behavior, but real DM stack slice order
and lazy access cannot be accepted from synthetic evidence alone. Phase 7 and
DM stack release readiness therefore remain explicitly incomplete until a real
3D fixture is validated.
