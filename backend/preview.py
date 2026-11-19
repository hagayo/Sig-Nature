"""Local end-to-end preview for the deterministic signature planner.

This preview uses only a name. Portrait-driven style selection and the
production OpenAI generation service are separate, unfinished features.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from backend.animation import encode_animation
from backend.pen_path import render_frames, render_signature
from backend.signature_planner import plan_signature


def generate_preview(\n    full_name: str, output_dir: Path, portrait: bytes = b""\n) -> tuple[Path, Path]:
    """Produce a transparent signature PNG and a 1.5-second H.264 MP4."""
    path = plan_signature(full_name, portrait=portrait)
    output_dir.mkdir(parents=True, exist_ok=True)
    png = render_signature(path, output_dir / "signature.png")
    mp4 = output_dir / "signature.mp4"
    with TemporaryDirectory(prefix="signature-frames-") as directory:
        frames = Path(directory)
        render_frames(path, frames)
        encode_animation(frames, mp4)
    return png, mp4
