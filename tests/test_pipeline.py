"""Local integration test: real FFmpeg, mocked portrait analysis, no API credits."""
import asyncio
from io import BytesIO
from pathlib import Path
import shutil
import subprocess

import pytest
from PIL import Image

from backend import service
from backend.portrait_analysis import PortraitStyle


def portrait_bytes(rgb: tuple[int,int,int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (96,96), rgb).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is not installed")
def test_name_and_portrait_generate_real_mp4_and_transparent_png(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(service, "ASSET_DIR", tmp_path)
    async def mock_vision(portrait: bytes, api_key: str) -> PortraitStyle:
        assert api_key == "fake-local-key"
        return (
            PortraitStyle(joy=1, playful=1, cute=1, energy=1, sadness=0)
            if portrait == happy
            else PortraitStyle(joy=0, sadness=1, tension=1, tough=1, energy=0)
        )
    monkeypatch.setattr(service, "analyze_portrait", mock_vision)
    happy = portrait_bytes((255,220,100))
    tense = portrait_bytes((30,30,40))
    a = asyncio.run(service.generate_signature("Hagay Onn", happy, "fake-local-key"))
    b = asyncio.run(service.generate_signature("Hagay Onn", tense, "fake-local-key"))
    assert a.asset_id != b.asset_id
    first = tmp_path / a.asset_id
    second = tmp_path / b.asset_id
    for folder in (first, second):
        assert (folder / "signature.mp4").stat().st_size > 0
        with Image.open(folder / "signature.png") as image:
            assert image.mode == "RGBA"
            assert image.getbbox() is not None
            assert image.getpixel((0,0))[3] == 0
    assert (first / "signature.png").read_bytes() != (second / "signature.png").read_bytes()
    if shutil.which("ffprobe"):
        meta = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,nb_frames,duration,r_frame_rate,width,height",
             "-of", "default=noprint_wrappers=1",
             str(first/"signature.mp4")], text=True,
        )
        assert "codec_name=h264" in meta
        assert "r_frame_rate=60/1" in meta
        assert "width=1280" in meta
        assert "height=720" in meta
        duration = float(next(line.split("=")[1] for line in meta.splitlines()
                              if line.startswith("duration=")))
        assert 4.0 <= duration <= 7.5
        frame_count = int(next(line.split("=")[1] for line in meta.splitlines()
                               if line.startswith("nb_frames=")))
        assert frame_count == round(duration * 60)
    # No temporary frames, source photos, or API credentials are persisted.
    assert not list(tmp_path.glob("_building_*"))
    assert not list(tmp_path.rglob("frame_*.png"))
    assert len(list(tmp_path.rglob("*"))) < 10
