"""Generate a photoreal macro writing clip locally, without an OpenAI API key.

Usage:
    python -m scripts.preview_cinema --name "חגי און" --style joyful
    python -m scripts.preview_cinema --name "Hagay Onn" --style calm

Requires FFmpeg/libx264 and the photographed macro materials committed to
backend/assets. Hebrew requires Gveret Levin (downloaded or installed).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from backend.cinematic_video import encode_cinematic_video, validate_cinematic_materials
from backend.pen_path import render_signature
from backend.portrait_analysis import PortraitStyle
from backend.signature_planner import plan_signature
from backend.style_mapping import style_from_portrait

STYLES: dict[str, PortraitStyle] = {
    "joyful": PortraitStyle(joy=1, cute=.8, playful=1, energy=.9),
    "bold": PortraitStyle(tough=1, tension=.9, confidence=1, dramatic=.8),
    "calm": PortraitStyle(calm=1, softness=.85, elegance=.8, tension=0),
    "mysterious": PortraitStyle(villainous=.9, dramatic=.9, elegance=.7),
}


def create_preview(name: str, output: Path, style_name: str) -> tuple[Path, Path]:
    """Write exactly the same generated ink path as PNG and photographic video."""
    validate_cinematic_materials()
    style = style_from_portrait(STYLES[style_name])
    path = plan_signature(name, style=style, portrait=style_name.encode())
    output.parent.mkdir(parents=True, exist_ok=True)
    png = render_signature(path, output.with_suffix(".png"))
    mp4 = encode_cinematic_video(path, output.with_suffix(".mp4"))
    return png, mp4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="חגי און", help="Hebrew or Latin full name")
    parser.add_argument("--style", choices=sorted(STYLES), default="joyful")
    parser.add_argument("--output", type=Path, default=Path("cinematic-signature.mp4"))
    args = parser.parse_args()
    png, mp4 = create_preview(args.name, args.output, args.style)
    print(png)
    print(mp4)


if __name__ == "__main__":
    main()
