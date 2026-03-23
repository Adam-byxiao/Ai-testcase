import os
from typing import List, Dict, Any
import numpy as np
import cv2


def _load_image(path: str):
    img = cv2.imread(path)
    if img is None:
        raise ValueError("Failed to read image")
    return img


def _bbox_area(bbox: List[float]) -> float:
    if not bbox:
        return 0.0
    return max(0.0, bbox[2]) * max(0.0, bbox[3])


def _bbox_iou(a: List[float], b: List[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    union = _bbox_area(a) + _bbox_area(b) - inter
    return inter / union if union else 0.0


def _scale_bbox_to_image(bbox: List[float], frame_bbox: List[float], image_shape) -> List[float]:
    fx, fy, fw, fh = frame_bbox
    x, y, w, h = bbox
    if fw == 0 or fh == 0:
        return [0, 0, 0, 0]
    rel_x = (x - fx) / fw
    rel_y = (y - fy) / fh
    rel_w = w / fw
    rel_h = h / fh
    img_h, img_w = image_shape[:2]
    return [rel_x * img_w, rel_y * img_h, rel_w * img_w, rel_h * img_h]


def detect_shapes_cv(image_path: str, min_area: int = 400) -> List[Dict[str, Any]]:
    img = _load_image(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    shapes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        x, y, w, h = cv2.boundingRect(approx)
        if w < 20 or h < 20:
            continue

        shape = "other"
        if len(approx) == 3:
            shape = "triangle"
        elif len(approx) == 4:
            shape = "rectangle"
        else:
            circularity = 4 * np.pi * area / (peri * peri) if peri > 0 else 0
            if circularity > 0.6:
                shape = "circle"

        shapes.append({"bbox": [x, y, w, h], "shape": shape})
    return shapes


def validate_flowchart_with_cv(image_path: str, json_nodes: List[Dict[str, Any]], frame_bbox: List[float]) -> Dict[str, Any]:
    img = _load_image(image_path)
    shapes = detect_shapes_cv(image_path)

    # scale json nodes into image space
    scaled_nodes = []
    for n in json_nodes:
        bbox = n.get("bbox")
        if not bbox:
            continue
        scaled = _scale_bbox_to_image(bbox, frame_bbox, img.shape)
        scaled_nodes.append({**n, "bbox_scaled": scaled})

    matched = []
    unmatched_nodes = []
    used_shape_idx = set()

    for n in scaled_nodes:
        best_iou = 0.0
        best_idx = -1
        for i, s in enumerate(shapes):
            if i in used_shape_idx:
                continue
            iou = _bbox_iou(n["bbox_scaled"], s["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_idx = i
        if best_iou >= 0.2 and best_idx >= 0:
            used_shape_idx.add(best_idx)
            matched.append({"node_id": n.get("id"), "shape": shapes[best_idx].get("shape"), "iou": round(best_iou, 3)})
        else:
            unmatched_nodes.append(n.get("id"))

    unmatched_shapes = [s for i, s in enumerate(shapes) if i not in used_shape_idx]

    return {
        "json_node_count": len(scaled_nodes),
        "shape_count": len(shapes),
        "matched": matched,
        "unmatched_nodes": unmatched_nodes,
        "unmatched_shapes": unmatched_shapes
    }
