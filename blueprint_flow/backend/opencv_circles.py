import os
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np


def _bbox_from_circle(x: int, y: int, r: int) -> List[int]:
    return [int(x - r), int(y - r), int(2 * r), int(2 * r)]


def _bbox_iou(a: List[int], b: List[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def detect_circular_screens(
    image_path: str,
    min_radius: int = 90,
    max_radius: int = 220,
    max_results: int = 12,
    radius_band: float = 0.35
) -> List[Dict[str, Any]]:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Failed to read image")
    h_img, w_img = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=120,
        param1=80,
        param2=30,
        minRadius=min_radius,
        maxRadius=max_radius
    )

    results = []
    if circles is None:
        return results

    # Use int (avoid uint16 overflow)
    circles = np.around(circles[0]).astype(int)
    candidates: List[Dict[str, Any]] = []
    for (x, y, r) in circles:
        if r <= 0:
            continue
        bbox = _bbox_from_circle(x, y, r)
        # keep only circles whose center is inside the image
        if x < 0 or y < 0 or x >= w_img or y >= h_img:
            continue
        candidates.append({"bbox": bbox, "radius": int(r), "center": [int(x), int(y)]})

    if not candidates:
        return []

    # Filter by dominant radius band to avoid small icon circles
    radii = sorted([c["radius"] for c in candidates])
    mid = radii[len(radii) // 2]
    min_r = int(mid * (1.0 - radius_band))
    max_r = int(mid * (1.0 + radius_band))
    candidates = [c for c in candidates if min_r <= c["radius"] <= max_r]

    # sort by radius desc, then dedup by IoU/center proximity
    candidates.sort(key=lambda c: c["radius"], reverse=True)
    for c in candidates:
        bbox = c["bbox"]
        keep = True
        for kept in results:
            if _bbox_iou(bbox, kept["bbox"]) > 0.4:
                keep = False
                break
            cx, cy = c["center"]
            kx, ky = kept["center"]
            if (cx - kx) ** 2 + (cy - ky) ** 2 < (min_radius ** 2):
                keep = False
                break
        if keep:
            results.append(c)
        if len(results) >= max_results:
            break

    return results


def crop_by_bbox(image_path: str, bbox: List[int]) -> bytes:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Failed to read image")
    x, y, w, h = bbox
    h_img, w_img = img.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w_img, x + w)
    y1 = min(h_img, y + h)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Empty crop region")
    crop = img[y0:y1, x0:x1]
    ok, buf = cv2.imencode('.png', crop)
    if not ok:
        raise ValueError("Failed to encode crop")
    return buf.tobytes()
