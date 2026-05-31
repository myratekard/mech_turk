# Badge templates

Per-platform verified-badge templates used by `app/services/cv_verifier.py` for the
**corroborating** template-match signal: `instagram.png`, `x.png`, `tiktok.png`.

## Status

Currently **empty**. The CV cross-check only asserts a match on a precise template hit
(the loose blue-disc heuristic is audit-only — on the sample set it scored precision 0,
firing on blue emojis / LIVE rings / Follow buttons). With no templates present, the CV
signal is inert and the verdict rests on the LLM, which scores 1.0 precision/recall on
the labeled set. Templates only *raise confidence / clear `needs_review`* when they agree
with the LLM; they never override it.

## How to generate

Clean, tightly-cropped badge images are needed (the LLM bounding box is not pixel-accurate,
so auto-cropping from a screenshot tends to miss). Either:

1. Manually crop the badge from a high-res verified screenshot (~24–32 px square), or
2. Use `python tools/make_badges.py --instagram <img> --x <img> --tiktok <img>` and then
   **visually verify** each output actually shows the badge before keeping it.

Tune `CV_MATCH_THRESHOLD` in `.env` once templates exist.
