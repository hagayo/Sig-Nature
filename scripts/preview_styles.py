"""Generate a visual quality contact sheet without OpenAI keys or GitHub Actions.

Run: python -m scripts.preview_styles --name "חגי און"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from backend.pen_path import render_signature
from backend.portrait_analysis import PortraitStyle
from backend.signature_planner import plan_signature
from backend.style_mapping import style_from_portrait

STYLES = {
    "joyful": PortraitStyle(
        joy=1, playful=1, friendly=1, cute=.8, energy=1,
        sadness=0, tension=0, calm=.2,
    ),
    "solemn": PortraitStyle(
        joy=0, sadness=.9, shyness=.7, energy=.1,
        calm=.7, playful=0,
    ),
    "bold": PortraitStyle(
        tough=1, anger=.8, tension=.9, confidence=1,
        softness=.1, calm=0,
    ),
    "serene": PortraitStyle(
        calm=1, softness=1, elegance=.8, friendly=.7,
        tension=0, anger=0,
    ),
}


def create_contact_sheet(
    full_name: str, output: Path, *, font_path: str | None = None,
) -> Path:
    """Four distinct artistic signatures for the same name and fake photo cues."""
    if font_path:
        import os
        os.environ["SIG_NATURE_HEBREW_FONT"] = font_path
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (1400, 600), "#f7f8fa")
    draw = ImageDraw.Draw(sheet)
    for i, (label, cues) in enumerate(STYLES.items()):
        path = plan_signature(
            full_name, portrait=(f"visual-fixture:{label}").encode("utf-8"),
            style=style_from_portrait(cues),
        )
        png = output.parent / f"{label}.png"
        render_signature(path, png)
        with Image.open(png) as original:
            if original.getbbox() is None:
                raise RuntimeError(f"The {label} signature contains no visible ink")
            ink = original.crop(original.getbbox()).copy()
        ink.thumbnail((640, 225), Image.Resampling.LANCZOS)
        column, row = i % 2, i // 2
        left, top = column * 700, row * 300
        draw.rounded_rectangle(
            (left + 6, top + 6, left + 694, top + 294),
            radius=14, fill="white", outline="#dfe5ed",
        )
        draw.text((left + 30, top + 24), label, fill="#56627a")
        position = (left + (700 - ink.width) // 2,
                    top + 52 + (220 - ink.height) // 2)
        sheet.paste(ink, position, ink)
    sheet.save(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="חגי און")
    parser.add_argument("--output", type=Path, default=Path("signature-preview.png"))
    parser.add_argument("--font", default=None)
    args = parser.parse_args()
    print(create_contact_sheet(args.name, args.output, font_path=args.font))


if __name__ == "__main__":
    main()
