import os
import re
from typing import List, Dict, Any, Tuple


def _bbox_contains(container: List[float], inner: List[float]) -> bool:
    if not container or not inner:
        return False
    cx, cy, cw, ch = container
    ix, iy, iw, ih = inner
    return ix >= cx and iy >= cy and (ix + iw) <= (cx + cw) and (iy + ih) <= (cy + ch)


def _bbox_area(bbox: List[float]) -> float:
    if not bbox:
        return 0.0
    return max(0.0, bbox[2]) * max(0.0, bbox[3])


def _should_ignore(name: str, ignore_regex: str) -> bool:
    if not name:
        return False
    return re.search(ignore_regex, name, re.IGNORECASE) is not None


def _is_flow_name(name: str, include_regex: str) -> bool:
    if not name:
        return False
    return re.search(include_regex, name, re.IGNORECASE) is not None


def aggregate_flow_nodes(nodes: List[Dict[str, Any]], texts: List[Dict[str, Any]], include_regex: str, ignore_regex: str) -> List[Dict[str, Any]]:
    # pick top-level flow containers based on name or size
    candidates = []
    for n in nodes:
        name = n.get("name", "") or ""
        if _should_ignore(name, ignore_regex):
            continue
        if _is_flow_name(name, include_regex):
            candidates.append(n)

    # if no named candidates, fallback to largest containers
    if not candidates:
        nodes_sorted = sorted(nodes, key=lambda x: _bbox_area(x.get("bbox")), reverse=True)
        candidates = nodes_sorted[:5]

    # dedupe by bbox overlap (keep largest)
    candidates = sorted(candidates, key=lambda x: _bbox_area(x.get("bbox")), reverse=True)
    final_nodes = []
    for n in candidates:
        if not any(_bbox_contains(other.get("bbox"), n.get("bbox")) for other in final_nodes if other.get("bbox")):
            final_nodes.append(n)

    # attach texts inside each node bbox
    aggregated = []
    for idx, n in enumerate(final_nodes, start=1):
        bbox = n.get("bbox")
        label = n.get("name") or f"Node {idx}"
        components = []
        for t in texts:
            tb = t.get("bbox")
            if bbox and tb and _bbox_contains(bbox, tb):
                txt = t.get("text") or t.get("name") or ""
                if txt:
                    components.append(txt)
        aggregated.append({
            "id": n.get("id") or f"n{idx}",
            "label": label,
            "bbox": bbox,
            "components": components
        })
    return aggregated
