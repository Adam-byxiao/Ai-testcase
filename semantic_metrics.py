import json
from typing import Any, Dict, List, Set

NORMALIZED_TYPES = [
    "Text",
    "Button",
    "Input",
    "Card",
    "Image",
    "Icon",
    "List",
    "Nav",
    "Container",
    "Chart",
    "Toggle",
    "Badge",
    "Avatar",
    "Table",
    "Modal",
    "Background",
    "Other"
]

FIGMA_TYPE_MAP = {
    "TEXT": "Text",
    "FRAME": "Container",
    "SECTION": "Container",
    "GROUP": "Container",
    "COMPONENT": "Container",
    "INSTANCE": "Container",
    "COMPONENT_SET": "Container",
    "CANVAS": "Container",
    "VECTOR": "Icon",
    "LINE": "Other",
    "RECTANGLE": "Background",
    "ELLIPSE": "Other",
    "STAR": "Other",
    "POLYGON": "Other",
    "SLICE": "Other",
    "BOOLEAN_OPERATION": "Other",
}

VISION_SYNONYMS = {
    "button": "Button",
    "cta": "Button",
    "input": "Input",
    "textfield": "Input",
    "text field": "Input",
    "text": "Text",
    "label": "Text",
    "title": "Text",
    "card": "Card",
    "panel": "Card",
    "image": "Image",
    "photo": "Image",
    "icon": "Icon",
    "avatar": "Avatar",
    "list": "List",
    "list item": "List",
    "navbar": "Nav",
    "navigation": "Nav",
    "tab": "Nav",
    "table": "Table",
    "chart": "Chart",
    "graph": "Chart",
    "toggle": "Toggle",
    "switch": "Toggle",
    "badge": "Badge",
    "modal": "Modal",
    "dialog": "Modal",
    "container": "Container",
    "background": "Background",
}


def _normalize_vision_type(t: str) -> str:
    if not t:
        return "Other"
    key = t.strip().lower()
    return VISION_SYNONYMS.get(key, "Other")


def _normalize_figma_type(t: str) -> str:
    if not t:
        return "Other"
    return FIGMA_TYPE_MAP.get(t, "Other")


def _traverse_json_nodes(node: Dict[str, Any], types: List[str]) -> None:
    node_type = node.get("type")
    if node_type:
        types.append(node_type)
    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            _traverse_json_nodes(child, types)


def _extract_json_types(json_context: str) -> List[str]:
    try:
        data = json.loads(json_context)
    except Exception:
        return []

    types: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                _traverse_json_nodes(item, types)
    elif isinstance(data, dict):
        _traverse_json_nodes(data, types)
    return types


def _extract_visual_types(visual_context: Any) -> List[str]:
    types: List[str] = []
    if isinstance(visual_context, str):
        try:
            visual_context = json.loads(visual_context)
        except Exception:
            return []
    if not isinstance(visual_context, dict):
        return []
    components = visual_context.get("components", []) or []
    for comp in components:
        if isinstance(comp, dict) and comp.get("type"):
            types.append(str(comp.get("type")))
    return types


def _count_types(type_list: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for t in type_list:
        counts[t] = counts.get(t, 0) + 1
    return counts


def compute_semantic_metrics(json_context: str, visual_context: Any) -> Dict[str, Any]:
    json_types = _extract_json_types(json_context)
    visual_types = _extract_visual_types(visual_context)

    json_normalized = [_normalize_figma_type(t) for t in json_types]
    visual_normalized = [_normalize_vision_type(t) for t in visual_types]

    json_type_set: Set[str] = set(json_normalized)
    visual_type_set: Set[str] = set(visual_normalized)

    overlap = json_type_set.intersection(visual_type_set)
    overlap_ratio = len(overlap) / max(1, len(visual_type_set))

    return {
        "json_node_count": len(json_types),
        "visual_component_count": len(visual_types),
        "json_type_counts": _count_types(json_types),
        "visual_type_counts": _count_types(visual_types),
        "normalized_json_type_counts": _count_types(json_normalized),
        "normalized_visual_type_counts": _count_types(visual_normalized),
        "type_overlap_ratio": round(overlap_ratio, 3),
        "overlap_types": sorted(list(overlap)),
        "taxonomy": NORMALIZED_TYPES
    }
