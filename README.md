# mech_turk — Verified-Account Artifact Extractor

Given a social-media **profile screenshot**, the engine:

1. **Identifies the platform** (Instagram, X/Twitter, TikTok).
2. **Confirms the account carries the official verified tick** — using two independent
   signals: a Gemini vision verdict and a classical-CV badge check, fused leniently.
3. **Extracts the profile** into a structured record — but only when verified.

The verified-only gate is the point: we document artifacts of *verified* accounts.

## Full solution (dashboard UI + API)

A React dashboard (`frontend/artifacts/turk`, "intel" themed) talks to the FastAPI
backend over the `/api` contract (`frontend/lib/api-spec/openapi.yaml`): upload
screenshots → each is analyzed by the engine → results show as **submissions** with
platform, status (`accepted`/`processed`/`in_review`), and points, plus a dashboard
summary. Auth (Clerk) was stripped for a self-contained dev build (fixed dev user);
persistence is **SQLite** at `artifacts/turk.db`; uploads are stored under
`artifacts/uploads/`.

Status mapping: engine `verified` → `accepted` (+100 pts); `needs_review` →
`in_review`; otherwise `processed`.

### Run both

```bash
# 1) Backend (serves /api + the engine) — from repo root, with .env (GOOGLE_API_KEY) set
uvicorn app.main:app --port 2100 --reload

# 2) Frontend (Vite dev server, proxies /api -> http://localhost:2100)
cd frontend
pnpm install                       # first time (needs pnpm; `npm i -g pnpm`)
cd artifacts/turk
# PORT/BASE_PATH are required by vite.config.ts; run vite's bin directly to avoid
# pnpm's pre-run deps-check tripping the repo's pnpm-only `preinstall` guard.
PORT=5173 BASE_PATH=/ node node_modules/vite/bin/vite.js --config vite.config.ts
```

Open http://localhost:5173 → Upload a screenshot → see it analyzed under Submissions /
Dashboard. Override the API target for the proxy with `VITE_API_TARGET`.

**Windows/local notes** (this template was generated on Replit, Linux-only):
- `pnpm-workspace.yaml` originally excluded all non-Linux native binaries — removed so
  esbuild/rollup/lightningcss/tailwind-oxide install for the current OS.
- `.npmrc` sets `verify-deps-before-run=false`; Clerk auth was stripped (fixed dev user).

## Architecture (algo)

```
screenshot ─► vision_llm (Gemini: platform + verdict + fields, one call)
                 │
                 ├─► badge_cv (independent SECOND OPINION: blue-disc localizer +
                 │             sliding multi-scale template match vs badges/; F1=1.0
                 │             cross-domain on full-res + WhatsApp-compressed)
                 │
                 └─► fusion (consensus: agree → decide; disagree → review queue)
                        │
                        └─► pipeline (gate extraction on verified) ─► store (JSON + evidence crop)
```

Code lives in `app/`:
- `services/vision_llm.py` — Gemini vision call (`gemini-2.5-flash`, structured output).
- `services/badge_cv.py` — CV second-opinion badge detector (template match vs `badges/`); the
  live CV signal. (`services/cv_verifier.py` is the earlier heuristic, retained for `tools/`.)
- `services/fusion.py` — consensus fusion (LLM + CV agree → decide, disagree → review).
- `services/pipeline.py` — orchestration + extraction gate.
- `services/store.py` — local JSON artifact store (R2/Mongo can drop in later).
- `schemas/models.py` — Pydantic models (`AnalysisResult`, `ProfileArtifact`, …).
- `api/` — FastAPI app exposing `POST /analyze` (for the Replit UI to call).

`verify/` holds the original CV codebase, trained models, notebooks, and the labeled
sample dataset (moved in from `myratekard-ai`).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # set GOOGLE_API_KEY (shared myratekard Gemini key)
```

## Run

```bash
# Single screenshot
python cli.py analyze path/to/screenshot.jpg

# Batch accuracy eval over the labeled sample tree
python cli.py eval --dir verify/samples --report report.json

# API (for the UI)
uvicorn app.main:app --port 2100 --reload
# POST /analyze  (multipart: file=<screenshot>)
```

## Dataset & ground truth

Labeled tree used for evaluation:

```
verify/samples/<platform>/<label>/*.jpeg
  platform ∈ { instagram, tiktok, twitter }   (twitter → predicted as 'x')
  label    ∈ { verified, not_verified }        (independent ground truth)
```

`cli.py eval` reports platform-classification accuracy and verification
precision/recall/F1 against these labels.

Current labeled set: **31 verified / 44 not verified** across 75 screenshots
(Instagram 10/12, X 18/3, TikTok 3/29).

## Results (on the labeled set)

| Metric | Score |
|---|---|
| Platform classification accuracy | **1.00** (75/75) |
| Verification precision | **1.00** |
| Verification recall | **1.00** |
| Verification accuracy | **1.00** (TP=31, FP=0, TN=44, FN=0) |

How we got here (the interesting part):
1. A naive single LLM call over-called "verified" (precision ~0.65) — fooled into false
   positives, and the labels themselves had errors (badges missed at low-res).
2. Re-labeling at full resolution fixed the ground truth (6 corrections).
3. A **reasoning-first prompt** (force the model to describe what sits next to the name
   *before* deciding, default to not-verified) made the LLM a perfect classifier on this set.
4. The classical-CV heuristic measured **precision 0** on its own (fires on blue emojis,
   LIVE rings, Follow buttons), so fusion was changed to **LLM-primary**: only a precise
   template match may corroborate; the loose heuristic can never assert a positive.

### Caveats (read before trusting 1.00)
- The prompt was tuned **on this same set**, so 1.00 is an in-distribution / dev-set number,
  not a held-out estimate. Expect lower precision on novel screenshots; a separate test set
  is needed for an unbiased figure.
- The set is small (75) and TikTok has only 3 positives.
- It only contains profile screenshots in the three supported layouts.
- The CV template signal is currently inactive (see `badges/README.md`); the verdict rests
  on the LLM today.

## v1 scope

Instagram, X, TikTok. Facebook & Snapchat deferred (no samples yet). Persistence is
local JSON; auth/rate-limiting and the Replit UI are out of scope for the engine.
