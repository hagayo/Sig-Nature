"""HTTP entrypoint for signature generation and asset delivery."""

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.service import GeneratedAssets, generate_signature

app = FastAPI(title="Sig-Nature")
ASSET_DIR = Path(__file__).resolve().parent / "generated"


def present_results(assets: GeneratedAssets) -> dict[str, str]:
    """Convert validated generated assets into frontend-facing URLs."""
    return {
        "signature_png_url": f"/api/assets/{assets.asset_id}/signature.png",
        "animation_webm_url": f"/api/assets/{assets.asset_id}/signature.webm",
    }


@app.post("/api/generate")
async def generate(
    full_name: str = Form(...),
    portrait: UploadFile = File(...),
    api_key: str = Form(...),
) -> dict[str, str]:
    """Generate assets using the service, then return their public URLs."""
    if not full_name.strip() or not api_key.strip():
        raise HTTPException(status_code=422, detail="Missing required input")
    if not portrait.content_type or not portrait.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Portrait must be an image")
    try:
        assets = await generate_signature(
            full_name=full_name.strip(),
            portrait=await portrait.read(),
            api_key=api_key,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return present_results(assets)


@app.get("/api/assets/{asset_id}/{filename}")
def serve_asset(asset_id: str, filename: str) -> FileResponse:
    """Serve only the two supported output formats from a generated asset."""
    if len(asset_id) != 32 or any(\n        char not in "0123456789abcdef" for char in asset_id\n    ):
        raise HTTPException(status_code=404, detail="Asset not found")
    if filename not in {"signature.png", "signature.webm"}:
        raise HTTPException(status_code=404, detail="Asset not found")
    path = ASSET_DIR / asset_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)
