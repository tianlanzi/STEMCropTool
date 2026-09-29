# Third-Party Notices

This file is an initial Phase 0 checklist, not a complete release notice. The
final distribution must include the license texts and attributions for every
component actually shipped.

## Runtime components to verify before release

- [ ] Python runtime and standard library license.
- [ ] PySide6 license and required Qt notices (LGPLv3/GPL/commercial choice to
      be handled according to the selected distribution terms).
- [ ] Qt module and bundled third-party notices for the modules actually
      shipped.
- [ ] NumPy license and licenses for binaries bundled in the selected NumPy
      wheel.

## Development/build components to verify before release

- [ ] PyInstaller license and bootloader notices, if applicable to the shipped
      artifact.
- [ ] pytest and pytest-qt are development-only and should not be bundled.

## Future vendored source

- [ ] The Phase 2 DM reader must record its exact openNCEM/ncempy provenance,
      modifications, copyright statement, and MIT license text.

No vendored DM reader or scientific file-format code is present in Phase 0.
