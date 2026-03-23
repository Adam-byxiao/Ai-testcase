import os
from typing import List, Dict, Tuple
import numpy as np
import cv2


def _load_image(path: str):
    img = cv2.imread(path)
    if img is None:
        raise ValueError("Failed to read image")
    return img


def _center(bbox: List[float]) -> Tuple[float, float]:
    x, y, w, h = bbox
    return (x + w / 2.0, y + h / 2.0)


def _point_dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _scale_bbox_to_image(bbox: List[float], frame_bbox: List[float], image_shape: Tuple[int, int]) -> List[float]:
    # frame_bbox is in Figma coordinates; map to image pixel space by normalizing within frame bbox
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


def detect_flowchart_edges_cv(image_path: str, nodes: List[Dict], frame_bbox: List[float]) -> List[Dict]:
    img = _load_image(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=40, maxLineGap=10)

    if lines is None or not nodes:
        return []

    # scale node bboxes into image pixel space
    nodes_scaled = []
    for n in nodes:
        bbox = n.get("bbox")
        if not bbox:
            continue
        scaled = _scale_bbox_to_image(bbox, frame_bbox, img.shape)
        nodes_scaled.append({**n, "bbox_scaled": scaled})

    centers = [(_center(n["bbox_scaled"])) for n in nodes_scaled]

    def nearest_node(pt):
        best_idx = -1
        best_dist = 1e12
        for i, c in enumerate(centers):
            dist = _point_dist(pt, c)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        return best_idx, best_dist

    edges_out = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        start_idx, d1 = nearest_node((x1, y1))
        end_idx, d2 = nearest_node((x2, y2))
        if start_idx == -1 or end_idx == -1 or start_idx == end_idx:
            continue
        # heuristic distance threshold in pixel space
        if d1 > 40000 or d2 > 40000:
            continue
        edges_out.append({
            "from": nodes_scaled[start_idx]["id"],
            "to": nodes_scaled[end_idx]["id"],
            "label": ""
        })

    # dedupe
    uniq = {}
    for e in edges_out:
        key = (e["from"], e["to"], e["label"])
        uniq[key] = e
    return list(uniq.values())
