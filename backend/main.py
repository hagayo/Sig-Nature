"""Sig-Nature API and shared three-page web interface."""
from dataclasses import asdict
from pathlib import Path
import subprocess

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from backend.portrait_analysis import MAX_IMAGE_BYTES, analyze_portrait, validate_portrait
from backend.service import GeneratedAssets, generate_signature
from backend.signature_analysis import analyze_signature
from backend.style_mapping import style_from_portrait

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


@app.get("/analyze-photo.html", include_in_schema=False)
def photo_page() -> FileResponse:
    return FileResponse(BASE_DIR / "analyze-photo.html")


@app.get("/analyze-signature.html", include_in_schema=False)
def signature_page() -> FileResponse:
    return FileResponse(BASE_DIR / "analyze-signature.html")


@app.get("/script.js", include_in_schema=False)
def javascript() -> FileResponse:
    return FileResponse(BASE_DIR / "script.js", media_type="text/javascript")


@app.get("/style.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")


def _provider_problem(exc: httpx.HTTPStatusError) -> HTTPException:
    status = exc.response.status_code
    if status in {401, 403}:
        return HTTPException(400, "The OpenAI API key was rejected")
    if status == 429:
        return HTTPException(503, "OpenAI rate limit reached")
    return HTTPException(502, f"OpenAI response failed ({status})")


async def _get_image(upload: UploadFile) -> bytes:
    if upload.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Upload JPEG, PNG or WebP")
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    try:
        validate_portrait(data)
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    finally:
        await upload.close()
    return data


@app.post("/api/generate")
async def generate(
    full_name: str = Form(...),
    portrait: UploadFile = File(...),
    api_key: str = Form(...),
) -> dict[str, str]:
    if not full_name.strip() or not api_key.strip():
        raise HTTPException(422, "Name and API key are required")
    content = await _get_image(portrait)
    try:
        assets = await generate_signature(full_name.strip(), content, api_key)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _provider_problem(exc) from exc
    except (httpx.RequestError, subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(503, "Image analysis or media generation unavailable") from exc
    return present_results(assets)


@app.post("/api/analyze-photo")
async def analyze_photo_route(
    image: UploadFile = File(...),
    api_key: str = Form(...),
    language: str = Form("he"),
) -> dict[str, object]:
    if language not in {"he", "en"} or not api_key.strip():
        raise HTTPException(422, "Invalid language or missing API key")
    photo = await _get_image(image)
    try:
        traits = await analyze_portrait(photo, api_key)
    except httpx.HTTPStatusError as exc:
        raise _provider_problem(exc) from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "OpenAI is temporarily unreachable") from exc
    except ValueError as exc:
        raise HTTPException(502, "Invalid portrait analysis output") from exc
    return {
        "traits": asdict(traits),
        "writing_style": asdict(style_from_portrait(traits)),
    }


@app.post("/api/analyze-signature")
async def analyze_signature_route(
    image: UploadFile = File(...),
    api_key: str = Form(...),
    language: str = Form("he"),
) -> dict[str, object]:
    if language not in {"he", "en"} or not api_key.strip():
        raise HTTPException(422, "Invalid language or missing API key")
    signature = await _get_image(image)
    try:
        report = await analyze_signature(signature, api_key, language)
    except httpx.HTTPStatusError as exc:
        raise _provider_problem(exc) from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "OpenAI is temporarily unreachable") from exc
    except ValueError as exc:
        raise HTTPException(502, "Invalid signature analysis output") from exc
    return {"analysis": report.to_payload()}


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
