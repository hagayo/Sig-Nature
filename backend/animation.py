"""Encode a continuous-pen signature animation as H.264 MP4.

Frame generation is separate: all 36 frames must depict successive prefixes
of one continuous pen path, never independent image generations.
"""

from pathlib import Path
import subprocess

FRAME_RATE = 24
DURATION_SECONDS = 1.5
FRAME_COUNT = int(FRAME_RATE * DURATION_SECONDS)


def encode_animation(frames_dir: Path, output: Path) -> Path:
    """Encode exactly 36 numbered PNG frames as a browser-compatible MP4."""
    if output.suffix.lower() != ".mp4":
        raise ValueError(f"Expected .mp4 output, got {output.name}")
    frames = sorted(frames_dir.glob("frame_*.png"))
    expected = [frames_dir / f"frame_{i:03d}.png" for i in range(FRAME_COUNT)]
    if frames != expected:
        missing = [path.name for path in expected if not path.is_file()]
        extra = [path.name for path in frames if path not in expected]
        raise ValueError(
            f"Expected {FRAME_COUNT} numbered frames in {frames_dir}; "
            f"missing={missing}; unexpected={extra}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(FRAME_RATE),
        "-i", str(frames_dir / "frame_%03d.png"),
        "-frames:v", str(FRAME_COUNT),
        "-vf", "scale=720:720:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output
