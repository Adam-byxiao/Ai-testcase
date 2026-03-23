import os
from typing import List, Dict


def generate_edges_fallback(nodes: List[Dict]) -> List[Dict]:
    # fallback: sort left-to-right by bbox center
    def center_x(n):
        bbox = n.get("bbox") or [0, 0, 0, 0]
        return bbox[0] + bbox[2] / 2.0

    ordered = sorted(nodes, key=center_x)
    edges = []
    for i in range(len(ordered) - 1):
        edges.append({"from": ordered[i].get("id"), "to": ordered[i+1].get("id"), "label": ""})
    return edges
