from __future__ import annotations

import re
from typing import Optional

from blueprint_main.domain.blueprint import (
    BlueprintEdge,
    BlueprintMeta,
    BlueprintNode,
    BlueprintPin,
    BlueprintSection,
    BlueprintSnapshot,
    sort_sections,
)


class BlueprintBuilder:
    @staticmethod
    def extract_bbox(node: dict) -> Optional[list[float]]:
        bbox = node.get("absoluteBoundingBox") or node.get("absoluteRenderBounds")
        if isinstance(bbox, dict):
            return [
                float(bbox.get("x", 0)),
                float(bbox.get("y", 0)),
                float(bbox.get("width", 0)),
                float(bbox.get("height", 0)),
            ]
        return None

    @staticmethod
    def infer_section(name: str) -> str:
        lowered = (name or "").lower()
        if "fixed" in lowered:
            return "FIXED"
        if "scroll" in lowered:
            return "SCROLLS"
        if "header" in lowered:
            return "HEADER"
        if "footer" in lowered:
            return "FOOTER"
        return "MAIN"

    @staticmethod
    def infer_pin_side(name: str) -> str:
        lowered = (name or "").lower()
        if re.search(
            r"(action|button|btn|icon|tap|click|confirm|cancel|close|stop|start|pause|play|record)",
            lowered,
        ):
            return "right"
        return "left"

    @classmethod
    def walk(cls, node: dict, acc: list[tuple[dict, int, list[str]]], depth: int = 0, path: Optional[list[str]] = None) -> None:
        current_path = list(path or [])
        name = node.get("name") or ""
        current_path.append(name)
        acc.append((node, depth, current_path))
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                cls.walk(child, acc, depth + 1, current_path)

    @classmethod
    def build_node_from_root(cls, root: dict) -> BlueprintNode:
        node_id = root.get("id") or root.get("name") or "unknown-node"
        tmp: list[tuple[dict, int, list[str]]] = []
        cls.walk(root, tmp)

        grouped: dict[str, list[BlueprintPin]] = {}
        for node, depth, path in tmp:
            if depth == 0:
                continue
            name = (node.get("name") or "").strip()
            if not name or node.get("visible") is False:
                continue
            pin = BlueprintPin(
                id=node.get("id") or f"{node_id}-{depth}-{len(grouped)}",
                name=name,
                type=node.get("type"),
                depth=depth,
                path=" / ".join([segment for segment in path if segment]),
                bbox=cls.extract_bbox(node),
                section=cls.infer_section(name),
                side=cls.infer_pin_side(name),
            )
            grouped.setdefault(pin.section or "MAIN", []).append(pin)

        sections = sort_sections(
            [BlueprintSection(title=title, pins=pins) for title, pins in grouped.items()]
        )
        return BlueprintNode(
            id=node_id,
            name=root.get("name") or node_id,
            type=root.get("type"),
            bbox=cls.extract_bbox(root),
            sections=sections,
            source_ref={"source": "figma_root"},
        )

    @staticmethod
    def build_snapshot(
        meta: BlueprintMeta | dict,
        nodes: list[BlueprintNode | dict],
        edges: list[BlueprintEdge | dict],
    ) -> BlueprintSnapshot:
        snapshot_meta = meta if isinstance(meta, BlueprintMeta) else BlueprintMeta.model_validate(meta)
        snapshot_nodes = [
            node if isinstance(node, BlueprintNode) else BlueprintNode.model_validate(node)
            for node in nodes
        ]
        snapshot_edges = [
            edge if isinstance(edge, BlueprintEdge) else BlueprintEdge.model_validate(edge)
            for edge in edges
        ]
        return BlueprintSnapshot(meta=snapshot_meta, nodes=snapshot_nodes, edges=snapshot_edges)

