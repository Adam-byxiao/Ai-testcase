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


class BlueprintSnapshot(BaseModel):
    meta: dict
    nodes: List[dict]
    edges: List[dict]


class FlowBuildRequest(BaseModel):
    name: str
    folder: Optional[str] = None
    scope: Optional[str] = "pin"


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


def _bbox_union(a: list[float], b: list[float]) -> list[float]:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = min(ax, bx)
    y1 = min(ay, by)
    x2 = max(ax + aw, bx + bw)
    y2 = max(ay + ah, by + bh)
    return [x1, y1, x2 - x1, y2 - y1]


def _bbox_iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _bbox_contains(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    area_b = bw * bh
    return inter / area_b if area_b > 0 else 0.0


def _merge_sections(target: list[dict], incoming: list[dict]) -> list[dict]:
    by_title = {s["title"]: list(s.get("pins", [])) for s in target}
    for s in incoming:
        by_title.setdefault(s["title"], [])
        by_title[s["title"]].extend(s.get("pins", []))
    # stable order
    order = ["FIXED", "SCROLLS", "HEADER", "FOOTER", "MAIN"]
    out = []
    for k in order:
        if k in by_title:
            out.append({"title": k, "pins": by_title[k]})
    for k, v in by_title.items():
        if k not in order:
            out.append({"title": k, "pins": v})
    return out


def _is_decision_text(name: str) -> bool:
    if not name:
        return False
    n = name.strip().lower()
    if "?" in n:
        return True
    if " if " in f" {n} ":
        return True
    return "鏄惁" in n or "鍒ゆ柇" in n or "鍒ゅ畾" in n


def _node_has_pin_name(node: dict, candidates: set[str]) -> bool:
    for sec in node.get("sections") or []:
        for pin in sec.get("pins") or []:
            if (pin.get("name") or "").strip().upper() in candidates:
                return True
    return False


def _find_decision_label_in_node(node: dict) -> Optional[str]:
    node_name = (node.get("name") or "").strip()
    if _is_decision_text(node_name):
        return node_name
    for sec in node.get("sections") or []:
        for pin in sec.get("pins") or []:
            pin_name = (pin.get("name") or "").strip()
            if _is_decision_text(pin_name):
                return pin_name
    return None


def _is_polygon_like_decision_node(node: dict) -> bool:
    node_name = (node.get("name") or "").strip().lower()
    node_type = (node.get("type") or "").strip().upper()
    has_ports = _node_has_pin_name(node, {"IN", "YES", "NO"})
    if "polygon" in node_name or node_type == "POLYGON":
        return True
    return has_ports and not _find_decision_label_in_node(node)


def _bbox_x_overlap_ratio(a: list[float], b: list[float]) -> float:
    ax, _, aw, _ = a
    bx, _, bw, _ = b
    overlap = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    base = max(1.0, min(aw, bw))
    return overlap / base


def _bbox_vertical_gap(a: list[float], b: list[float]) -> float:
    _, ay, _, ah = a
    _, by, _, bh = b
    if ay <= by:
        return max(0.0, by - (ay + ah))
    return max(0.0, ay - (by + bh))


def _should_merge_decision_pair(shape_node: dict, label_node: dict) -> bool:
    shape_bbox = shape_node.get("bbox")
    label_bbox = label_node.get("bbox")
    if not shape_bbox or not label_bbox:
        return False
    if _bbox_x_overlap_ratio(shape_bbox, label_bbox) < 0.45:
        return False
    if _bbox_vertical_gap(shape_bbox, label_bbox) > 220:
        return False
    return True


def _merge_decision_node_pairs(nodes: list[dict]) -> list[dict]:
    ordered = sorted(
        [node for node in nodes if isinstance(node, dict)],
        key=lambda node: ((node.get("bbox") or [10**9, 10**9])[1], (node.get("bbox") or [10**9])[0]),
    )
    used: set[str] = set()
    merged_nodes: list[dict] = []

    def node_key(node: dict) -> str:
        return str(node.get("id") or node.get("name"))

    for node in ordered:
        key = node_key(node)
        if key in used:
            continue
        if not _is_polygon_like_decision_node(node):
            merged_nodes.append(node)
            used.add(key)
            continue

        best_match = None
        best_gap = 10**9
        for candidate in ordered:
            candidate_key = node_key(candidate)
            if candidate_key in used or candidate_key == key:
                continue
            label = _find_decision_label_in_node(candidate)
            if not label:
                continue
            if not _should_merge_decision_pair(node, candidate):
                continue
            gap = _bbox_vertical_gap(node.get("bbox"), candidate.get("bbox"))
            if gap < best_gap:
                best_gap = gap
                best_match = candidate

        if not best_match:
            merged_nodes.append(node)
            used.add(key)
            continue

        label = _find_decision_label_in_node(best_match) or best_match.get("name") or node.get("name")
        merged_nodes.append(
            {
                "id": f"decision-{key}",
                "name": label,
                "type": "DECISION",
                "bbox": _bbox_union(node.get("bbox"), best_match.get("bbox")),
                "sections": _merge_sections(node.get("sections", []), best_match.get("sections", [])),
                "merged_from": [node.get("id"), best_match.get("id")],
            }
        )
        used.add(key)
        used.add(node_key(best_match))

    return merged_nodes


def _merge_nodes_by_visual(nodes: list[dict]) -> list[dict]:
    groups = []
    for n in nodes:
        merged = False
        nb = n.get("bbox")
        if not nb:
            continue
        for g in groups:
            gb = g.get("bbox")
            if not gb:
                continue
            iou = _bbox_iou(nb, gb)
            contain = max(_bbox_contains(gb, nb), _bbox_contains(nb, gb))
            if iou > 0.15 or contain > 0.8:
                g["bbox"] = _bbox_union(gb, nb)
                g["sections"] = _merge_sections(g.get("sections", []), n.get("sections", []))
                g["name"] = f"{g['name']} + {n['name']}"
                merged = True
                break
        if not merged:
            groups.append(n)
    return groups


def _semantic_key(name: str) -> str:
    n = name.lower().strip()
    for sep in [" / ", "/", "-", "_"]:
        if sep in n:
            n = n.split(sep)[0]
            break
    n = re.sub(r"\d+", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    keywords = ["header", "footer", "nav", "tab", "panel", "dialog", "modal", "card", "list", "button", "icon"]
    for k in keywords:
        if k in n:
            return k
    return n[:24] if n else "group"


def _merge_nodes_by_semantic(nodes: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for n in nodes:
        key = _semantic_key(n.get("name") or "")
        if key not in buckets:
            buckets[key] = {**n}
            buckets[key]["name"] = n.get("name") or key
        else:
            buckets[key]["bbox"] = _bbox_union(buckets[key]["bbox"], n["bbox"])
            buckets[key]["sections"] = _merge_sections(buckets[key].get("sections", []), n.get("sections", []))
            buckets[key]["name"] = f"{buckets[key]['name']} + {n['name']}"
    return list(buckets.values())


def _snapshot_base_dir() -> str:
    return os.path.join(BASE_DIR, "output", "blueprint_snapshots")


def _load_snapshot_by_name(name: str, folder: Optional[str]) -> dict:
    base_dir = _snapshot_base_dir()
    report_dir = base_dir
    if folder:
        folder_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", folder)[:60]
        report_dir = os.path.join(base_dir, folder_safe)
    path = os.path.join(report_dir, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="snapshot not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_flow_graph_from_nodes(snapshot: dict) -> dict:
    nodes = snapshot.get("nodes") or []
    edges = snapshot.get("edges") or []

    node_map = {}
    for n in nodes:
        nid = n.get("id") or n.get("name")
        if nid:
            node_map[nid] = {"id": nid, "name": n.get("name") or str(nid)}

    pin_to_node = {}
    for n in nodes:
        nid = n.get("id") or n.get("name")
        for sec in n.get("sections") or []:
            for p in sec.get("pins") or []:
                pid = p.get("id")
                if pid:
                    pin_to_node[pid] = nid
        # include header pin id
        if nid:
            pin_to_node[f"node-{nid}"] = nid

    graph_edges = []
    skipped = 0
    for e in edges:
        frm = e.get("from")
        to = e.get("to")
        if not frm or not to:
            skipped += 1
            continue
        src = pin_to_node.get(frm)
        dst = pin_to_node.get(to)
        if not src or not dst:
            skipped += 1
            continue
        graph_edges.append({"from": src, "to": dst})

    # unique edges
    uniq = []
    seen = set()
    for e in graph_edges:
        key = (e["from"], e["to"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)

    return {
        "nodes": list(node_map.values()),
        "edges": uniq,
        "stats": {
            "node_count": len(node_map),
            "edge_count": len(uniq),
            "skipped_edges": skipped
        }
    }


def _build_flow_graph_from_pins(snapshot: dict) -> dict:
    nodes = snapshot.get("nodes") or []
    edges = snapshot.get("edges") or []

    pin_nodes = []
    pin_map = {}
    parent_nodes = {}
    node_sections = {}

    def _is_decision_name(name: str) -> bool:
        if not name:
            return False
        n = name.strip().lower()
        if "?" in n:
            return True
        if " if " in f" {n} ":
            return True
        if "是否" in n or "判断" in n or "判定" in n:
            return True
        return False

    def _is_generic_container(name: str) -> bool:
        if not name:
            return False
        n = name.strip().lower()
        return bool(re.match(r"^(group|frame)\s*\d+", n))

    def _infer_decision_label(node: dict) -> Optional[str]:
        for sec in node.get("sections") or []:
            for p in sec.get("pins") or []:
                pname = p.get("name") or ""
                if _is_decision_name(pname):
                    return pname
        return None

    for n in nodes:
        nid = n.get("id") or n.get("name")
        nname = n.get("name") or str(nid)
        if nid:
            node_sections[nid] = n.get("sections") or []
            decision_label = _infer_decision_label(n) if _is_generic_container(nname) else None
            effective_name = decision_label or nname
            parent_nodes[nid] = {
                "id": nid,
                "name": effective_name,
                "is_decision": _is_decision_name(effective_name)
            }
            header_id = f"node-{nid}"
            header_name = f"{nname} / HEADER"
            pin_nodes.append({
                "id": header_id,
                "name": header_name,
                "parent_id": nid,
                "parent_name": nname,
                "pin_name": "HEADER",
                "side": "right"
            })
            pin_map[header_id] = header_id
        for sec in n.get("sections") or []:
            for p in sec.get("pins") or []:
                pid = p.get("id")
                if not pid:
                    continue
                pname = p.get("name") or str(pid)
                pin_nodes.append({
                    "id": pid,
                    "name": f"{nname} / {pname}",
                    "parent_id": nid,
                    "parent_name": nname,
                    "pin_name": pname,
                    "side": p.get("side") or "left",
                    "depth": p.get("depth")
                })
                pin_map[pid] = pid

    graph_edges = []
    skipped = 0
    for e in edges:
        frm = e.get("from")
        to = e.get("to")
        if not frm or not to:
            skipped += 1
            continue
        if frm not in pin_map or to not in pin_map:
            skipped += 1
            continue
        graph_edges.append({"from": frm, "to": to})

    uniq = []
    seen = set()
    for e in graph_edges:
        key = (e["from"], e["to"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)

    # only keep pins that are actually connected
    connected = set()
    for e in uniq:
        connected.add(e["from"])
        connected.add(e["to"])
    pin_nodes = [n for n in pin_nodes if n["id"] in connected]

    # build parent-level graph with pin labels
    pin_parent = {n["id"]: n.get("parent_id") for n in pin_nodes if n.get("parent_id")}
    pin_lookup = {n["id"]: n for n in pin_nodes}
    parent_edges_map = {}
    decision_out_map = {}
    decision_in_count = {}
    for e in uniq:
        src_pin = e["from"]
        dst_pin = e["to"]
        src_parent = pin_parent.get(src_pin)
        dst_parent = pin_parent.get(dst_pin)
        if not src_parent or not dst_parent:
            continue
        if src_parent == dst_parent:
            continue
        src_meta = parent_nodes.get(src_parent) or {}
        dst_meta = parent_nodes.get(dst_parent) or {}
        src_is_decision = bool(src_meta.get("is_decision"))
        dst_is_decision = bool(dst_meta.get("is_decision"))

        def _decision_label(parent_id: str, target_id: str) -> str:
            if parent_id not in decision_out_map:
                decision_out_map[parent_id] = {}
            mapping = decision_out_map[parent_id]
            if target_id in mapping:
                return mapping[target_id]
            order = ["YES", "NO"]
            idx = len(mapping)
            label = order[idx] if idx < len(order) else f"OUT-{idx+1}"
            mapping[target_id] = label
            return label

        def _decision_port_from_pin(pin_name: Optional[str]) -> Optional[str]:
            if not pin_name:
                return None
            n = pin_name.strip().lower()
            if "yes" in n or "true" in n or "正确" in n or "是" == n:
                return "YES"
            if "no" in n or "false" in n or "错误" in n or "否" == n:
                return "NO"
            return None

        from_name = pin_lookup.get(src_pin, {}).get("name")
        to_name = pin_lookup.get(dst_pin, {}).get("name")
        if src_is_decision:
            forced = _decision_port_from_pin(pin_lookup.get(src_pin, {}).get("name"))
            port = forced or _decision_label(src_parent, dst_parent)
            from_name = f"{src_meta.get('name') or src_parent} / {port}"
        if dst_is_decision:
            decision_in_count[dst_parent] = decision_in_count.get(dst_parent, 0) + 1
            to_name = f"{dst_meta.get('name') or dst_parent} / IN"

        key = (src_parent, dst_parent)
        if key not in parent_edges_map:
            parent_edges_map[key] = {
                "from": src_parent,
                "to": dst_parent,
                "pins": []
            }
        parent_edges_map[key]["pins"].append({
            "from_pin": src_pin,
            "to_pin": dst_pin,
            "from_name": from_name,
            "to_name": to_name
        })

    parent_edges = list(parent_edges_map.values())
    parent_nodes_list = []
    for n in parent_nodes.values():
        if n.get("is_decision"):
            n["ports"] = {
                "in": ["IN"],
                "out": ["YES", "NO"]
            }
        n["sections"] = node_sections.get(n["id"]) or []
        parent_nodes_list.append(n)

    return {
        "nodes": parent_nodes_list,
        "edges": parent_edges,
        "pin_nodes": pin_nodes,
        "pin_edges": uniq,
        "stats": {
            "node_count": len(parent_nodes_list),
            "edge_count": len(parent_edges),
            "skipped_edges": skipped
        }
    }


# === Tarjan SCC for Cycle Detection ===
import sys
sys.setrecursionlimit(10000)


class _TarjanSCC:
    """Tarjan SCC finder - finds strongly connected components in a graph"""
    __slots__ = ('index', 'stack', 'lowlink', 'on_stack', 'scc_map', 'scc_list', 'adj')

    def __init__(self):
        self.index = 0
        self.stack = []
        self.lowlink = {}
        self.on_stack = {}
        self.scc_map = {}  # node_id -> scc_id
        self.scc_list = []  # list of sccs, each scc is a list of node_ids
        self.adj = {}

    def _dfs(self, v):
        self.index += 1
        self.lowlink[v] = self.index
        self.stack.append(v)
        self.on_stack[v] = True

        for edge in self.adj.get(v, []):
            w = edge["id"]
            if w not in self.lowlink:
                self._dfs(w)
                self.lowlink[v] = min(self.lowlink[v], self.lowlink[w])
            elif self.on_stack.get(w, False):
                self.lowlink[v] = min(self.lowlink[v], self.lowlink[w])

        if self.lowlink[v] == self.index:
            scc = []
            while True:
                w = self.stack.pop()
                self.on_stack[w] = False
                scc.append(w)
                if w == v:
                    break
            scc_id = len(self.scc_list)
            for node_id in scc:
                self.scc_map[node_id] = scc_id
            self.scc_list.append(scc)

    def find_sccs(self, nodes, adj):
        self.index = 0
        self.stack = []
        self.lowlink = {}
        self.on_stack = {}
        self.scc_map = {}
        self.scc_list = []
        self.adj = adj

        for n in nodes:
            nid = n["id"]
            if nid not in self.lowlink:
                self._dfs(nid)
        return self.scc_map, self.scc_list


_tarjan = _TarjanSCC()


def _find_sccs(nodes, adj):
    return _tarjan.find_sccs(nodes, adj)


def _is_self_loop(scc, adj):
    if len(scc) != 1:
        return False
    nid = scc[0]
    for edge in adj.get(nid, []):
        if edge["id"] == nid:
            return True
    return False


def _find_cycle_blocks(sccs, adj):
    """Find all cycles (SCCs with >1 node or self-loop)"""
    cycles = {}
    for i, scc in enumerate(sccs):
        if len(scc) > 1 or _is_self_loop(scc, adj):
            # Find entry node: node with external predecessor inside cycle
            entry = None
            cycle_set = set(scc)
            for n in scc:
                for e in adj.get(n, []):
                    if e["id"] in cycle_set and e["id"] != n:
                        # n has internal predecessor, might be entry
                        if entry is None:
                            entry = n
                # Also check external predecessors
                for edge in adj.get(n, []):
                    if edge["id"] in cycle_set:
                        continue
                    # External predecessor found, n has entry point
                    if entry is None or n == scc[0]:
                        entry = n
                        break
            if entry is None:
                entry = scc[0]

            cycles[i] = {
                "entry": entry,
                "internal": scc,
                "exits": [],
                "nested_in": None,
                "sub_cycles": []
            }

    # Find nesting relationships
    cycle_ids = list(cycles.keys())
    for cid in cycle_ids:
        block = cycles[cid]
        for other_cid in cycle_ids:
            if cid == other_cid:
                continue
            other_block = cycles[other_cid]
            other_set = set(other_block["internal"])
            for n in block["internal"]:
                for edge in adj.get(n, []):
                    w = edge["id"]
                    if w in other_set:
                        # block points to other_block, so block is nested inside other_block
                        block["nested_in"] = other_cid
                        other_block["sub_cycles"].append(cid)
                        break

    # Find exit edges for each cycle
    for cid, block in cycles.items():
        cycle_set = set(block["internal"])
        for n in block["internal"]:
            for e in adj.get(n, []):
                w = e["id"]
                if w not in cycle_set:
                    block["exits"].append({
                        "from": n,
                        "to": w,
                        "pins": e.get("pins") or []
                    })

    return cycles


def _has_external_pred(nid, cycle_set, adj):
    """Check if node has a predecessor outside the cycle"""
    for edge in adj.get(nid, []):
        if edge["id"] not in cycle_set:
            return True
    return False


def _build_cycle_tree(cycle_id, block, adj, cycle_blocks, visited):
    """Build tree structure for a cycle block, returns the entry node tree"""
    entry = block["entry"]
    cycle_set = set(block["internal"])

    # Recursive DAG builder that handles exit edges
    def build_from(v, in_cycle_path):
        if v in visited:
            return None
        visited.add(v)
        children = []

        for e in adj.get(v, []):
            w = e["id"]
            if w in cycle_set:
                # Edge inside cycle
                if w in in_cycle_path:
                    # Back edge - this is the cycle-back edge, skip it
                    continue
                child = build_from(w, in_cycle_path | {v})
                if child:
                    child["edge_pins"] = e.get("pins") or []
                    children.append(child)
            else:
                # Exit edge - node is outside cycle
                children.append({
                    "id": w,
                    "exit": True,
                    "edge_pins": e.get("pins") or [],
                    "children": []
                })

        return {
            "id": v,
            "type": "cycle_node",
            "entry_of": cycle_id,
            "children": children
        }

    entry_tree = build_from(entry, {entry})

    # If entry doesn't connect to anything in cycle (self-loop case), wrap it
    if not entry_tree:
        entry_tree = {"id": entry, "type": "cycle_node", "entry_of": cycle_id, "children": []}

    return entry_tree


def _build_flow_tree_with_cycles(graph: dict) -> dict:
    """Build flow tree handling cycles by expanding them as special nodes"""
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    # Build adjacency
    adj = {}
    node_map = {}
    for n in nodes:
        nid = n["id"]
        adj[nid] = []
        node_map[nid] = n

    for e in edges:
        src = e["from"]
        dst = e["to"]
        if src in adj:
            adj[src].append({"id": dst, "pins": e.get("pins") or []})

    # Find SCCs and cycles
    scc_map, scc_list = _find_sccs(nodes, adj)
    cycles = _find_cycle_blocks(scc_list, adj)

    # Classify nodes: in_cycle vs dag
    in_cycle = {}  # node_id -> cycle_id
    for cid, block in cycles.items():
        for n in block["internal"]:
            in_cycle[n] = cid

    # Build DAG indegree (ignoring edges within same cycle)
    indeg = {}
    for n in nodes:
        indeg[n["id"]] = 0
    for e in edges:
        src, dst = e["from"], e["to"]
        src_cycle = in_cycle.get(src)
        dst_cycle = in_cycle.get(dst)
        if src_cycle != dst_cycle:
            indeg[dst] += 1

    # Find roots (nodes with indegree 0 in DAG)
    roots = [nid for nid, d in indeg.items() if d == 0]

    visited = set()

    def build_tree(v):
        if v in visited:
            return None
        visited.add(v)

        cid = in_cycle.get(v)
        if cid is not None:
            block = cycles[cid]
            return _build_cycle_tree(cid, block, adj, cycles, visited)

        children = []
        for e in adj.get(v, []):
            w = e["id"]
            child = build_tree(w)
            if child:
                child["edge_pins"] = e.get("pins") or []
                children.append(child)

        return {"id": v, "children": children}

    trees = []
    for r in roots:
        if r not in visited:
            t = build_tree(r)
            if t:
                trees.append(t)

    # Also add top-level cycles that weren't reached from any root
    for cid, block in cycles.items():
        if block["entry"] not in visited:
            t = _build_cycle_tree(cid, block, adj, cycles, visited)
            trees.append(t)

    return {
        "roots": roots,
        "trees": trees,
        "cycles": {cid: {
            "entry": block["entry"],
            "internal": block["internal"],
            "exits": block["exits"]
        } for cid, block in cycles.items()},
        "stats": {
            "root_count": len(roots),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "cycle_count": len(cycles)
        }
    }


def _build_flow_tree(graph: dict) -> dict:
    """Legacy fallback: simple tree builder with cycle detection"""
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    node_ids = [n["id"] for n in nodes]
    indeg = {nid: 0 for nid in node_ids}
    adj = {nid: [] for nid in node_ids}
    for e in edges:
        src = e["from"]
        dst = e["to"]
        if src in adj:
            adj[src].append({"id": dst, "pins": e.get("pins") or []})
        if dst in indeg:
            indeg[dst] += 1

    roots = [nid for nid, d in indeg.items() if d == 0]

    def build(nid, path):
        if nid in path:
            return {"id": nid, "cycle": True, "children": []}
        children = []
        for c in adj.get(nid, []):
            child = build(c["id"], path | {nid})
            child["edge_pins"] = c.get("pins") or []
            children.append(child)
        return {"id": nid, "children": children}

    trees = [build(r, set()) for r in roots]
    return {
        "roots": roots,
        "trees": trees,
        "stats": {
            "root_count": len(roots),
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
    }


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


@app.post("/api/blueprint/save")
async def save_blueprint_snapshot(payload: BlueprintSnapshot):
    base_dir = os.path.join(BASE_DIR, "output", "blueprint_snapshots")
    os.makedirs(base_dir, exist_ok=True)
    meta = payload.meta or {}
    raw_key = meta.get("file_key") or "unknown"
    file_key = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_key)
    raw_folder = meta.get("folder") or file_key
    folder_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_folder)[:60]
    report_dir = os.path.join(base_dir, folder_safe)
    os.makedirs(report_dir, exist_ok=True)
    raw_name = meta.get("name") or "snapshot"
    name_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name)[:60]
    node_id = (meta.get("node_id") or "all").replace(":", "-")
    ts = meta.get("timestamp") or datetime.now().isoformat()
    name = f"{file_key}_{node_id}_{name_safe}_{int(datetime.now().timestamp())}.json"
    path = os.path.join(report_dir, name)
    report = {
        "meta": {
            "file_key": file_key,
            "node_id": meta.get("node_id"),
            "mode": meta.get("mode"),
            "timestamp": ts
        },
        "nodes": payload.nodes,
        "edges": payload.edges
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return {"ok": True, "path": path}


@app.get("/api/blueprint/snapshot/latest")
async def get_latest_snapshot(file_key: Optional[str] = None, node_id: Optional[str] = None):
    report_dir = os.path.join(os.getcwd(), "output", "blueprint_snapshots")
    if not os.path.exists(report_dir):
        raise HTTPException(status_code=404, detail="no snapshots")
    files = [f for f in os.listdir(report_dir) if f.endswith(".json")]
    if not files:
        raise HTTPException(status_code=404, detail="no snapshots")
    if file_key:
        files = [f for f in files if f.startswith(file_key)]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(report_dir, f)), reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="no snapshots for file_key")
    latest = files[0]
    with open(os.path.join(report_dir, latest), "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/api/blueprint/snapshot/list")
async def list_snapshots(file_key: Optional[str] = None, node_id: Optional[str] = None, folder: Optional[str] = None):
    base_dir = os.path.join(BASE_DIR, "output", "blueprint_snapshots")
    report_dir = base_dir
    if folder:
        folder_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", folder)[:60]
        report_dir = os.path.join(base_dir, folder_safe)
    if not os.path.exists(report_dir):
        return []
    files = [f for f in os.listdir(report_dir) if f.endswith(".json")]
    if file_key:
        safe_key = re.sub(r"[^a-zA-Z0-9._-]", "_", file_key)
        files = [f for f in files if f.startswith(safe_key)]
    if node_id:
        safe_node = node_id.replace(":", "-")
        files = [f for f in files if safe_node in f]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(report_dir, f)), reverse=True)
    out = []
    for f in files:
        path = os.path.join(report_dir, f)
        out.append({
            "name": f,
            "mtime": os.path.getmtime(path)
        })
    return out


@app.get("/api/blueprint/snapshot/folders")
async def list_snapshot_folders():
    base_dir = _snapshot_base_dir()
    if not os.path.exists(base_dir):
        return []
    items = []
    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)
        if os.path.isdir(path):
            items.append(name)
    items.sort()
    return items


@app.get("/api/blueprint/snapshot/get")
async def get_snapshot(name: str, folder: Optional[str] = None):
    base_dir = _snapshot_base_dir()
    report_dir = base_dir
    if folder:
        folder_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", folder)[:60]
        report_dir = os.path.join(base_dir, folder_safe)
    path = os.path.join(report_dir, name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="snapshot not found")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/api/blueprint/layers")
async def blueprint_layers(file_key: Optional[str] = None, node_id: Optional[str] = None, mode: Optional[str] = "A"):
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
            raise HTTPException(status_code=400, detail="node_id is required for blueprint layers")

        raw_json = fetch_figma_api_json(file_key, node_id=node_id)
        root = _find_node_document(raw_json, node_id)
        if not root:
            raise HTTPException(status_code=404, detail="node not found")

        root_bbox = _extract_bbox(root)

        nodes = []
        for child in (root.get("children") or []):
            if not isinstance(child, dict):
                continue
            child_bbox = _extract_bbox(child)
            if not child_bbox:
                continue
            child_name = (child.get("name") or "").strip()
            if not child_name:
                continue

            tmp = []
            _walk(child, tmp)
            pins = []
            for n, depth, path in tmp:
                if depth == 0:
                    continue
                name = (n.get("name") or "").strip()
                if not name:
                    continue
                if n.get("visible") is False:
                    continue
                pins.append({
                    "id": n.get("id"),
                    "name": name,
                    "type": n.get("type"),
                    "depth": depth,
                    "path": " / ".join([p for p in path if p]),
                    "bbox": _extract_bbox(n),
                    "section": _infer_section(name),
                    "side": _infer_pin_side(name),
                })

            sections = {}
            for p in pins:
                sections.setdefault(p["section"], []).append(p)
            section_list = []
            for k in ["FIXED", "SCROLLS", "HEADER", "FOOTER", "MAIN"]:
                if k in sections:
                    section_list.append({"title": k, "pins": sections[k]})
            for k, v in sections.items():
                if k not in {s["title"] for s in section_list}:
                    section_list.append({"title": k, "pins": v})

            nodes.append({
                "id": child.get("id"),
                "name": child_name,
                "type": child.get("type"),
                "bbox": child_bbox,
                "sections": section_list
            })

        mode_norm = (mode or "A").upper()
        if mode_norm == "B":
            nodes = _merge_nodes_by_visual(nodes)
        elif mode_norm == "C":
            nodes = _merge_nodes_by_semantic(nodes)
        nodes = _merge_decision_node_pairs(nodes)

        image_url, used_node_id = export_figma_image(file_key, node_id=node_id)
        return {
            "figma": {
                "file_key": file_key,
                "node_id": used_node_id,
                "image_url": image_url,
                "root_bbox": root_bbox
            },
            "mode": mode or "A",
            "nodes": nodes
        }
    except Exception as e:
        print(f"[Blueprint] layers_failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/blueprint/flow/graph")
async def build_flow_graph(payload: FlowBuildRequest):
    snapshot = _load_snapshot_by_name(payload.name, payload.folder)
    scope = (payload.scope or "pin").lower()
    if scope == "node":
        graph = _build_flow_graph_from_nodes(snapshot)
    else:
        graph = _build_flow_graph_from_pins(snapshot)
    out_dir = os.path.join(BASE_DIR, "output", "blueprint_flow")
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"flow_graph_{os.path.splitext(payload.name)[0]}.json"
    out_path = os.path.join(out_dir, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    return {"ok": True, "path": out_path, "graph": graph}


@app.post("/api/blueprint/flow/tree")
async def build_flow_tree(payload: FlowBuildRequest):
    snapshot = _load_snapshot_by_name(payload.name, payload.folder)
    scope = (payload.scope or "pin").lower()
    if scope == "node":
        graph = _build_flow_graph_from_nodes(snapshot)
    else:
        graph = _build_flow_graph_from_pins(snapshot)

    # Use cycle-aware tree builder
    tree = _build_flow_tree_with_cycles(graph)

    out_dir = os.path.join(BASE_DIR, "output", "blueprint_flow")
    os.makedirs(out_dir, exist_ok=True)
    out_name = f"flow_tree_{os.path.splitext(payload.name)[0]}.json"
    out_path = os.path.join(out_dir, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)
    return {"ok": True, "path": out_path, "tree": tree}
