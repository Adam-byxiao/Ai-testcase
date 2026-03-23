from typing import List, Dict, Any, Tuple
import math
import re
import os
import json
from openai import OpenAI
from prompts import get_node_mapping_prompt


def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t


def _text_score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.75
    aset = set(na.split())
    bset = set(nb.split())
    if not aset or not bset:
        return 0.0
    return len(aset & bset) / max(len(aset), len(bset))


def _center(bbox: List[float]) -> Tuple[float, float]:
    x, y, w, h = bbox
    return (x + w / 2.0, y + h / 2.0)


def _dist_score(a: List[float], b: List[float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    d = math.hypot(ax - bx, ay - by)
    return 1.0 / (1.0 + d)


def match_visual_to_json_nodes(
    visual_nodes: List[Dict[str, Any]],
    json_nodes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Return mapping from visual label to json name with score.
    """
    results = []
    for v in visual_nodes:
        v_label = v.get("label") or v.get("meaning") or ""
        v_bbox = v.get("bbox")
        best = {"json_name": None, "score": 0.0}
        for j in json_nodes:
            j_name = j.get("name") or ""
            j_bbox = j.get("bbox")
            score = _text_score(v_label, j_name)
            if v_bbox and j_bbox:
                score = max(score, 0.4 * score + 0.6 * _dist_score(v_bbox, j_bbox))
            if score > best["score"]:
                best = {"json_name": j_name, "score": score}
        results.append({
            "visual_label": v_label,
            "json_name": best["json_name"],
            "score": round(best["score"], 3)
        })
    return {"mappings": results}


def match_visual_to_json_nodes_llm(
    visual_nodes: List[Dict[str, Any]],
    json_nodes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    prompt = get_node_mapping_prompt()
    payload = prompt.format(
        visual_nodes=json.dumps(visual_nodes, ensure_ascii=False),
        json_nodes=json.dumps(json_nodes, ensure_ascii=False)
    )
    base_url = os.getenv("OPENAI_BASE_URL")
    timeout_sec = float(os.getenv("OPENAI_TIMEOUT_SEC", "120"))
    model = os.getenv("OPENAI_FUSION_MODEL", "gpt-4o")
    client = OpenAI(base_url=base_url, timeout=timeout_sec) if base_url else OpenAI(timeout=timeout_sec)
    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": payload}
            ]
        }]
    )
    text = ""
    if hasattr(response, "output_text") and response.output_text:
        text = response.output_text
    if not text:
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "message":
                for content in getattr(item, "content", []) or []:
                    ctype = getattr(content, "type", None)
                    if ctype in ("output_text", "text"):
                        text += content.text
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
    return json.loads(text)
