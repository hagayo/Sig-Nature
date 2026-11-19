# Sig-Nature

A playful portrait-inspired signature maker, plus two stand-alone analysis tools.

## Pages

- `/` - Create a signature from a full name, a portrait and your own OpenAI API key. Download the exact same result as a transparent PNG and a video.
- `/analyze-photo.html` - Inspect the visual impressions identified in a portrait and all numeric handwriting parameters derived from them, for debugging.
- `/analyze-signature.html` - Upload an existing handwritten signature and get a playful visual interpretation of its strokes and style.

All three pages use **the same** `style.css` and `script.js`, one navigation/header design, responsive layout, and a Hebrew/English toggle. CSS uses shared `:root` color, spacing, radius and button tokens.

## Local setup (Windows 10 or Linux)

Requirements: Python 3.12+, FFmpeg with `libx264`, internet access, and a personal OpenAI API key.

```sh
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000.

All OpenAI calls are made with the API key entered for that request. The key and the input portrait/signature are **not saved** by the backend. Generated PNG/MP4 files are kept in `backend/generated/`, excluded from git. By default they persist until manually deleted. Optionally set `SIG_NATURE_ASSET_TTL_HOURS` to a positive number to remove expired completed results on the next generation request. Staging folders and unrelated files are never touched; this is opt-in, not a background scheduler. Expired download links stop working.

## Personal signature engine

The form can now generate a personalized signature for **any supported
Hebrew or Latin name**, rather than relying on the original test name.
The same request path supports the following cases:

- Hebrew full names, including all final forms (ך, ם, ן, ף, ץ), long
  surnames, multiple words, geresh/gershayim, maqaf and vowel points.
- English and other Latin-script names with accented vowels, common special
  letters, apostrophes and hyphenated names.
- Mixed Hebrew/Latin names such as `שרה Smith` or `Hagay און`.
- Different portrait impressions change stroke pressure, roundness,
  proportions, slant, irregularity and length of the finishing flourish.
- A deterministic signature for identical inputs; no random unrelated glyphs.

`backend/name_rules.py` normalizes Unicode, strips diacritics in favor of
readable hand lettering and rejects control characters, numbers and unsupported
scripts. `backend/signature_composer.py` measures every glyph and its pen
trajectory in unrestricted coordinates, lays out whole names in the appropriate
writing direction, connects glyphs in a single visible pen-down stroke,
adds a natural ending gesture and **only then fits the complete ink to the
720×720 paper plane**. This prevents the clipping formerly caused by
hard-coded starting coordinates. Short and long names use the same algorithm.

The handwritten font assets are included in the repository so first-run
generation requires no font download:

- Hebrew: **Gveret Levin**, AlefAlefAlef, SIL OFL 1.1
  (`backend/assets/GveretLevin-Regular.ttf`,
  `backend/assets/GveretLevin-OFL.txt`).
- Latin: **Caveat**, Google Fonts, SIL OFL 1.1
  (`backend/assets/Caveat-Variable.ttf`,
  `backend/assets/Caveat-OFL.txt`).

The fonts remain fully configurable through
`SIG_NATURE_HEBREW_FONT` and `SIG_NATURE_LATIN_FONT` for local development.
Unsupported scripts still receive a clear validation error rather than
unreadable placeholders; the app does not claim universal language coverage.
Handwriting is stylized: the font-to-stroke approximation is not
motion-captured human writing.

### Cinematic pen and ink

Production video uses `backend/cinematic_video.py`: a photographic-looking
3/4 side-angle close-up of the nib on textured paper. Ink is deposited
strictly along the same trajectory used for the transparent PNG. A stabilized
camera follows the nib and pulls back to reveal the full signature. Motion is
curvature-aware and deliberately slower (approximately 6.8-10.7 seconds,
depending on the handwriting). Video is streamed at 1280×720, 60 FPS, H.264,
CRF 17, slow preset. This is a photo-composited synthetic video, not
photography of a physical hand.

### Offline visual QA

```sh
python -m scripts.preview_styles --name "שרה לוי" --output styles.png
python -m scripts.preview_cinema --name "John Smith" --style bold --output signature.mp4
python -m pytest -q tests/test_general_names.py tests/test_signature_planner.py tests/test_font_signature.py
```

The test commands do not spend OpenAI credits. The old example name is no
longer privileged by any drawing code. Full-run visual approval on real names
and portraits remains an independent acceptance step.

## Analysis API

- `POST /api/generate`: multipart `full_name`, `portrait`, `api_key` - returns `signature_png_url`, `animation_mp4_url`.
- `POST /api/analyze-photo`: multipart `image`, `api_key`, `language` (`he`/`en`). Returns `summary`, `cues` (2-5 concrete visible clues), `vibe`, `traits` (18 calibrated values), and `writing_style` (the exact geometry controls used by generation). The photo preview uses EXIF-normalized, resized JPEG; the generated signature uses the same 18-score visual model.
- `POST /api/analyze-signature`: multipart `image`, `api_key`, `language`. Returns a concise `analysis` of visible strokes and a playful character impression. Fine ink remains intact through a white-composited PNG upload. The analysis separates line appearance from actual writing pressure, and does not hallucinate a person's name.
- Both analysis routes reject an unrecognizable image with HTTP 422. A malformed, refused or incomplete structured vision response returns 502, and provider errors are mapped separately. Prompts and JSON schemas live in `backend/portrait_analysis.py` and `backend/signature_analysis.py`; both use `backend/vision_client.py` for identical OpenAI request handling.

Descriptions of personality and emotion are **creative impressions of an image**, not factual measurements.

## No-API visual QA

Use the deterministic four-style contact sheet to assess handwriting readability
and individuality without sending images, spending OpenAI credits or running CI:

```sh
python -m scripts.preview_styles --name "חגי און" --output signature-preview.png
```

The command writes four isolated transparent PNGs and a 2-by-2 comparison
image. Use `--font C:/path/to/GveretLevin-Regular.ttf` when offline. It is a
visual inspection tool, not a claim that human handwriting realism is solved.

### Local cinematic QA (no model charges)

To inspect the **actual production macro compositor** instead of the old overhead
sprite, render both a transparent PNG and a Full HD 60 FPS MP4:

```sh
python -m scripts.preview_cinema --name "חגי און" --style joyful --output cinematic-signature.mp4
```

Styles: `joyful`, `bold`, `calm` and `mysterious`. No real face is uploaded,
and no OpenAI request is made. `--name "Hagay Onn"` also works offline
without the Hebrew font. The renderer requires the two compact photographic
assets under `backend/assets/` and FFmpeg with `libx264`.

## Local tests (do not trigger GitHub Actions)

```sh
python -m pytest -q
node --test tests/*.test.mjs
```

External OpenAI calls are mocked in the tests, so no API credits are spent. FFmpeg is needed for the local cinematic MP4 pipeline test. The integration test renders 1280×720 photographic frames and may take longer than the other unit tests. The old GitHub workflow remains parked in `ci-disabled/ci.yml`; no workflows are active under `.github/workflows/`.


### Motion polish

The movement timeline uses local curvature to decelerate near bends, gently
accelerates at the beginning, and eases into the final stroke. Bidirectional
filtering of the velocity profile prevents skeleton jitter from appearing as
hand tremor. The writing duration scales with path length and visual
complexity rather than being fixed, and is deliberately slower than the
earlier rapid version. The real-paper macro camera uses restrained positional
inertia and a damped wrist angle so the pen body does not snap at corners.
The pen photo and paper pigment textures are cached/reused where possible.
