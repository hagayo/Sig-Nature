"""Sig-Nature: same-origin site, image analysis and generated asset delivery."""
from pathlib import Path
import subprocess

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.portrait_analysis import MAX_IMAGE_BYTES, validate_portrait
from backend.service import GeneratedAssets, generate_signature

app = FastAPI(title="Sig-Nature")
BASE_DIR = Path(__file__).resolve().parent.parent
ASSET_DIR = Path(__file__).resolve().parent / "generated"


def present_results(assets: GeneratedAssets) -> dict[str, str]:
    return {
        "signature_png_url": f"/api/assets/{assets.asset_id}/signature.png",
        "animation_mp4_url": f"/api/assets/{assets.asset_id}/signature.mp4",
    }


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/script.js", include_in_schema=False)
def javascript() -> FileResponse:
    return FileResponse(BASE_DIR / "script.js", media_type="text/javascript")


@app.get("/style.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")


@app.post("/api/generate")
async def generate(
    full_name: str = Form(...),
    portrait: UploadFile = File(...),
    api_key: str = Form(...),
) -> dict[str, str]:
    if not full_name.strip() or not api_key.strip():
        raise HTTPException(422, "Name and API key are required")
    if portrait.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Upload a JPEG, PNG or WebP portrait")
    content = await portrait.read(MAX_IMAGE_BYTES + 1)
    try:
        validate_portrait(content)
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    try:
        assets = await generate_signature(full_name.strip(), content, api_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise HTTPException(400, "The OpenAI API key was rejected") from exc
        if exc.response.status_code == 429:
            raise HTTPException(503, "OpenAI rate limit reached") from exc
        raise HTTPException(502, f"OpenAI response failed ({exc.response.status_code})") from exc
    except (httpx.RequestError, subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise HTTPException(503, "Image analysis or video encoder unavailable") from exc
    return present_results(assets)


@app.get("/api/assets/{asset_id}/{filename}")
def serve_asset(asset_id: str, filename: str) -> FileResponse:
    if len(asset_id) != 32 or any(ch not in "0123456789abcdef" for ch in asset_id):
        raise HTTPException(404, "Asset not found")
    if filename not in {"signature.png", "signature.mp4"}:
        raise HTTPException(404, "Asset not found")
    path = ASSET_DIR / asset_id / filename
    if not path.is_file():
        raise HTTPException(404, "Asset not found")
    return FileResponse(path, media_type=("video/mp4" if filename.endswith(".mp4") else "image/png"))
