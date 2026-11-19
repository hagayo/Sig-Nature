"""Encode a curvature-timed signature as crisp browser-compatible H.264 MP4.

Duration is based on path complexity and writer tempo, not a fixed 1.5 seconds.
Each frame is a monotonic pen-path prefix, with 60 FPS and a clean final hold.
"""
from pathlib import Path
import subprocess

from backend.motion import FRAME_RATE


def encode_animation(
    frames_dir: Path,
    output: Path,
    *,
    frame_count: int | None = None,
    frame_rate: int = FRAME_RATE,
) -> Path:
    """Encode only an exact contiguous set of PNG frames, without rescaling."""
    if output.suffix.lower() != ".mp4":
        raise ValueError(f"Expected .mp4 output, got {output.name}")
    frames = sorted(frames_dir.glob("frame_*.png"))
    if frame_count is None:
        frame_count = len(frames)
    if frame_count < 2 or frame_count > 600:
        raise ValueError("Video frame count must be between 2 and 600")
    if frame_rate < 24 or frame_rate > 120:
        raise ValueError("Unsupported video frame rate")
    expected = [frames_dir / f"frame_{i:03d}.png" for i in range(frame_count)]
    if frames != expected:
        missing = [path.name for path in expected if not path.is_file()]
        extra = [path.name for path in frames if path not in expected]
        raise ValueError(
            f"Expected {frame_count} numbered frames in {frames_dir}; "
            f"missing={missing}; unexpected={extra}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(frame_rate),
        "-i", str(frames_dir / "frame_%03d.png"),
        "-frames:v", str(frame_count),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",
        "-tune", "animation",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output
