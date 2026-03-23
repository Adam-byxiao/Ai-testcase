import os
import tempfile
from typing import List, Dict, Tuple
import requests
import numpy as np
import cv2


def _download_image(image_url: str) -> str:
    resp = requests.get(image_url, timeout=20)
    resp.raise_for_status()
    fd, path = tempfile.mkstemp(suffix='.png')
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)
    return path


def _load_image(path: str):
    img = cv2.imread(path)
    if img is None:
        raise ValueError("Failed to read image")
    return img


def detect_flowchart_nodes(image_path: str) -> List[Dict]:
    img = _load_image(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    nodes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 400:  # filter tiny noise
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
            # check for rectangle vs diamond
            aspect = w / float(h)
            if 0.6 <= aspect <= 1.4:
                shape = "rectangle"
            else:
                shape = "rectangle"
        else:
            # circularity
            circularity = 4 * np.pi * area / (peri * peri) if peri > 0 else 0
            if circularity > 0.6:
                shape = "circle"

        nodes.append({
            "bbox": [int(x), int(y), int(w), int(h)],
            "shape": shape
        })
    return nodes


def _center(bbox: List[int]) -> Tuple[int, int]:
    x, y, w, h = bbox
    return (x + w // 2, y + h // 2)


def detect_flowchart_edges(image_path: str, nodes: List[Dict]) -> List[Dict]:
    img = _load_image(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=40, maxLineGap=10)

    if lines is None or not nodes:
        return []

    node_centers = [_center(n["bbox"]) for n in nodes]

    def nearest_node(pt):
        best_idx = -1
        best_dist = 1e9
        for i, c in enumerate(node_centers):
            dist = (pt[0] - c[0]) ** 2 + (pt[1] - c[1]) ** 2
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
        if d1 > 5000 or d2 > 5000:
            continue
        edges_out.append({
            "from": f"n{start_idx+1}",
            "to": f"n{end_idx+1}",
            "label": ""
        })

    # dedupe edges
    uniq = {}
    for e in edges_out:
        key = (e["from"], e["to"], e["label"])
        uniq[key] = e
    return list(uniq.values())


def build_flowchart_from_cv(image_url: str) -> Dict:
    path = _download_image(image_url)
    try:
        nodes_raw = detect_flowchart_nodes(path)
        nodes = []
        for idx, n in enumerate(nodes_raw, start=1):
            nodes.append({
                "id": f"n{idx}",
                "label": "",
                "shape": n.get("shape", "other"),
                "bbox": n.get("bbox")
            })
        edges = detect_flowchart_edges(path, nodes)
        return {"nodes": nodes, "edges": edges}
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
