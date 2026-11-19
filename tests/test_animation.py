"""Tests for adaptive frame-count MP4 encoding and quality settings."""
from pathlib import Path
import subprocess

import pytest

from backend.animation import encode_animation
from backend.motion import FRAME_RATE


def test_output_rate_is_smooth() -> None:
    assert FRAME_RATE == 60


def test_rejects_missing_frame(tmp_path: Path) -> None:
    for i in [0,2]:
        (tmp_path / f"frame_{i:03d}.png").write_bytes(b"png")
    with pytest.raises(ValueError, match="frame_001.png"):
        encode_animation(tmp_path, tmp_path / "result.mp4", frame_count=3)


def test_rejects_wrong_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Expected .mp4"):
        encode_animation(tmp_path, tmp_path / "result.webm")


def test_encodes_dynamic_number_of_frames(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    count = 149
    for index in range(count):
        (tmp_path / f"frame_{index:03d}.png").write_bytes(b"png")
    recorded: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded.append(command)
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    output = tmp_path / "result.mp4"
    assert encode_animation(tmp_path, output, frame_count=count) == output
    command = recorded[0]
    assert command[command.index("-framerate")+1] == "60"
    assert command[command.index("-frames:v")+1] == str(count)
    assert command[command.index("-c:v")+1] == "libx264"
    assert command[command.index("-crf")+1] == "17"
    assert command[command.index("-preset")+1] == "slow"
    assert command[command.index("-movflags")+1] == "+faststart"
    assert "yuv420p" in command


@pytest.mark.parametrize("count", [0,1,601])
def test_invalid_frame_counts(tmp_path: Path, count: int) -> None:
    with pytest.raises(ValueError, match="frame count"):
        encode_animation(tmp_path, tmp_path / "result.mp4", frame_count=count)
