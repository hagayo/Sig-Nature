"""Produce one transparent signature PNG and one filmed-look macro MP4.

The photograph-like video tracks the same pen-down geometry as the PNG,
using an oblique moving macro camera and photo-derived ink/paper materials.
"""
from pathlib import Path

from backend.cinematic_video import encode_cinematic_video
from backend.pen_path import render_signature
from backend.signature_planner import plan_signature
from backend.style_mapping import WritingStyle


def generate_preview(
    full_name: str,
    output_dir: Path,
    portrait: bytes = b"",
    style: WritingStyle | None = None,
) -> tuple[Path, Path]:
    """No hand-drawn sprites or throwaway PNG frames are used in production."""
    path = plan_signature(full_name, portrait=portrait, style=style)
    output_dir.mkdir(parents=True, exist_ok=True)
    png = render_signature(path, output_dir / "signature.png")
    mp4 = encode_cinematic_video(path, output_dir / "signature.mp4")
    return png, mp4
