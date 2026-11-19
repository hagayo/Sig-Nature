"""Tests for the frame-to-MP4 encoder contract."""

from pathlib import Path
import subprocess

import pytest

from backend.animation import DURATION_SECONDS, FRAME_COUNT, FRAME_RATE, encode_animation


def test_timing_is_exact() -> None:
    assert FRAME_RATE == 24
    assert FRAME_COUNT == 36
    assert FRAME_COUNT / FRAME_RATE == DURATION_SECONDS == 1.5


def test_rejects_missing_frame(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="frame_000.png"):
        encode_animation(tmp_path, tmp_path / "result.mp4")


def test_rejects_wrong_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Expected .mp4"):
        encode_animation(tmp_path, tmp_path / "result.webm")


def test_encodes_numbered_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(FRAME_COUNT):
        (tmp_path / f"frame_{index:03d}.png").write_bytes(b"png")
    recorded: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded.append(command)
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    output = tmp_path / "result.mp4"
    assert encode_animation(tmp_path, output) == output
    command = recorded[0]
    assert command[command.index("-framerate") + 1] == "24"
    assert command[command.index("-frames:v") + 1] == "36"
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-movflags") + 1] == "+faststart"
