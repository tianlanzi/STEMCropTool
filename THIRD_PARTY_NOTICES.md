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

## Vendored source

- [x] The DM3/DM4 parser in `src/stem_crop_tool/vendor/ncempy_dm.py` is
      adapted from the MIT-licensed `ncempy/io/dm.py` implementation in
      openNCEM. The vendored header records the exact upstream comparison
      commit, the immediate motif-learn source commit, and local modifications.
      The selected MIT text is in `licenses/NCEMPY_IO_MIT.txt`.

Upstream project: https://github.com/ercius/openNCEM
