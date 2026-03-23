from fastapi import FastAPI, HTTPException
from urllib.parse import urlparse, parse_qs
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import os
from datetime import datetime

from figma_mcp import fetch_figma_api_json
from dotenv import load_dotenv
from figma_image_exporter import export_figma_image
from figma_layer.figma_layer_links import extract_layer_links_from_file_json
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_ENV = os.path.join(BASE_DIR, "..", ".env")
load_dotenv(ROOT_ENV)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BlueprintConnections(BaseModel):
    file_key: str
    node_id: Optional[str] = None
    connections: List[dict]


def _parse_figma_url(maybe_url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        parsed = urlparse(maybe_url)
        if "figma.com" not in parsed.netloc:
            return None, None
        parts = [p for p in parsed.path.split("/") if p]
        file_key = None
        if "design" in parts:
            idx = parts.index("design")
            if idx + 1 < len(parts):
                file_key = parts[idx + 1]
        elif "file" in parts:
            idx = parts.index("file")
            if idx + 1 < len(parts):
                file_key = parts[idx + 1]
        qs = parse_qs(parsed.query)
        node_id = qs.get("node-id", [None])[0]
        return file_key, node_id
    except Exception:
        return None, None


def _extract_bbox(node: dict):
    bbox = node.get("absoluteBoundingBox") or node.get("absoluteRenderBounds")
    if isinstance(bbox, dict):
        return [
            float(bbox.get("x", 0)),
            float(bbox.get("y", 0)),
            float(bbox.get("width", 0)),
            float(bbox.get("height", 0)),
        ]
    return None


def _find_node_document(raw_json: dict, node_id: Optional[str]) -> Optional[dict]:
    if "nodes" in raw_json and node_id:
        node_entry = (raw_json.get("nodes") or {}).get(node_id)
        if node_entry and isinstance(node_entry, dict):
            return node_entry.get("document")
    if "document" in raw_json:
        return raw_json.get("document")
    return None


def _walk(node: dict, acc: list, depth: int = 0, path: Optional[list] = None):
    if path is None:
        path = []
    name = node.get("name") or ""
    acc.append((node, depth, path + [name]))
    for c in node.get("children", []) or []:
        if isinstance(c, dict):
            _walk(c, acc, depth + 1, path + [name])


def _infer_section(name: str) -> str:
    n = name.lower()
    if "fixed" in n:
        return "FIXED"
    if "scroll" in n:
        return "SCROLLS"
    if "header" in n:
        return "HEADER"
    if "footer" in n:
        return "FOOTER"
    return "MAIN"


def _infer_pin_side(name: str) -> str:
    n = name.lower()
    if re.search(r"(action|button|btn|icon|tap|click|confirm|cancel|close|stop|start|pause|play|record)", n):
        return "right"
    return "left"


@app.get("/api/blueprint/nodes")
async def blueprint_nodes(file_key: Optional[str] = None, node_id: Optional[str] = None):
    try:
        if not file_key:
            raise HTTPException(status_code=400, detail="file_key is required")
        # parse when file_key is actually a figma url
        if file_key and "http" in file_key:
            fk, nid = _parse_figma_url(file_key)
            file_key = fk or file_key
            node_id = nid or node_id
        if node_id and "-" in node_id and ":" not in node_id:
            node_id = node_id.replace("-", ":")
        raw_json = fetch_figma_api_json(file_key, node_id=node_id)

        # build groups by top-level frames/sections
        roots = []
        if "document" in raw_json:
            roots = [raw_json["document"]]
        elif "nodes" in raw_json:
            for _, n in (raw_json.get("nodes") or {}).items():
                doc = n.get("document")
                if doc:
                    roots.append(doc)

        all_nodes = []
        for r in roots:
            _walk(r, all_nodes)

        min_w = float(os.getenv("BLUEPRINT_NODE_MIN_W", "160"))
        min_h = float(os.getenv("BLUEPRINT_NODE_MIN_H", "120"))
        ignore_re = os.getenv("BLUEPRINT_NODE_IGNORE_REGEX", "Background|BG|Stroke|Mask|Shadow|Glow|Overlay|Union|Vector|Line")
        ignore = re.compile(ignore_re, re.I) if ignore_re else None

        def is_valid(n: dict):
            name = (n.get("name") or "").strip()
            if not name:
                return False
            if ignore and ignore.search(name):
                return False
            bbox = _extract_bbox(n)
            if not bbox:
                return False
            if bbox[2] < min_w or bbox[3] < min_h:
                return False
            t = n.get("type")
            return t in ("FRAME", "INSTANCE", "SECTION", "GROUP", "COMPONENT")

        # group by first-level children of document
        groups = []
        for r in roots:
            for top in r.get("children", []) or []:
                if not isinstance(top, dict):
                    continue
                top_bbox = _extract_bbox(top)
                if not top_bbox:
                    continue
                bucket = []
                tmp = []
                _walk(top, tmp)
                for n, depth, _ in tmp:
                    # only keep shallow nodes (screen-level)
                    if depth > 2:
                        continue
                    if is_valid(n):
                        bucket.append({
                            "id": n.get("id"),
                            "name": n.get("name"),
                            "type": n.get("type"),
                            "bbox": _extract_bbox(n),
                            "depth": depth
                        })
                if bucket:
                    groups.append({
                        "group_id": top.get("id"),
                        "group_name": top.get("name"),
                        "bbox": top_bbox,
                        "nodes": bucket
                    })

        # fallback to flat list if no groups
        nodes = []
        if not groups:
            for n, depth, _ in all_nodes:
                if depth > 2:
                    continue
                if is_valid(n):
                    nodes.append({
                        "id": n.get("id"),
                        "name": n.get("name"),
                        "type": n.get("type"),
                        "bbox": _extract_bbox(n),
                        "depth": depth
                    })
        else:
            for g in groups:
                nodes.extend(g["nodes"])
        image_url, used_node_id = export_figma_image(file_key, node_id=node_id)
        return {
            "figma": {
                "file_key": file_key,
                "node_id": used_node_id,
                "image_url": image_url
            },
            "nodes": nodes,
            "groups": groups
        }
    except Exception as e:
        print(f"[Blueprint] nodes_failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/blueprint/node")
async def blueprint_node(file_key: Optional[str] = None, node_id: Optional[str] = None):
    try:
        if not file_key:
            raise HTTPException(status_code=400, detail="file_key is required")
        if file_key and "http" in file_key:
            fk, nid = _parse_figma_url(file_key)
            file_key = fk or file_key
            node_id = nid or node_id
        if node_id and "-" in node_id and ":" not in node_id:
            node_id = node_id.replace("-", ":")
        if not node_id:
            raise HTTPException(status_code=400, detail="node_id is required for blueprint node")

        raw_json = fetch_figma_api_json(file_key, node_id=node_id)
        root = _find_node_document(raw_json, node_id)
        if not root:
            raise HTTPException(status_code=404, detail="node not found")

        node_meta = {
            "id": root.get("id"),
            "name": root.get("name"),
            "type": root.get("type"),
            "bbox": _extract_bbox(root),
        }

        pins = []
        tmp = []
        _walk(root, tmp)
        for n, depth, path in tmp:
            if depth == 0:
                continue
            name = (n.get("name") or "").strip()
            if not name:
                continue
            if n.get("visible") is False:
                continue
            bbox = _extract_bbox(n)
            pins.append({
                "id": n.get("id"),
                "name": name,
                "type": n.get("type"),
                "depth": depth,
                "path": " / ".join([p for p in path if p]),
                "bbox": bbox,
                "section": _infer_section(name),
                "side": _infer_pin_side(name),
            })

        # group pins by section
        sections = {}
        for p in pins:
            sections.setdefault(p["section"], []).append(p)

        # stable order
        section_list = []
        for k in ["FIXED", "SCROLLS", "HEADER", "FOOTER", "MAIN"]:
            if k in sections:
                section_list.append({"title": k, "pins": sections[k]})
        for k, v in sections.items():
            if k not in {s["title"] for s in section_list}:
                section_list.append({"title": k, "pins": v})

        image_url, used_node_id = export_figma_image(file_key, node_id=node_id)
        return {
            "figma": {
                "file_key": file_key,
                "node_id": used_node_id,
                "image_url": image_url,
            },
            "node": node_meta,
            "sections": section_list,
        }
    except Exception as e:
        print(f"[Blueprint] node_failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/blueprint/connections")
async def save_connections(payload: BlueprintConnections):
    report_dir = os.path.join(os.getcwd(), "output", "blueprint_connections")
    os.makedirs(report_dir, exist_ok=True)
    report = {
        "ts": datetime.now().isoformat(),
        "file_key": payload.file_key,
        "node_id": payload.node_id,
        "connections": payload.connections
    }
    report_name = f"connections_{payload.file_key}_{(payload.node_id or 'all').replace(':','-')}_{int(datetime.now().timestamp())}.json"
    report_path = os.path.join(report_dir, report_name)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return {"ok": True, "path": report_path}
