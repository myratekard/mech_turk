import argparse
import os
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np
from PIL import Image


def load_image(path: str) -> np.ndarray:
    img = np.array(Image.open(path).convert("RGB"))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def save_image(path: str, bgr: np.ndarray) -> None:
    Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path)


def nms(boxes: List[Tuple[int, int, int, int]], scores: List[float], iou_thr=0.3):
    if len(boxes) == 0:
        return []
    boxes_np = np.array(boxes, dtype=np.float32)
    scores_np = np.array(scores, dtype=np.float32)
    idxs = scores_np.argsort()[::-1]
    pick = []
    while len(idxs) > 0:
        i = idxs[0]
        pick.append(i)
        if len(idxs) == 1:
            break
        iou = _iou(boxes_np[i], boxes_np[idxs[1:]])
        idxs = idxs[1:][iou < iou_thr]
    return [boxes[p] for p in pick], [scores[p] for p in pick]


def _iou(a: np.ndarray, bs: np.ndarray) -> np.ndarray:
    ax1, ay1, ax2, ay2 = a
    bx1 = bs[:, 0]; by1 = bs[:, 1]; bx2 = bs[:, 2]; by2 = bs[:, 3]
    inter_x1 = np.maximum(ax1, bx1)
    inter_y1 = np.maximum(ay1, by1)
    inter_x2 = np.minimum(ax2, bx2)
    inter_y2 = np.minimum(ay2, by2)
    inter_w = np.maximum(0, inter_x2 - inter_x1 + 1)
    inter_h = np.maximum(0, inter_y2 - inter_y1 + 1)
    inter = inter_w * inter_h
    a_area = (ax2 - ax1 + 1) * (ay2 - ay1 + 1)
    b_area = (bx2 - bx1 + 1) * (by2 - by1 + 1)
    return inter / (a_area + b_area - inter + 1e-9)


def find_blue_badge_candidates(
    bgr: np.ndarray,
    min_diam_px: int = 16,
    max_diam_px: Optional[int] = None,
) -> List[Tuple[int, int, int, int]]:
    """
    Heuristic: verified badges are typically blue circles (or near-circles).
    We threshold for blue in HSV, morph, then filter near-circular contours.
    Returns list of [x1,y1,x2,y2] boxes.
    """
    if max_diam_px is None:
        max_diam_px = int(max(bgr.shape[:2]) * 0.09)  # ~ up to 9% of dimension

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Blue ranges (tolerant): tweak if you need stricter/looser matches
    # OpenCV H in [0,179]. Typical blue ~ [100..130]
    blue_masks = []
    ranges = [
        ((100, 70, 40), (130, 255, 255)),  # primary
        ((90, 60, 40), (140, 255, 255)),   # wider safety net
    ]
    for low, high in ranges:
        blue_masks.append(cv2.inRange(hsv, np.array(low), np.array(high)))
    mask = cv2.bitwise_or.reduce(blue_masks)

    # Clean up small noise
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 20:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        diam = max(w, h)
        if diam < min_diam_px or diam > max_diam_px:
            continue

        # Circularity filter: 4πA/P^2 close to 1 means circle
        perim = cv2.arcLength(cnt, True)
        if perim == 0:
            continue
        circularity = 4 * np.pi * (area / (perim * perim))
        # Accept “near-circles” (badges/rounded lozenges)
        if circularity > 0.55 and 0.5 < (w / (h + 1e-6)) < 1.5:
            boxes.append((x, y, x + w, y + h))

    return boxes


def looks_like_checkmark(roi_bgr: np.ndarray) -> float:
    """
    Returns a confidence score [0..1] that the ROI contains a white check ✓.

    Heuristic steps:
    - Convert to gray, emphasize edges.
    - HoughLinesP to find two short lines forming an acute angle (~35°–85°),
      with one segment ~40–70% the length of the other, meeting near a junction.
    - Also require sufficient white pixels (likely check stroke) inside blue badge.
    """
    gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
    # Normalize contrast
    gray = cv2.equalizeHist(gray)
    edges = cv2.Canny(gray, 60, 150, apertureSize=3, L2gradient=True)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=25,
        minLineLength=max(6, int(0.18 * max(roi_bgr.shape[:2]))),
        maxLineGap=int(0.12 * max(roi_bgr.shape[:2])),
    )

    if lines is None or len(lines) < 2:
        return 0.0

    # Count white-ish pixels (for the check stroke, often white)
    white = cv2.inRange(cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV),
                        np.array([0, 0, 200]), np.array([179, 60, 255]))
    white_ratio = float(np.count_nonzero(white)) / (white.size + 1e-6)

    # Pairwise line angle logic
    def line_vec(l):
        x1, y1, x2, y2 = l[0]
        v = np.array([x2 - x1, y2 - y1], dtype=np.float32)
        ln = np.linalg.norm(v) + 1e-6
        return v / ln, ln, np.array([x1, y1]), np.array([x2, y2])

    lines_info = [line_vec(l) for l in lines]
    good_pairs = 0
    best_score = 0.0

    for i in range(len(lines_info)):
        v1, len1, a1, b1 = lines_info[i]
        for j in range(i + 1, len(lines_info)):
            v2, len2, a2, b2 = lines_info[j]
            # angle between them
            cosang = np.clip(np.dot(v1, v2), -1, 1)
            angle = np.degrees(np.arccos(abs(cosang)))

            # check-like: two segments meeting at ~ acute angle
            if 35 <= angle <= 85:
                # length ratio between arms
                r = min(len1, len2) / (max(len1, len2) + 1e-6)
                if 0.4 <= r <= 0.7:
                    # endpoints proximity: should “join” close
                    join_dist = min(
                        np.linalg.norm(a1 - a2), np.linalg.norm(a1 - b2),
                        np.linalg.norm(b1 - a2), np.linalg.norm(b1 - b2),
                    )
                    if join_dist <= max(4.0, 0.15 * max(roi_bgr.shape[:2])):
                        good_pairs += 1
                        # combine with white ratio for confidence
                        score = 0.5 * (1.0 - abs(60 - angle) / 60.0) + 0.5 * min(white_ratio / 0.18, 1.0)
                        best_score = max(best_score, score)

    # Require some white and at least one plausible pair
    if white_ratio < 0.04 or good_pairs == 0:
        return 0.0
    return float(np.clip(best_score, 0.0, 1.0))


def multi_scale_template_match(
    image_bgr: np.ndarray,
    template_bgr: np.ndarray,
    scales=(0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5),
    method=cv2.TM_CCOEFF_NORMED,
    thr=0.75,
) -> List[Tuple[Tuple[int, int, int, int], float]]:
    """
    Basic multi-scale template matching, returns [(box, score), ...]
    """
    results = []
    hI, wI = image_bgr.shape[:2]
    for s in scales:
        th, tw = template_bgr.shape[:2]
        ths, tws = int(th * s), int(tw * s)
        if ths < 6 or tws < 6 or ths >= hI or tws >= wI:
            continue
        templ = cv2.resize(template_bgr, (tws, ths), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(image_bgr, templ, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            # lower is better
            if min_val < (1 - thr):
                x1, y1 = min_loc
                box = (x1, y1, x1 + tws, y1 + ths)
                score = 1.0 - float(min_val)
                results.append((box, score))
        else:
            # higher is better
            if max_val >= thr:
                x1, y1 = max_loc
                box = (x1, y1, x1 + tws, y1 + ths)
                score = float(max_val)
                results.append((box, score))
    return results


def load_templates(dir_path: Optional[str]) -> List[np.ndarray]:
    if not dir_path:
        return []
    templates = []
    for p in Path(dir_path).glob("*"):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            t = load_image(str(p))
            templates.append(t)
    return templates


def detect_verified_badge(
    image_bgr: np.ndarray,
    templates_dir: Optional[str] = None,
    debug_draw: bool = False,
) -> Tuple[bool, np.ndarray, List[Tuple[int, int, int, int]]]:
    """
    Returns (is_verified, debug_image, boxes)
    """
    draw = image_bgr.copy()

    # 1) Heuristic pass: find blue-ish circles, then checkmark
    candidates = find_blue_badge_candidates(image_bgr)
    candidate_scores = []
    for (x1, y1, x2, y2) in candidates:
        pad = int(0.15 * max((x2 - x1), (y2 - y1)))
        xa, ya = max(0, x1 - pad), max(0, y1 - pad)
        xb, yb = min(image_bgr.shape[1] - 1, x2 + pad), min(image_bgr.shape[0] - 1, y2 + pad)
        roi = image_bgr[ya:yb, xa:xb]
        score = looks_like_checkmark(roi)
        candidate_scores.append(score)

    heuristic_hits = [(box, sc) for box, sc in zip(candidates, candidate_scores) if sc >= 0.35]
    heuristic_hits, heuristic_scores = nms(
        [b for b, _ in heuristic_hits],
        [s for _, s in heuristic_hits],
        iou_thr=0.4
    )

    # 2) Optional template-matching pass
    tm_hits_all = []
    if templates_dir:
        tmps = load_templates(templates_dir)
        for t in tmps:
            tm_hits_all += multi_scale_template_match(image_bgr, t, thr=0.72)
        if tm_hits_all:
            tm_boxes, tm_scores = zip(*tm_hits_all)
            tm_boxes_nms, tm_scores_nms = nms(list(tm_boxes), list(tm_scores), iou_thr=0.4)
            tm_hits_all = list(zip(tm_boxes_nms, tm_scores_nms))

    # Merge signals (heuristic + templates)
    all_boxes = []
    all_scores = []
    for b, s in zip(heuristic_hits, heuristic_scores):
        all_boxes.append(b)
        all_scores.append(s + 0.05)  # slight bias to heuristic if present

    for b, s in tm_hits_all:
        all_boxes.append(b)
        all_scores.append(s)

    final_boxes, final_scores = nms(all_boxes, all_scores, iou_thr=0.5) if all_boxes else ([], [])

    is_verified = len(final_boxes) > 0

    # Draw debug
    if debug_draw:
        for (x1, y1, x2, y2), s in zip(final_boxes, final_scores):
            cv2.rectangle(draw, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(draw, f"{s:.2f}", (x1, max(0, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        # Also draw heuristic candidates in yellow (light)
        for (x1, y1, x2, y2), s in zip(candidates, candidate_scores):
            cv2.rectangle(draw, (x1, y1), (x2, y2), (0, 220, 220), 1)

    return is_verified, draw, final_boxes


def main():
    ap = argparse.ArgumentParser(description="Detect social-media verified badge in a screenshot.")
    ap.add_argument("--image", required=True, help="Path to the screenshot image")
    ap.add_argument("--templates", default=None, help="Directory of badge templates (PNG/JPG)")
    ap.add_argument("--out", default=None, help="Path to save debug image (defaults to <image>_detected.png)")
    args = ap.parse_args()

    img = load_image(args.image)
    ok, dbg, boxes = detect_verified_badge(img, templates_dir=args.templates, debug_draw=True)

    print(f"Verified badge detected: {ok}")
    if boxes:
        print("Boxes:", boxes)

    out_path = args.out or str(Path(args.image).with_name(Path(args.image).stem + "_detected.png"))
    save_image(out_path, dbg)
    print(f"Debug image saved to: {out_path}")


if __name__ == "__main__":
    main()
