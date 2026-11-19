"""Generate a transparent PNG and an H.264 MP4 from exactly one pen path."""
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.animation import encode_animation
from backend.pen_path import render_frames, render_signature
from backend.signature_planner import plan_signature
from backend.style_mapping import WritingStyle


def generate_preview(
    full_name: str,
    output_dir: Path,
    portrait: bytes = b"",
    style: WritingStyle | None = None,
) -> tuple[Path, Path]:
    """Keep animation frame files temporary and never regenerate the path."""
    path = plan_signature(full_name, portrait=portrait, style=style)
    output_dir.mkdir(parents=True, exist_ok=True)
    png = render_signature(path, output_dir / "signature.png")
    mp4 = output_dir / "signature.mp4"
    with TemporaryDirectory(prefix="signature-frames-") as directory:
        frames = Path(directory)
        render_frames(path, frames)
        encode_animation(frames, mp4)
    return png, mp4
