"""Render the design SVGs to PNG so they can be visually checked, and validate well-formedness."""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

DIAGRAMS = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
OUT = DIAGRAMS / "_preview"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    failures = 0
    for svg in sorted(DIAGRAMS.glob("*.svg")):
        try:
            ET.parse(svg)
        except ET.ParseError as exc:
            print(f"XML MALFORMED  {svg.name}: {exc}")
            failures += 1
            continue
        try:
            drawing = svg2rlg(str(svg))
            if drawing is None:
                raise ValueError("svglib returned no drawing")
            scale = min(1.0, 1100 / max(drawing.width, 1))
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
            renderPM.drawToFile(drawing, str(OUT / f"{svg.stem}.png"), fmt="PNG", dpi=110)
            print(f"ok  {svg.name:34s} {drawing.width:6.0f} x {drawing.height:6.0f}")
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            print(f"RENDER FAILED  {svg.name}: {type(exc).__name__}: {exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
