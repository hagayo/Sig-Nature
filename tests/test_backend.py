"""API tests with mocked paid vision calls and valid image bytes."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import main, service
from backend.service import GeneratedAssets
from backend.portrait_analysis import PortraitStyle

client = TestClient(main.app)


def photo_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (64, 64), "navy").save(buf, format="PNG")
    return buf.getvalue()


def test_generate_rejects_non_image() -> None:
    response = client.post(
        "/api/generate",
        data={"full_name": "חגי און", "api_key": "test-key"},
        files={"portrait": ("input.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 415


def test_generate_rejects_corrupt_image() -> None:
    response = client.post(
        "/api/generate",
        data={"full_name": "חגי און", "api_key": "test-key"},
        files={"portrait": ("bad.png", b"not-an-image", "image/png")},
    )
    assert response.status_code == 415


def test_generate_returns_both_asset_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_generator(full_name: str, portrait: bytes, api_key: str) -> GeneratedAssets:
        assert full_name == "חגי און"
        assert portrait == photo_bytes()
        assert api_key == "test-key"
        return GeneratedAssets(asset_id="a"*32)
    monkeypatch.setattr(main, "generate_signature", fake_generator)
    response = client.post(
        "/api/generate",
        data={"full_name": " חגי און ", "api_key": "test-key"},
        files={"portrait": ("photo.png", photo_bytes(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "signature_png_url": f"/api/assets/{'a'*32}/signature.png",
        "animation_mp4_url": f"/api/assets/{'a'*32}/signature.mp4",
    }


def test_asset_rejects_path_traversal() -> None:
    assert client.get("/api/assets/not-valid/signature.png").status_code == 404
    assert client.get("/api/assets/" + "a"*32 + "/secret.txt").status_code == 404


def test_asset_returns_existing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / ("b"*32)
    folder.mkdir()
    (folder/"signature.png").write_bytes(b"sample")
    monkeypatch.setattr(main, "ASSET_DIR", tmp_path)
    response = client.get("/api/assets/" + "b"*32 + "/signature.png")
    assert response.status_code == 200
    assert response.content == b"sample"


def test_home_and_site_assets_are_served() -> None:
    assert client.get("/").status_code == 200
    assert client.get("/script.js").status_code == 200
    assert client.get("/style.css").status_code == 200


def test_no_paid_api_call_for_unsupported_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden(*args: object) -> PortraitStyle:
        raise AssertionError("Vision API should not be called")
    monkeypatch.setattr(service, "analyze_portrait", forbidden)
    response = client.post(
        "/api/generate",
        data={"full_name": "Invalid 123", "api_key": "test-key"},
        files={"portrait": ("photo.png", photo_bytes(), "image/png")},
    )
    assert response.status_code == 422
