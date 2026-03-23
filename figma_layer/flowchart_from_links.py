from typing import Dict, Any, List


def build_flowchart_from_links(links: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes = {}
    edges = []
    for link in links:
        src = (link.get("from_name") or "").strip()
        dst = (link.get("to_name") or "").strip()
        if not src or not dst:
            continue
        nodes.setdefault(src, {"name": src})
        nodes.setdefault(dst, {"name": dst})
        edges.append({
            "from": src,
            "to": dst,
            "source": link.get("source")
        })

    # Build indegree
    indeg = {n: 0 for n in nodes}
    for e in edges:
        indeg[e["to"]] = indeg.get(e["to"], 0) + 1

    starts = [n for n, d in indeg.items() if d == 0]

    # Kahn topological sort (best-effort)
    queue = list(starts)
    topo = []
    indeg_work = dict(indeg)
    adj = {n: [] for n in nodes}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])

    while queue:
        n = queue.pop(0)
        topo.append(n)
        for m in adj.get(n, []):
            indeg_work[m] -= 1
            if indeg_work[m] == 0:
                queue.append(m)

    has_cycle = len(topo) != len(nodes)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "starts": starts,
        "topo": topo,
        "has_cycle": has_cycle
    }


def build_flowchart_with_visual_order(
    visual_nodes: List[Dict[str, Any]],
    json_edges: List[Dict[str, Any]],
    visual_edges: List[Dict[str, Any]] | None = None
) -> Dict[str, Any]:
    """
    Combine JSON edges with visual left-to-right ordering to build a logical flowchart.
    visual_nodes: [{label, bbox}]
    json_edges: [{from_name, to_name}]
    """
    # Order nodes by center-x
    def center_x(b):
        x, y, w, h = b
        return x + w / 2.0

    ordered = [n for n in visual_nodes if n.get("label") and n.get("bbox")]
    ordered.sort(key=lambda n: center_x(n["bbox"]))
    ordered_labels = [n["label"] for n in ordered]

    # Build edge set from json
    edge_set = set()
    edges = []
    for e in json_edges:
        src = (e.get("from_name") or "").strip()
        dst = (e.get("to_name") or "").strip()
        if not src or not dst:
            continue
        edge_set.add((src, dst))
        edges.append({"from": src, "to": dst, "source": "json"})

    # Override with visual edges if provided
    if visual_edges:
        for ve in visual_edges:
            src = (ve.get("from") or "").strip()
            dst = (ve.get("to") or "").strip()
            if not src or not dst:
                continue
            # remove conflicting json edge
            if (dst, src) in edge_set:
                edge_set.remove((dst, src))
                edges = [e for e in edges if not (e["from"] == dst and e["to"] == src)]
            if (src, dst) not in edge_set:
                edge_set.add((src, dst))
                edges.append({"from": src, "to": dst, "source": "vision"})

    # Add visual-order edges if missing
    for i in range(len(ordered_labels) - 1):
        a = ordered_labels[i]
        b = ordered_labels[i + 1]
        if (a, b) not in edge_set and (b, a) not in edge_set:
            edges.append({"from": a, "to": b, "source": "visual_order"})

    # Build topo / start / end / branches
    nodes = ordered_labels
    indeg = {n: 0 for n in nodes}
    outdeg = {n: 0 for n in nodes}
    for e in edges:
        indeg[e["to"]] = indeg.get(e["to"], 0) + 1
        outdeg[e["from"]] = outdeg.get(e["from"], 0) + 1
    starts = [n for n in nodes if indeg.get(n, 0) == 0]
    ends = [n for n in nodes if outdeg.get(n, 0) == 0]
    branches = [n for n in nodes if outdeg.get(n, 0) > 1 or indeg.get(n, 0) > 1]

    return {
        "ordered_nodes": ordered,
        "edges": edges,
        "starts": starts,
        "ends": ends,
        "branches": branches
    }
