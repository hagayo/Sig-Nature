"""Regression tests for local prerequisites and opt-in asset retention."""
from io import BytesIO
import os
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend import main, service

client = TestClient(main.app)


def photo() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (96, 96), "navy").save(buffer, "PNG")
    return buffer.getvalue()


def test_no_paid_call_when_h264_encoder_is_missing(monkeypatch):
    def unavailable():
        raise FileNotFoundError("ffmpeg not found")

    async def forbid_vision(*args, **kwargs):
        raise AssertionError("Paid vision should not be requested")

    monkeypatch.setattr(service, "ensure_video_encoder", unavailable)
    monkeypatch.setattr(service, "analyze_portrait", forbid_vision)
    response = client.post(
        "/api/generate",
        data={"full_name": "Hagay Onn", "api_key": "dummy-key"},
        files={"portrait": ("sample.png", photo(), "image/png")},
    )
    assert response.status_code == 503


def test_retention_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("SIG_NATURE_ASSET_TTL_HOURS", raising=False)
    directory = tmp_path / ("a" * 32)
    directory.mkdir()
    (directory / "signature.mp4").write_bytes(b"stored-video")
    assert service.purge_expired_assets(tmp_path, now=time.time() + 100000) == 0
    assert directory.exists()


def test_expiration_only_removes_complete_old_assets(monkeypatch, tmp_path):
    monkeypatch.setenv("SIG_NATURE_ASSET_TTL_HOURS", "1")
    old = tmp_path / ("a" * 32)
    recent = tmp_path / ("b" * 32)
    pending = tmp_path / "_building_in_progress"
    other = tmp_path / "human-files"
    for directory in (old, recent, pending, other):
        directory.mkdir()
        (directory / "data.txt").write_text("sample", encoding="utf-8")
    now = time.time()
    os.utime(old, (now - 7200, now - 7200))
    os.utime(recent, (now, now))
    os.utime(pending, (now - 7200, now - 7200))
    os.utime(other, (now - 7200, now - 7200))
    assert service.purge_expired_assets(tmp_path, now=now) == 1
    assert not old.exists()
    assert recent.exists()
    assert pending.exists()
    assert other.exists()


@pytest.mark.parametrize("ttl", ["0", "-2", "nan", "inf", "wrong"])
def test_invalid_retention_is_rejected(monkeypatch, tmp_path, ttl):
    monkeypatch.setenv("SIG_NATURE_ASSET_TTL_HOURS", ttl)
    with pytest.raises(RuntimeError):
        service.purge_expired_assets(tmp_path)
