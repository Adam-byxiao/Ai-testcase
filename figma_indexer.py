import re
import json
from typing import Any, Dict, List


def build_json_index(figma_context_json: str) -> Dict[str, Any]:
    try:
        data = json.loads(figma_context_json)
    except Exception:
        return {
            "node_index": {},
            "text_index": {},
            "frame_index": [],
            "component_index": [],
            "line_index": []
        }

    node_index: Dict[str, Dict[str, Any]] = {}
    text_index: Dict[str, Dict[str, Any]] = {}
    frame_index: List[Dict[str, Any]] = []
    component_index: List[Dict[str, Any]] = []
    line_index: List[Dict[str, Any]] = []

    def walk(n: Dict[str, Any], parent_id: str | None = None):
        if not isinstance(n, dict):
            return
        node_id = n.get("id")
        node_type = n.get("type")
        node_name = n.get("name")
        bbox = n.get("bbox")

        if node_id:
            node_index[node_id] = {
                "id": node_id,
                "type": node_type,
                "name": node_name,
                "bbox": bbox,
                "parent_id": parent_id
            }

        if node_type in ("FRAME", "SECTION", "CANVAS") and bbox:
            frame_index.append({"id": node_id, "name": node_name, "bbox": bbox})

        if node_type == "TEXT" and bbox:
            text_index[node_id] = {
                "id": node_id,
                "name": node_name,
                "text": n.get("content", ""),
                "bbox": bbox,
                "parent_id": parent_id
            }

        if node_type in ("INSTANCE", "COMPONENT", "COMPONENT_SET") and bbox:
            component_index.append({"id": node_id, "name": node_name, "bbox": bbox})

        if node_type in ("LINE", "VECTOR", "BOOLEAN_OPERATION") and bbox:
            line_index.append({"id": node_id, "name": node_name, "bbox": bbox})

        for c in n.get("children", []) or []:
            if isinstance(c, dict):
                walk(c, node_id)

    if isinstance(data, list):
        for root in data:
            if isinstance(root, dict):
                walk(root, None)
    elif isinstance(data, dict):
        walk(data, None)

    return {
        "node_index": node_index,
        "text_index": text_index,
        "frame_index": frame_index,
        "component_index": component_index,
        "line_index": line_index
    }


def select_flowchart_frames(index: Dict[str, Any], name_regex: str) -> List[Dict[str, Any]]:
    rx = re.compile(name_regex, re.IGNORECASE)
    frames = []
    for f in index.get("frame_index", []):
        name = f.get("name", "") or ""
        if rx.search(name):
            frames.append(f)
    return frames


def bbox_contains(container: List[float], inner: List[float]) -> bool:
    if not container or not inner:
        return False
    cx, cy, cw, ch = container
    ix, iy, iw, ih = inner
    return ix >= cx and iy >= cy and (ix + iw) <= (cx + cw) and (iy + ih) <= (cy + ch)


def filter_flow_nodes(index: Dict[str, Any], frame_bbox: List[float], min_w: float, min_h: float, ignore_regex: str) -> List[Dict[str, Any]]:
    rx = re.compile(ignore_regex, re.IGNORECASE)
    nodes = []
    for node in index.get("node_index", {}).values():
        bbox = node.get("bbox")
        name = node.get("name", "") or ""
        ntype = node.get("type")
        if not bbox:
            continue
        if not bbox_contains(frame_bbox, bbox):
            continue
        if rx.search(name):
            continue
        if ntype not in ("FRAME", "GROUP", "COMPONENT", "INSTANCE", "SECTION"):
            continue
        w, h = bbox[2], bbox[3]
        if w < min_w or h < min_h:
            continue
        nodes.append(node)
    return nodes
