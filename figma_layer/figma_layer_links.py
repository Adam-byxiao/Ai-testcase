from typing import Dict, Any, List, Tuple
import html


ARROW_TOKENS = ["→", "-->", "->", "=>"]


def _iter_nodes(node: Dict[str, Any]):
    yield node
    for child in node.get("children", []) or []:
        yield from _iter_nodes(child)


def _collect_roots(file_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    roots: List[Dict[str, Any]] = []
    if "document" in file_json:
        roots.append(file_json.get("document"))
    elif "nodes" in file_json:
        for _, node in (file_json.get("nodes") or {}).items():
            doc = node.get("document")
            if doc:
                roots.append(doc)
    return [r for r in roots if r]

def _extract_bbox(node: Dict[str, Any]) -> List[float] | None:
    bbox = node.get("absoluteBoundingBox") or node.get("absoluteRenderBounds")
    if isinstance(bbox, dict):
        return [
            float(bbox.get("x", 0)),
            float(bbox.get("y", 0)),
            float(bbox.get("width", 0)),
            float(bbox.get("height", 0))
        ]
    return None


def _parse_arrow_name(name: str) -> Dict[str, str] | None:
    if not name:
        return None
    name = html.unescape(name).strip()
    token = None
    for t in ARROW_TOKENS:
        if t in name:
            token = t
            break
    if not token:
        return None
    parts = [p.strip() for p in name.split(token, 1)]
    if len(parts) != 2:
        return None
    left, right = parts
    if not left or not right:
        return None
    return {"from_name": left, "to_name": right}


def _collect_arrow_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen = set()
    for node in nodes:
        name = (node.get("name") or "").strip()
        parsed = _parse_arrow_name(name)
        if not parsed:
            continue
        node_id = node.get("id")
        key = (node_id, name)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "id": node_id,
            "name": html.unescape(name),
            "type": node.get("type"),
            "bbox": _extract_bbox(node)
        })
    return items


def _collect_named_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen = set()
    for node in nodes:
        node_type = node.get("type")
        if node_type not in ("FRAME", "INSTANCE", "COMPONENT", "SECTION", "GROUP"):
            continue
        name = (node.get("name") or "").strip()
        if not name:
            continue
        node_id = node.get("id")
        key = (node_id, name)
        if key in seen:
            continue
        seen.add(key)
        bbox = _extract_bbox(node)
        if not bbox:
            continue
        items.append({
            "id": node_id,
            "name": name,
            "type": node_type,
            "bbox": bbox
        })
    return items


def extract_layer_links_from_file_json(file_json: Dict[str, Any]) -> Dict[str, Any]:
    roots = _collect_roots(file_json)
    if not roots:
        return []

    id_to_name: Dict[str, str] = {}
    nodes: List[Dict[str, Any]] = []
    for root in roots:
        for node in _iter_nodes(root):
            nodes.append(node)
            node_id = node.get("id")
            node_name = node.get("name")
            if node_id and node_name:
                id_to_name[node_id] = node_name

    links: List[Dict[str, Any]] = []
    seen = set()

    # 1) Prototype reactions
    for node in nodes:
        reactions = node.get("reactions") or []
        if not reactions:
            continue
        for reaction in reactions:
            action = reaction.get("action") or {}
            dest_id = action.get("destinationId")
            if not dest_id:
                continue
            from_id = node.get("id")
            from_name = node.get("name") or ""
            to_name = id_to_name.get(dest_id, "")
            key = (from_id, dest_id, "reaction")
            if key in seen:
                continue
            seen.add(key)
            links.append({
                "from_id": from_id,
                "from_name": from_name,
                "to_id": dest_id,
                "to_name": to_name,
                "source": "reaction",
                "trigger": (reaction.get("trigger") or {}).get("type")
            })

    # 2) Name-based arrows
    for node in nodes:
        name = node.get("name") or ""
        parsed = _parse_arrow_name(name)
        if not parsed:
            continue
        key = (parsed["from_name"], parsed["to_name"], "name")
        if key in seen:
            continue
        seen.add(key)
        source = "vector" if node.get("type") == "VECTOR" else "name"
        links.append({
            "from_id": node.get("id"),
            "from_name": parsed["from_name"],
            "to_id": None,
            "to_name": parsed["to_name"],
            "source": source
        })

    arrow_nodes = _collect_arrow_nodes(nodes)
    name_nodes = _collect_named_nodes(nodes)
    return {
        "links": links,
        "arrow_nodes": arrow_nodes,
        "name_nodes": name_nodes
    }
