from typing import Dict, Any, List, Tuple
import cv2


def _rel_to_abs(bbox_rel: List[float], w: int, h: int) -> List[float]:
    x, y, bw, bh = bbox_rel
    return [x * w, y * h, bw * w, bh * h]


def _center(bbox: List[float]) -> Tuple[float, float]:
    x, y, w, h = bbox
    return (x + w / 2.0, y + h / 2.0)

def _norm_text(text: str) -> str:
    import re
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t

def _load_image_size(image_path: str) -> Tuple[int, int]:
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Failed to read image")
    h, w = img.shape[:2]
    return w, h


def group_flow_by_banners(
    banners: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    arrow_nodes: List[Dict[str, Any]],
    image_path: str,
    fallback_edges: List[Dict[str, Any]] | None = None
) -> List[Dict[str, Any]]:
    if not banners:
        return []

    w, h = _load_image_size(image_path)

    # build node bbox lookup by name
    name_to_bbox: Dict[str, List[float]] = {}
    for n in nodes:
        name = (n.get("name") or "").strip()
        bbox = n.get("bbox")
        if name and isinstance(bbox, list) and len(bbox) == 4:
            name_to_bbox[name] = bbox

    # build arrow bbox lookup by parsed name
    arrow_bbox: Dict[Tuple[str, str], List[float]] = {}
    for a in arrow_nodes or []:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        if "->" in name or "→" in name or "-->" in name or "=>" in name:
            parts = name.replace("-->", "->").replace("→", "->").replace("=>", "->").split("->", 1)
            if len(parts) == 2:
                src = parts[0].strip()
                dst = parts[1].strip()
                if src and dst and a.get("bbox"):
                    arrow_bbox[(src, dst)] = a["bbox"]

    groups: List[Dict[str, Any]] = []
    for b in banners:
        bbox_rel = b.get("bbox") or []
        if not bbox_rel or len(bbox_rel) != 4:
            continue
        bbox_abs = _rel_to_abs(bbox_rel, w, h)
        bx, by, bw, bh = bbox_abs
        band = max(400.0, bh * 6.0)
        right_x = bx + bw
        right_min = right_x - max(40.0, bw * 0.05)

        # select nodes in same row band to the right
        group_nodes = []
        group_node_bboxes: Dict[str, List[float]] = {}
        for name, nb in name_to_bbox.items():
            cx, cy = _center(nb)
            if cx <= right_min:
                continue
            if cy < (by - band) or cy > (by + band):
                continue
            group_nodes.append(name)
            group_node_bboxes[name] = nb

        # select links where both ends are in group_nodes
        node_set = set(group_nodes)
        group_edges = []
        raw_arrows = []
        for e in links:
            src = (e.get("from_name") or "").strip()
            dst = (e.get("to_name") or "").strip()
            if not src or not dst:
                continue
            in_nodes = src in node_set and dst in node_set
            in_arrow_band = False
            ab = arrow_bbox.get((src, dst))
            if ab:
                ax, ay, aw, ah = ab
                acx, acy = _center([ax, ay, aw, ah])
                if acx > right_x and (by - band) <= acy <= (by + band):
                    in_arrow_band = True
            if in_nodes or in_arrow_band:
                group_edges.append({"from": src, "to": dst, "source": e.get("source")})
                raw_arrows.append(f"{src} -> {dst}")

        # fallback: use provided edges to anchor nodes
        if not group_edges and fallback_edges:
            for e in fallback_edges:
                src = (e.get("from") or "").strip()
                dst = (e.get("to") or "").strip()
                if not src or not dst:
                    continue
                if src in node_set or dst in node_set:
                    group_edges.append({"from": src, "to": dst, "source": "visual"})
                    raw_arrows.append(f"{src} -> {dst}")

        groups.append({
            "feature_label": b.get("label") or "",
            "banner_bbox": bbox_abs,
            "nodes": group_nodes,
            "edges": group_edges,
            "raw_arrows": raw_arrows,
            "confidence": b.get("confidence"),
            "node_bboxes": group_node_bboxes
        })

    return groups
