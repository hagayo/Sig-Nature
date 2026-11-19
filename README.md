# Sig-Nature

Turn a name and a portrait into a playful handwritten signature and a video of
a blue ballpoint pen writing that **exact same continuous stroke**.

## Running locally

Requirements: Python 3.12+, FFmpeg with libx264, and an OpenAI API key belonging
to the user. No Node server, database, or GitHub Actions are needed.

```sh
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000**. Supply a Hebrew or Latin full name, a JPEG,
PNG or WebP portrait and your own OpenAI API key. Select Hebrew/English in the
interface. It returns a transparent **signature.png** and a **signature.mp4**
(H.264, yuv420p, 24 FPS, 36 frames, 1.5 seconds).

## Architecture

1. `portrait_analysis.py` - OpenAI vision produces 18 scores for the **visual
   expression and theatrical character** conveyed by the photograph (smiling,
   tense, tough, cute, playful, elegant, etc.). The scores are artistic
   impressions, not personality assessments.
2. `style_mapping.py` - These scores control pressure, stroke roundness,
   slant, irregularity, width, height, letter spacing, writing rhythm,
   directional rise and finishing flourish.
3. `signature_planner.py` - Converts a Hebrew or Latin name into **one
   uninterrupted pen-down path**. Curved bridges between letters and words are
   deliberately visible. Every letter has a defined directed single-path glyph.
4. `pen_path.py` - Renders an exact distance-based prefix at every video frame.
   Ink width/opacity and slight simulated paper indentation depend on pressure.
   The pen nib stays at the current final path point. PNG uses the same path.
5. `animation.py` - Encodes exactly 36 numbered frames with FFmpeg to an
   MP4 encoded as H.264, yuv420p, with faststart.
6. `service.py` - Calls portrait analysis, renders files to a temporary
   directory, then atomically publishes the PNG/MP4 pair. Raw photos and API
   keys are not saved. Only generated results persist in `backend/generated/`
   (ignored by git).

The single-stroke alphabets are intentionally stylized approximations, not a
trained handwriting model. Visual legibility should be reviewed for each
supported language and long names.

## Tests

Run locally without triggering GitHub Actions:

```sh
python -m pytest -q
node --test tests/frontend.test.mjs
```

The integration tests mock the external vision API; they do not spend API
credits. The MP4 integration test requires local FFmpeg.
