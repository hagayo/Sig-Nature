"""Build a 1.5-second WebM from 36 ordered image frames.

The image-generation stage must supply progressive pen positions. This module
does not infer handwriting stroke order from a finished signature.
"""

from pathlib import Path
import subprocess

FRAME_RATE = 24
DURATION_SECONDS = 1.5
FRAME_COUNT = int(FRAME_RATE * DURATION_SECONDS)


def encode_animation(frames_dir: Path, output: Path) -> Path:
    """Encode exactly 36 consecutively numbered PNG frames as WebM."""
    frames = sorted(frames_dir.glob("frame_*.png"))
    expected = [frames_dir / f"frame_{i:03d}.png" for i in range(FRAME_COUNT)]
    if frames != expected:
        missing = [str(path.name) for path in expected if not path.is_file()]
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
        "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "30",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output
