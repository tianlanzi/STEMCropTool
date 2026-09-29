# STEMCropTool — Agent-Oriented Implementation Plan

## 1. Purpose

Build a cross-platform desktop application for exact rectangular cropping of grayscale STEM images and image stacks.

The implementation must proceed phase by phase. An agent working on a phase must finish that phase's tests and exit criteria before starting the next phase. Do not silently broaden the supported formats or add unrelated UI features.

Primary target:

- Windows desktop application distributed as a double-clickable executable/application directory.
- Shared source code that can also be built as a macOS `.app`.
- English-only UI for the initial release.

## 2. Authoritative product decisions

### 2.1 Supported inputs

- Grayscale PNG.
- Grayscale JPG/JPEG.
- `.npy` containing either:
  - a 2D image shaped `(Y, X)`, or
  - a 3D stack shaped `(Z, Y, X)`, where axis 0 is the slice axis.
- DM3 and DM4 containing a supported 2D image or 3D stack.
- Reject 1D arrays and every dataset whose declared dimensionality is greater than 3.
- Do not automatically `squeeze()` higher-dimensional data into an accepted shape. A declared 4D dataset remains unsupported even when one dimension has length 1.
- Reject color/multi-channel raster images rather than silently converting them to grayscale.
- NPZ is out of scope for the initial release.

### 2.2 Supported outputs

- PNG.
- NPY.
- Do not implement JPG, TIFF, NPZ, DM3, or DM4 export in the initial release.

### 2.3 Crop behavior

- Exactly one crop rectangle exists at a time.
- Drag to create a rectangle.
- Hold Shift while creating or resizing to constrain the rectangle to a square.
- The rectangle can be moved, resized, deleted, and recreated.
- Numeric inputs allow exact editing of `x`, `y`, `width`, and `height`.
- The UI displays at least `x`, `y`, `width`, and `height` continuously.
- All crop coordinates are integer source-pixel coordinates, independent of display zoom.
- Coordinate origin is the top-left pixel.
- Internally use half-open NumPy bounds:

  ```python
  crop = image[y0:y1, x0:x1]
  width = x1 - x0
  height = y1 - y0
  ```

- Clamp the ROI to image bounds and require a minimum size of `1 x 1` pixels.

### 2.4 View behavior

- Mouse-wheel zoom.
- Pan.
- Fit to window.
- 100% / actual-pixel display.
- Reset view.
- Zoom and display conversion must never modify the source array.
- Display contrast is a view-only mapping. For the initial release, map each displayed slice from its finite minimum/maximum to the display range. Constant slices display as black. Non-finite display pixels display as black. This mapping has no effect on export values.

### 2.5 Stack behavior

- A 3D array is interpreted as `(Z, Y, X)`.
- Provide a slider and/or spin box for selecting the current slice.
- Export choices for a stack:
  - current slice,
  - an inclusive user-selected slice range,
  - all slices.
- Batch export applies the same integer ROI to every selected slice.
- File loading and batch export must not run on the GUI thread.

### 2.6 Normalization contract

Normalization is optional and applies to the exported crop, not to the source array or display buffer.

- Scope: local to each exported crop.
- For stack batch export, normalize every crop independently.
- Convert to `float32` before computation.
- Require all crop values to be finite. If a selected crop contains NaN or infinity, normalized export fails with a clear error; do not silently replace values.
- Formula for a non-constant crop:

  ```python
  (crop - crop.min()) / (crop.max() - crop.min())
  ```

- A constant crop normalizes to all zeros.
- Normalized NPY output is `float32` in `[0, 1]`.
- Normalized PNG output is `uint8` in `[0, 255]`.
- UI help text must state that independently normalized stack slices are no longer quantitatively comparable. Users must disable normalization when original quantitative comparability is required.

### 2.7 Raw dtype contract

- Unnormalized NPY output preserves the input dtype exactly.
- Unnormalized PNG:
  - `uint8` remains 8-bit grayscale.
  - `uint16` remains 16-bit grayscale.
  - arbitrary float, signed integer, complex, boolean, and unsupported integer widths must not be silently rescaled or truncated. Require normalized PNG export or NPY instead.
- Complex arrays are unsupported for display/cropping in the initial release and must be rejected on load with a clear message.

### 2.8 Metadata contract

- DM inputs may provide `pixelSize`, `pixelUnit`, origins, and tags.
- Plain NPY, PNG, and JPG inputs must be treated as having no physical calibration unless a future, explicitly supported metadata mechanism provides it.
- A single export writes a same-stem JSON sidecar.
- A batch export writes one batch-level `manifest.json` rather than one JSON per slice.
- Metadata must include:
  - source filename, source format, source shape, and source dtype,
  - DM dataset index when applicable,
  - slice index when applicable,
  - crop rectangle as `x`, `y`, `width`, `height`,
  - normalization mode,
  - output filename, format, shape, and dtype,
  - spatial pixel size/unit when available,
  - physical crop size when calibration is available.
- Unknown calibration values must be `null`; never invent them.
- Store the source filename by default, not an absolute local path.

## 3. Technical direction

### 3.1 Runtime and dependencies

- Python 3.12 x64 is the required development, test, and packaging target for the initial release.
- Create a dedicated repository-local Conda prefix environment at `.venv`; do not install project dependencies into Conda `base` or the user's shared `version_3_12` environment.
- Preferred Windows bootstrap command, run from the repository root:

  ```powershell
  conda create --prefix .\.venv python=3.12 pip -y
  ```

- After creation, invoke tools through explicit paths whenever practical. On Windows the project interpreter is `.venv\python.exe`; on macOS it is `.venv/bin/python`.
- Do not depend on activation state for scripted tests or packaging. For example, use `.venv\python.exe -m pytest` and `.venv\python.exe -m PyInstaller ...` on Windows.
- The shared `version_3_12` environment may be inspected to confirm the intended Python family, but it is not the project runtime and must not be modified for this project.
- Runtime dependency target:
  - PySide6,
  - NumPy.
- Development dependencies should include at least:
  - pytest,
  - pytest-qt,
  - PyInstaller.
- Use Qt raster codecs first. Add Pillow only if round-trip tests show that Qt cannot reliably meet the grayscale PNG/JPG and `uint16` PNG requirements. Do not add scikit-image, SciPy, scikit-learn, matplotlib, or the `motif-learn` package.
- Pin tested dependency versions in project metadata before the first release.

### 3.2 Architectural boundary

The numerical core must be independent of Qt. Qt-specific raster codecs belong in an infrastructure/adapters layer rather than in the numerical core.

Target structure:

```text
STEMCropTool/
├── pyproject.toml
├── README.md
├── IMPLEMENTATION_PLAN.md
├── THIRD_PARTY_NOTICES.md
├── licenses/
├── src/
│   └── stem_crop_tool/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── core/
│       │   ├── models.py
│       │   ├── crop.py
│       │   ├── normalize.py
│       │   ├── batch.py
│       │   ├── metadata.py
│       │   └── readers/
│       │       ├── base.py
│       │       ├── npy.py
│       │       └── dm.py
│       ├── infrastructure/
│       │   ├── raster_io.py
│       │   ├── exporters.py
│       │   └── atomic_write.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── image_view.py
│       │   ├── crop_item.py
│       │   ├── stack_controls.py
│       │   ├── export_dialog.py
│       │   └── workers.py
│       └── vendor/
│           └── ncempy_dm.py
├── tests/
│   ├── core/
│   ├── infrastructure/
│   ├── ui/
│   ├── integration/
│   └── fixtures/
├── packaging/
│   ├── pyinstaller/
│   ├── windows/
│   └── macos/
└── scripts/
```

The exact number of modules may be adjusted, but these boundaries must be preserved:

- `core/` cannot import PySide6.
- `ui/` cannot implement crop math, normalization, file parsing, or export encoding.
- Vendored code is accessed through `core/readers/dm.py`; the rest of the application must not import the vendor module directly.
- Long-running operations expose progress and cancellation independently of Qt, then `ui/workers.py` adapts them to Qt signals/threads.

### 3.3 Image source abstraction

Define a small reader/source protocol before implementing concrete readers. It should expose the equivalent of:

```python
shape: tuple[int, ...]
dtype: np.dtype
ndim: int
metadata: ImageMetadata
slice_count: int

get_slice(index: int = 0) -> np.ndarray
close() -> None
```

Requirements:

- A 2D source reports `slice_count == 1`.
- A 3D source returns one `(Y, X)` slice without materializing the whole stack.
- NPY stacks use `numpy.load(..., mmap_mode="r", allow_pickle=False)`.
- DM stacks use the vendored reader's memory-mapped access.
- The document/source owns resource lifetime and closes the previous source when another file is opened.
- Loading errors use application exceptions with user-facing messages; raw tracebacks stay in logs/tests, not modal UI text.

### 3.4 DM reader policy

- Do not depend on `motif-learn` at runtime.
- Do not use `mtflearn/io/_dm4.py`.
- Vendor the `ncempy.io.dm`-derived single-file reader used by the local `motif-learn` project, after recording exact provenance.
- Reference source available during development:
  `C:\Users\Joseph\Documents\GitHub\motif-learn\mtflearn\io\_dm_ncempy.py`
- Before copying:
  - compare the local copy with a pinned upstream openNCEM `ncempy/io/dm.py` revision,
  - record upstream URL and commit in the vendored file header,
  - record local modifications separately.
- Use the MIT option provided for `ncempy/io`, retain copyright/permission text, and include the license in `licenses/` and `THIRD_PARTY_NOTICES.md`.
- Apply and test the destructor safety fix: construction failure before `fid` exists must not raise a second exception from `__del__()`.
- Prefer explicit context management over destructor-driven cleanup.
- Do not call the convenience `dmReader()` for a large stack if it materializes the full dataset. The application adapter must use `fileDM`/`getMemmap()` and read metadata separately.
- Determine supported dimensionality from the DM dataset declaration, not from a memmap shape after singleton dimensions were removed.
- Skip recognized RGB thumbnails.
- If a DM file contains multiple non-thumbnail datasets:
  - expose them from the reader adapter,
  - automatically open the only supported dataset when there is exactly one,
  - show a simple dataset selector when multiple supported 2D/3D datasets exist,
  - show a clear error when none are supported.

### 3.5 Threading policy

- Never manipulate widgets outside the GUI thread.
- Run file parsing/opening and batch export in worker objects on Qt-managed threads.
- The pure batch core must support:
  - progress callbacks/events,
  - cooperative cancellation between slices,
  - deterministic output ordering,
  - cleanup of temporary/incomplete files after cancellation or failure.
- Disable conflicting UI actions while a load/export operation is active.
- Cancellation must leave already completed files valid and identify them in the result; incomplete current-file output must be removed.

## 4. Agent execution protocol

Every implementation agent must follow this protocol:

1. Read this whole document and inspect the repository state.
2. Work on only the first incomplete phase unless the user explicitly selects another phase.
3. Preserve unrelated user changes and inspect `git status` before editing.
4. Do not install or add dependencies outside the phase's scope.
5. Add or update automated tests in the same phase as the behavior they cover.
6. Run the phase-specific tests plus all earlier tests.
7. Update the phase checklist/status in this document only when every exit criterion is satisfied.
8. Report:
   - files changed,
   - commands/tests run and their results,
   - remaining risks or missing external fixtures,
   - the next phase, without starting it.
9. Do not create commits, tags, releases, or publish artifacts unless the user explicitly asks.
10. Do not mark DM support complete without testing user-provided real DM3/DM4 fixtures.

## 5. Implementation phases

### Phase 0 — Repository bootstrap and early packaging spike

**Status:** Complete (2026-09-29)

**Completion evidence:**

- Created a repository-local Conda prefix using 64-bit Python 3.12.14.
- Installed and validated NumPy 2.5.3, PySide6 6.11.2, pytest 9.1.1,
  pytest-qt 4.5.0, and PyInstaller 6.22.3 without modifying the shared
  `version_3_12` environment.
- Source test suite: `2 passed`.
- Bounded `python -m stem_crop_tool` Qt event-loop smoke check: exit code 0.
- PyInstaller `--onedir` build completed successfully.
- Bounded packaged `STEMCropTool.exe` Qt event-loop smoke check: exit code 0.
- `pip check`: no broken requirements.

**Goal:** Establish a reproducible project skeleton and prove that a minimal PySide6 + NumPy application can be packaged early.

**Tasks:**

- Add `pyproject.toml` using a `src/` layout.
- Set the supported Python version and define runtime/development dependency groups.
- Add `.gitignore` for `.venv`, build, test, cache, and packaging outputs.
- Create the package skeleton and a minimal `python -m stem_crop_tool` entry point.
- Create an empty main window that opens and exits cleanly.
- Add pytest configuration and one import/smoke test.
- Add initial `THIRD_PARTY_NOTICES.md` and `licenses/` placeholders with an explicit checklist; do not claim completeness yet.
- Create the dedicated local Conda prefix `.venv` with Python 3.12 using the command in Section 3.1. Do not reuse or modify the user's shared `version_3_12` environment. If an exact Python 3.12 environment cannot be created, stop and report rather than silently choosing Python 3.11, 3.13, Conda `base`, or another interpreter.
- Build a Windows PyInstaller `--onedir` smoke artifact and launch it manually or through a bounded smoke check.
- Record the initial packaging command/spec under `packaging/pyinstaller/`.

**Tests:**

- Package imports successfully.
- `python -m stem_crop_tool` opens a window.
- Window can be closed without a traceback.
- PyInstaller `--onedir` output starts on the development Windows machine.

**Exit criteria:**

- Reproducible setup commands are documented.
- The minimal source application and packaged application both launch.
- No scientific file handling or custom crop UI has been added yet.

### Phase 1 — Pure core contracts, crop math, and normalization

**Status:** Complete (2026-09-29)

**Completion evidence:**

- Added immutable crop, metadata, normalization, export request, and export
  result value models.
- Added bounded drag creation in every direction, clamping, translation,
  resizing, square constraints, exact half-open slicing, and 2D crop extraction.
- Added strict local min-max normalization with `float32` output, constant-crop
  zero behavior, source immutability, and explicit NaN/Inf rejection.
- Added raw/normalized PNG and NPY dtype decision rules without file I/O.
- Added application-specific core exceptions.
- Added a static architecture test proving `core/` has no PySide6 imports.
- Full cumulative test suite: `72 passed` on Python 3.12.14.
- `compileall` succeeded and `pip check` reported no broken requirements.

**Goal:** Implement and fully test all coordinate, dtype, crop, and normalization rules without Qt.

**Tasks:**

- Define immutable/value-oriented models for:
  - integer crop rectangle,
  - image metadata,
  - normalization mode,
  - export request/result.
- Implement ROI validation, clamping, translation, resizing helpers, and square constraint math.
- Implement array crop extraction using half-open bounds.
- Implement strict local min-max normalization.
- Implement output dtype decision rules without performing file I/O.
- Define application-specific exceptions for unsupported dimensions, dtype, non-finite normalization, and invalid ROI.

**Tests:**

- ROI creation in every drag direction.
- Clamp at all four image edges.
- Move/resize behavior and minimum `1 x 1` size.
- Square constraint near edges.
- Exact agreement between reported width/height and NumPy slice shape.
- Normal integer and float normalization.
- Negative-valued data.
- Constant crop produces zeros.
- NaN/Inf normalized crop fails clearly.
- Raw NPY dtype decision preserves dtype.
- Unsupported PNG dtype decisions fail instead of truncating.

**Exit criteria:**

- `core/` has no PySide6 import.
- Core unit tests cover coordinate and normalization edge cases.
- No file reader, exporter, or UI code is mixed into these modules.

### Phase 2 — Reader layer and source metadata

**Status:** Complete (2026-09-29)

**Completion evidence:**

- Added a Qt-independent `ImageSource` protocol and `ImageDocument` lifecycle
  owner that preserves the current source when a replacement fails to open.
- Added read-only, memory-mapped NPY sources for exact 2D and `(Z,Y,X)` 3D
  data, with `allow_pickle=False`, dtype preservation, and explicit rejection
  of 1D, declared 4D (including singleton 4D), complex, and non-numeric data.
- Added Qt-codec raster sources for grayscale/indexed-grayscale PNG and
  grayscale JPEG, with exact `uint8`/`uint16` PNG round trips and explicit
  RGB/RGBA rejection.
- Vendored the single-file openNCEM/ncempy DM parser from the local
  motif-learn source, recorded the exact upstream/local commits and local
  modifications, selected the upstream MIT option, and bundled its license.
- Fixed partial-construction cleanup, raw-index bounds, thumbnail-aware
  logical dataset indexing, and singleton-dimension preservation in DM
  memory maps.
- Added DM dataset enumeration, thumbnail exclusion, supported-dataset
  selection, declared-dimension validation, lazy slice access, calibration
  extraction, and read-only access to parsed tags.
- Validated the user-provided real 2D DM3 (`2048 x 2048`, `uint32`) and DM4
  (`1024 x 1024`, `uint32`) samples, including thumbnail skipping and `nm`
  calibration. Real 3D DM validation remains deferred because no fixture is
  currently available.
- Full cumulative suite with external real-data tests: `108 passed` on Python
  3.12.14. Without external fixtures, the same suite skips only the opt-in
  real-DM integration test.
- `compileall` succeeded and `pip check` reported no broken requirements.

**Goal:** Open every supported input through a common lazy source interface while preserving dtype and dimensionality.

**Tasks:**

- Implement the source protocol and document/resource lifecycle.
- Implement NPY reader:
  - `allow_pickle=False`,
  - memory mapping,
  - exact 2D/3D validation,
  - axis 0 slice access,
  - rejection of complex and >3D arrays.
- Implement grayscale raster reader using Qt codecs in `infrastructure/` while returning NumPy data to the document layer.
- Validate grayscale rather than silently converting RGB/RGBA.
- Test 8-bit and 16-bit PNG value preservation.
- Test grayscale JPG dimensions and dtype expectations, allowing for JPEG's inherent lossy pixel values.
- Vendor and attribute the DM reader according to Section 3.4.
- Add the safe destructor/resource fix with a focused regression test.
- Implement the DM adapter with dataset enumeration, thumbnail exclusion, dimension validation, lazy/memory-mapped slice access, and calibration extraction.
- Ensure a 4D dataset with a singleton dimension is still rejected.

**Tests/fixtures:**

- Generate synthetic NPY fixtures for 2D, 3D, 1D, 4D, complex, `uint8`, `uint16`, signed integer, and float data.
- Generate small grayscale PNG/JPG fixtures and color-image rejection fixtures.
- Round-trip `uint8` and `uint16` PNG through the chosen codec and compare values exactly for PNG.
- Test source closing/reopening and failure cleanup.
- Test malformed files and unsupported extensions.
- Add DM tests using the user-provided real samples when available.

**Exit criteria:**

- NPY and raster acceptance tests pass.
- DM code is isolated behind the adapter and license/provenance files exist.
- DM support remains explicitly marked provisional if real DM3/DM4 samples have not yet been supplied and tested.
- Opening a 3D stack does not load the entire stack into a normal in-memory ndarray.

### Phase 3 — Export engine and metadata sidecars

**Status:** Complete (2026-09-29)

**Completion evidence:**

- Added Qt-independent current/range/all slice selection, deterministic
  default naming, thread-safe cooperative cancellation, and immutable progress
  records.
- Added a streaming export engine that reads, crops, normalizes, and writes one
  slice at a time rather than collecting a stack of crops in memory.
- Added raw and locally normalized NPY export. Raw output preserves dtype and
  values (including non-native endian dtype); normalized output is `float32`.
- Added exact raw `uint8`/`uint16` PNG export and rounded normalized `uint8`
  PNG export. Non-native endian `uint16` values are converted to native storage
  without changing pixel values; forbidden raw PNG dtypes fail before writing.
- Added same-stem JSON sidecars for single exports and one `manifest.json` for
  batches, including source, crop, normalization, output, slice, dataset, and
  spatial/physical-size metadata without absolute source-path leakage.
- Added same-directory atomic temporary writes, preflight collision checks,
  explicit overwrite policy, deterministic progress callbacks, cancellation
  manifests, and incomplete-current-file cleanup on failure.
- Added an end-to-end test from a memory-mapped NPY stack through ordered batch
  outputs and manifest validation.
- Full cumulative suite with external real-DM tests: `138 passed` on Python
  3.12.14. Without external fixtures, only the opt-in real-DM integration test
  is skipped.
- `compileall` succeeded and `pip check` reported no broken requirements.

**Goal:** Produce scientifically predictable PNG/NPY outputs and JSON metadata without a GUI.

**Tasks:**

- Implement single-crop export from an `ImageSource` and `ExportRequest`.
- Implement current-slice, inclusive range, and all-slice batch iteration.
- Implement raw and normalized NPY export.
- Implement raw `uint8`/`uint16` and normalized `uint8` PNG export.
- Implement automatic names:
  - suggested single name: `<source_stem>_crop.<ext>`,
  - batch item name: `<source_stem>_z0000_crop.<ext>`, with zero padding derived from stack size.
- Let the UI eventually override the single filename and select the batch directory.
- Never overwrite an existing file without explicit user confirmation supplied by the caller.
- Use atomic writes where practical: write a temporary file in the destination directory, close/flush it, then replace/rename.
- Implement single JSON sidecar and batch manifest schemas.
- Compute physical crop size only when valid spatial calibration exists.
- Implement deterministic progress and cooperative cancellation hooks.

**Tests:**

- NPY raw dtype and values exactly match the crop.
- Normalized NPY is `float32 [0,1]`.
- PNG output dimensions and pixel values are correct.
- `uint16` raw PNG round-trips without down-conversion.
- Batch range boundaries are correct and filenames sort in slice order.
- JSON/manifest content matches actual output files.
- No absolute source path leaks into default metadata.
- Existing-file policy is respected.
- Simulated cancellation/failure removes incomplete temporary output.

**Exit criteria:**

- The export engine can be exercised entirely from tests without constructing a Qt window.
- All format/dtype rules in Section 2 are enforced.
- Batch export is streaming; it does not first collect all cropped slices in memory.

### Phase 4 — Main window, image display, and stack navigation

**Status:** Complete (2026-09-29)

**Completion evidence:**

- Replaced the bootstrap shell with an English main window containing exact
  input filters, menus, toolbar, status/busy feedback, view controls, disabled
  future crop/export placeholders, and 2D-aware stack controls.
- Added worker-thread source opening with GUI-thread-only state changes,
  last-request-wins handling for overlapping requests, deterministic thread
  cleanup, concise user errors, and preservation of the current document after
  a failed replacement.
- Added multiple-DM-dataset selection and verified the supplied real 2D DM3 and
  DM4 files open through the GUI. Real 3D DM validation remains intentionally
  deferred to Phase 7 because no such fixture is currently available.
- Added an independently owned finite-min/max `uint8` display buffer and a
  detached grayscale `QImage` with explicit stride. Constant and non-finite
  display pixels are black; source arrays remain unchanged.
- Added middle-button pan, wheel/programmatic zoom, fit, actual-pixel 100%,
  reset, and transform-preserving lazy stack navigation.
- Full cumulative suite with external real data: `154 passed` on Python
  3.12.14. Without external data: `152 passed, 2 skipped`.
- The UI suite passed 10 consecutive runs (`12 passed` per run) after hardening
  Qt thread ownership and GUI-thread cleanup. Source launch smoke test,
  `compileall`, and `pip check` also passed.

**Goal:** Provide a stable desktop shell that opens supported data and displays an exact selected slice.

**Tasks:**

- Build the English main window, menu/toolbar, status area, and central image view.
- Implement Open File with the exact supported extension filters.
- Run file parsing/opening through a worker and show non-blocking progress/busy state.
- Add DM dataset selection when needed.
- Implement safe NumPy-to-QImage conversion with explicit lifetime ownership, byte order, and row-stride handling.
- Keep the source array untouched; construct a separate display buffer.
- Add zoom, pan, fit-to-window, 100%, and reset actions.
- Add stack slider/spin box and current/total slice indicator for 3D sources.
- Hide or disable stack controls for 2D sources.
- Close the old source only after a new source opens successfully, or otherwise leave the current document usable.
- Present concise user errors without exposing raw tracebacks.

**Tests:**

- GUI opens/closes under pytest-qt.
- Open valid 2D and 3D sources.
- Switch stack slices and verify displayed source indices.
- 100% maps one source pixel to one logical image pixel before device scaling considerations.
- Zoom/pan do not alter source values or current slice.
- Failed open does not destroy the existing valid document.
- Rapid repeated open actions do not leave orphan workers/resources.

**Exit criteria:**

- All supported sources that passed Phase 2 can be opened through the GUI.
- Large-stack slice navigation uses lazy access.
- The GUI remains responsive during file parsing.
- No crop rectangle or export workflow is implemented yet beyond disabled placeholders.

### Phase 5 — Interactive ROI and exact numeric editing

**Status:** Complete (2026-09-29)

**Completion evidence:**

- Added a single permanent crop graphics item with a visible border,
  translucent fill, and eight resize handles that remain a fixed screen size
  across zoom levels.
- Added deterministic nearest-pixel-boundary snapping and mouse creation in
  every drag direction, bounded movement, edge/corner resizing, middle-button
  pan coexistence, and Shift-constrained square creation/resizing.
- Kept all crop calculations in the Qt-independent core through `CropRect`,
  `ResizeHandle`, numeric-field clamping, translation, and handle-resize
  helpers; the UI contains no competing fractional ROI state.
- Added synchronized zero-based `x`, `y`, `width`, and `height` controls plus
  New Crop, Clear Crop, and Delete-key behavior. File replacement clears the
  ROI, while stack slice changes retain it exactly.
- Added an integration contract test proving the graphics item, numeric panel,
  NumPy crop, and JSON metadata all consume the same `CropRect` values.
- Full cumulative suite with supplied real DM3/DM4 fixtures: `179 passed` on
  Python 3.12.14. Without external data: `177 passed, 2 skipped`.
- The expanded UI suite passed 10 consecutive runs (`22 passed` per run), and
  a visual smoke check with the supplied `(8, 512, 512)` stack confirmed the
  crop overlay, handles, stack navigation, and numeric panel layout.

**Goal:** Implement one pixel-exact crop rectangle whose mouse and numeric representations always agree.

**Tasks:**

- Implement the custom crop graphics item with visible border and resize handles.
- Create by drag in every direction.
- Move and resize inside image bounds.
- Constrain creation and resize to a square while Shift is held.
- Add delete/clear/recreate actions.
- Add synchronized integer fields for `x`, `y`, `width`, and `height`.
- Show current coordinates/sizes in an appropriate panel/status area.
- Convert scene coordinates to source integer pixel boundaries through one tested conversion path.
- Define deterministic rounding/snap behavior; do not allow fractional source ROI state.
- Keep the same ROI when switching stack slices because every slice shares `(Y, X)`.
- Disable export when no valid ROI exists.

**Tests:**

- Mouse-created ROI matches the core rectangle exactly at multiple zoom levels.
- Reverse-direction dragging is normalized correctly.
- Moving/resizing at every edge stays in bounds.
- Shift produces equal width and height near image boundaries.
- Numeric editing updates graphics and graphics updates numeric fields without feedback loops.
- Delete and file reopen clear/reset ROI appropriately.
- Slice changes retain the same ROI.

**Exit criteria:**

- The displayed ROI, numeric controls, JSON coordinates, and actual NumPy crop use the same integer rectangle.
- Automated tests cover zoom-independent coordinate mapping.
- There is never more than one ROI.

### Phase 6 — Export UI, background batch processing, progress, and cancellation

**Status:** Not started

**Goal:** Connect the tested export engine to the UI without blocking the event loop.

**Tasks:**

- Implement the export dialog/panel:
  - PNG or NPY,
  - normalization checkbox,
  - current slice/range/all for stacks,
  - target file for single export,
  - target directory for batch export.
- Display dtype consequences before confirmation where useful.
- Reject unsupported raw PNG dtypes with an actionable message.
- Execute exports through worker threads.
- Add progress count/percentage, current slice, cancel button, success summary, and failure summary.
- Prevent document/ROI mutation that would invalidate an active batch request, or snapshot the immutable request before starting.
- Ensure GUI objects are touched only on the GUI thread.
- Surface completed outputs after cancellation without claiming the whole batch succeeded.

**Tests:**

- Single 2D export through UI.
- Current-slice 3D export.
- Range and all-slice export.
- UI remains responsive during an intentionally slowed batch.
- Cancellation works between slices and cleans partial current output.
- Export uses the ROI snapshot from job start.
- Worker errors restore enabled UI state and leave the app usable.

**Exit criteria:**

- All user-requested workflows are accessible in the UI.
- A large simulated batch does not freeze the GUI.
- Export results match Phase 3 core tests exactly.

### Phase 7 — Real-data validation, performance, and robustness

**Status:** Not started

**Goal:** Validate the complete application against representative STEM data and harden failure paths.

**Tasks:**

- Add the user-provided test-data inventory without committing private/large samples unless explicitly authorized.
- Prefer checksums and a local fixture-location convention for uncommitted samples.
- Test at minimum when samples are available:
  - one 2D DM3,
  - one 2D DM4,
  - one 3D DM stack (currently unavailable; keep 3D DM support provisional until a real fixture is tested),
  - calibrated data with pixel size/unit,
  - one representative NPY stack (the current normal workload is `(8, 512, 512)`),
  - `uint16` PNG,
  - constant and non-finite NPY edge cases.
- Compare DM shape, dtype, selected pixel values, slice order, and calibration against a trusted reference such as the existing `motif-learn` reader behavior.
- Measure startup, file-open, slice-switch, and batch memory behavior.
- Verify batch processing remains bounded-memory.
- Harden corrupted/truncated file errors, permission errors, full disk/write failure, invalid destinations, and stale memmap/resource cleanup.
- Review all dialogs/messages for clear English wording.
- Run the complete automated suite repeatedly and address flaky threading/UI tests.

**Performance targets:**

- Switching an already indexed local stack slice should feel interactive and must not read the full stack.
- Batch memory use should be approximately bounded by the source mapping, one source slice/crop, one output buffer, and display/UI buffers—not stack length times slice size.
- No target may be claimed without recording the hardware and fixture used.

**Exit criteria:**

- Real DM3 and DM4 fixtures pass documented validation.
- A real 3D DM stack passes slice-order, lazy-access, and batch-crop validation. Until such a fixture is available, Phase 7 remains incomplete for 3D DM support even though Phase 2 development may proceed.
- No known dtype down-conversion or off-by-one crop bug remains.
- Resource, cancellation, and write-failure paths have tests.
- If real DM fixtures are still unavailable, this phase cannot be marked complete and DM support cannot be advertised as release-ready.

### Phase 8 — Windows release packaging

**Status:** Not started

**Goal:** Produce a reproducible Windows release candidate that runs without a separately installed Python.

**Tasks:**

- Finalize the PyInstaller `--onedir` spec.
- Include only required Qt modules/plugins and application resources.
- Include license texts and `THIRD_PARTY_NOTICES.md` in the distribution.
- Ensure Qt remains dynamically linked as separate libraries in the distribution.
- Add version metadata and application icon.
- Test on a clean Windows machine/VM without the development environment.
- Smoke-test every input/output format and one batch export from the packaged build.
- Measure artifact size and startup time.
- Optionally compare `pyside6-deploy`/Nuitka only after the PyInstaller build is reliable. Do not switch packagers merely for a smaller file without repeating the full packaged-app test matrix.
- Add an installer only after the portable `onedir` artifact works. Inno Setup is an acceptable later choice.

**Exit criteria:**

- Clean-machine packaged tests pass.
- Distribution contains required notices/licenses.
- The release artifact and build instructions are reproducible.
- No `--onefile` requirement is imposed for the initial release.

### Phase 9 — macOS build, signing path, and cross-platform release checks

**Status:** Not started

**Goal:** Produce and validate a macOS `.app` from the same source tree.

**Tasks:**

- Build on macOS hardware or a macOS CI runner; do not attempt to create the `.app` on Windows.
- Create the macOS PyInstaller spec/configuration and application icon.
- Run core, integration, and GUI smoke tests on macOS.
- Validate file dialogs, keyboard modifiers, wheel/trackpad zoom, high-DPI behavior, and application lifecycle conventions.
- Test DM/NPY memory mapping and cleanup on macOS.
- Document Apple signing and notarization requirements.
- For public external distribution, sign and notarize the `.app`/DMG using user-provided Apple credentials; never store credentials in the repository.
- Add CI jobs for Windows and macOS tests/builds when the user chooses a CI provider and authorizes repository workflow changes.

**Exit criteria:**

- The `.app` launches on a clean supported macOS system.
- Core file/crop/export workflows pass on both Windows and macOS.
- Public distribution is not claimed until signing/notarization succeeds when required.

## 6. Required test matrix

The following matrix is cumulative. A later phase must not regress earlier rows.

| Area | Required cases |
|---|---|
| Dimensions | 1D reject, 2D accept, 3D `(Z,Y,X)` accept, 4D reject, singleton-4D reject |
| Dtypes | `uint8`, `uint16`, signed integer, `float32`, `float64`, complex reject |
| Values | negative, constant, NaN, `+inf`, `-inf`, high dynamic range |
| Raster | grayscale PNG 8-bit, PNG 16-bit, grayscale JPG, RGB/RGBA reject |
| NPY | 2D, 3D memmap, `allow_pickle=False`, malformed/truncated |
| DM | DM3 2D, DM4 2D, 3D stack, thumbnail skip, calibration, multiple datasets, >3D reject |
| ROI | every drag direction, bounds, minimum size, move, resize, Shift-square, numeric edit |
| View | zoom, pan, fit, 100%, reset, high DPI, slice switch |
| Export | raw/normalized NPY, raw 8/16-bit PNG, normalized PNG, invalid raw PNG dtype |
| Batch | current/range/all, naming, order, progress, cancellation, failure cleanup |
| Metadata | crop coordinates, slice index, dtype, normalization, calibration, null unknowns |
| Packaging | source run, PyInstaller run, clean Windows, clean macOS |

## 7. Release-blocking invariants

The application is not release-ready if any of the following is false:

- The exported crop equals `source[y:y+height, x:x+width]` exactly before optional normalization.
- View zoom/pan never changes crop coordinates or source data.
- Raw NPY preserves dtype and values.
- Raw `uint16` PNG has passed exact round-trip tests.
- 3D stacks are processed lazily and batch export is bounded-memory.
- Batch work does not freeze the GUI.
- 4D data is rejected based on declared dimensionality.
- DM license attribution and Qt/NumPy notices are included.
- Real DM3/DM4 samples have been validated.
- Packaged builds have been tested outside the development environment.

## 8. Explicit non-goals for the initial release

- NPZ input/output.
- TIFF input/output.
- Color images or automatic RGB-to-grayscale conversion.
- 4D STEM datasets.
- Multiple simultaneous ROIs.
- Brightness/contrast editing controls or scientific intensity processing beyond view-only mapping.
- Image rotation, resampling, filtering, denoising, or annotation.
- Automatic updates.
- Cloud storage or collaboration.
- CLI, plugin system, localization, dark-mode customization, recent-files list, undo/redo, and session restoration.

The architecture should not prevent a future CLI, but the initial release does not implement one.

## 9. Open external inputs

The implementation can begin before these arrive, but the corresponding phases cannot be fully accepted without them. Current fixture status:

- Representative NPY, 2D DM3, and 2D DM4 files have been supplied and used in
  Phase 2. Representative real PNG/JPG samples remain optional external inputs
  for Phase 7 because deterministic synthetic codec fixtures already cover
  their Phase 2 contracts.
- A representative `(8, 512, 512)` NPY stack has been supplied for the normal
  workload; larger synthetic stacks may be generated for optional stress tests.
- Existing 2D DM expectations were cross-checked against the local motif-learn
  reader; any future DM fixture must likewise include or derive a trusted
  shape/dtype/calibration reference.
- A real 3D DM stack is not currently available. This does not block Phase 2, but 3D DM support must remain explicitly unverified and cannot be advertised as release-ready until Phase 7 validates one.
- macOS build access for Phase 9.
- Apple signing credentials only if public notarized macOS distribution is requested.
