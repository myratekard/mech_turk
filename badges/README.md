# Badge templates

Per-platform verified-badge templates used by `app/services/badge_cv.py` as an independent
**second opinion** to the LLM. 15 grayscale 40×40 crops are committed: `instagram.png`,
`x.png`, `tiktok.png` plus harvested variants `*_h0..3.png`.

## How it works

`badge_cv.detect()` localizes blue, roundish, filled discs in the top band of the screenshot,
then lets each template **slide** over a padded patch at several scales and takes the best
`TM_CCOEFF_NORMED` score. A match is asserted at `BADGE_CV_THRESHOLD` (default **0.76**) — the
clean badge/non-badge split validated cross-domain (full-res iPhone + WhatsApp-compressed):
precision = recall = F1 = **1.0** on both sets. See `tools/cv_tmpl.py` for the iteration/eval
harness and `tests/test_badge_cv.py` for the regression check.

## Fusion

The CV verdict is fused with the LLM as consensus (`app/services/fusion.py`): when both agree,
the verdict is decided directly; when they **disagree**, the submission is routed to the review
queue (`needs_review`). The detector has caught LLM mislabels in testing.

## Regenerating / adding templates

- Seed from full-res confirmed badges: `python tools/cv_tmpl.py` (writes `instagram/x/tiktok.png`).
- Harvest more variants for margin: `python -m tools.harvest_templates`.
- Tune `BADGE_CV_THRESHOLD` in `.env` if the operating point needs adjusting.
