"""Render the code-native SVG application icon as a multi-size Windows ICO."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


SIZES = (16, 24, 32, 48, 64, 128, 256)


def _render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"could not encode {size}x{size} icon image")
    return bytes(payload)


def build_icon(svg_path: Path, output_path: Path) -> None:
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise ValueError(f"invalid SVG icon source: {svg_path}")

    images = [(size, _render_png(renderer, size)) for size in SIZES]
    header_size = 6 + 16 * len(images)
    entries: list[bytes] = []
    payloads: list[bytes] = []
    offset = header_size
    for size, payload in images:
        encoded_size = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                encoded_size,
                encoded_size,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        payloads.append(payload)
        offset += len(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        struct.pack("<HHH", 0, 1, len(images))
        + b"".join(entries)
        + b"".join(payloads)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build_icon(args.svg, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
