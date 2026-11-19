"""Behavioral contract tests for the initial backend."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.service import GeneratedAssets

client = TestClient(main.app)


def test_generate_rejects_non_image() -> None:
    response = client.post(
        "/api/generate",
        data={"full_name": "Example", "api_key": "test-key"},
        files={"portrait": ("input.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["detail"] == "Portrait must be an image"


def test_generate_reports_unimplemented_engine() -> None:
    response = client.post(
        "/api/generate",
        data={"full_name": "Example", "api_key": "test-key"},
        files={"portrait": ("photo.png", b"image", "image/png")},
    )
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]


def test_generate_returns_both_asset_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_generator(
        full_name: str, portrait: bytes, api_key: str
    ) -> GeneratedAssets:
        assert full_name == "Example"
        assert portrait == b"image"
        assert api_key == "test-key"
        return GeneratedAssets(asset_id="a" * 32)

    monkeypatch.setattr(main, "generate_signature", fake_generator)
    response = client.post(
        "/api/generate",
        data={"full_name": " Example ", "api_key": "test-key"},
        files={"portrait": ("photo.png", b"image", "image/png")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "signature_png_url": f"/api/assets/{'a' * 32}/signature.png",
        "animation_mp4_url": f"/api/assets/{'a' * 32}/signature.mp4",
    }


def test_asset_rejects_path_traversal() -> None:
    response = client.get("/api/assets/not-a-valid-id/signature.png")
    assert response.status_code == 404


def test_asset_returns_existing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asset_id = "b" * 32
    folder = tmp_path / asset_id
    folder.mkdir()
    (folder / "signature.png").write_bytes(b"sample")
    monkeypatch.setattr(main, "ASSET_DIR", tmp_path)
    response = client.get(f"/api/assets/{asset_id}/signature.png")
    assert response.status_code == 200
    assert response.content == b"sample"
