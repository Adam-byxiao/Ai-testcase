import os
import json
from typing import Any, Dict
from figma_indexer import build_json_index, filter_flow_nodes


def _get_bbox_for_node(figma_context_json: str, node_id: str | None) -> list | None:
    if not node_id:
        return None
    try:
        data = json.loads(figma_context_json)
    except Exception:
        return None
    target = None

    def walk(n: Dict[str, Any]):
        nonlocal target
        if not isinstance(n, dict):
            return
        if n.get("id") == node_id:
            target = n.get("bbox")
            return
        for c in n.get("children", []) or []:
            if isinstance(c, dict):
                walk(c)

    if isinstance(data, list):
        for root in data:
            if isinstance(root, dict):
                walk(root)
    elif isinstance(data, dict):
        walk(data)
    return target


def extract_flow_nodes_scoped(figma_context_json: str, node_id: str | None = None) -> Dict[str, Any]:
    index = build_json_index(figma_context_json)

    min_w = float(os.getenv("FLOW_NODE_MIN_W", "200"))
    min_h = float(os.getenv("FLOW_NODE_MIN_H", "200"))
    ignore_regex = os.getenv("FLOW_NODE_IGNORE_REGEX", "Background|BG|Stroke|Mask|Shadow|Glow")
    max_nodes = int(os.getenv("FLOWCHART_MAX_NODES", "15"))
    max_texts = int(os.getenv("FLOWCHART_MAX_TEXTS", "80"))

    frame_bbox = _get_bbox_for_node(figma_context_json, node_id)
    if not frame_bbox and index.get("frame_index"):
        frame_bbox = index["frame_index"][0].get("bbox")

    nodes = filter_flow_nodes(index, frame_bbox, min_w, min_h, ignore_regex) if frame_bbox else []
    nodes = nodes[:max_nodes]

    # Also include texts within the frame bbox
    texts = []
    for t in index.get("text_index", {}).values():
        bbox = t.get("bbox")
        if frame_bbox and bbox and (bbox[0] >= frame_bbox[0]) and (bbox[1] >= frame_bbox[1]) and (bbox[0]+bbox[2] <= frame_bbox[0]+frame_bbox[2]) and (bbox[1]+bbox[3] <= frame_bbox[1]+frame_bbox[3]):
            texts.append(t)
            if len(texts) >= max_texts:
                break

    return {
        "containers": nodes,
        "texts": texts,
        "frame_bbox": frame_bbox,
        "index_summary": {
            "total_nodes": len(index.get("node_index", {})),
            "total_texts": len(index.get("text_index", {})),
            "flow_nodes": len(nodes),
            "flow_texts": len(texts)
        }
    }
