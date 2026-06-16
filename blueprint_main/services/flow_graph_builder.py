from __future__ import annotations

import re

from blueprint_main.domain.blueprint import BlueprintSnapshot
from blueprint_main.domain.flow_graph import FlowGraph, FlowGraphEdge, FlowGraphNode, FlowGraphPin, FlowGraphStats


class FlowGraphBuilder:
    @staticmethod
    def build_from_nodes(snapshot: BlueprintSnapshot) -> FlowGraph:
        node_map: dict[str, FlowGraphNode] = {}
        pin_to_node: dict[str, str] = {}

        for node in snapshot.nodes:
            node_map[node.id] = FlowGraphNode(id=node.id, name=node.name)
            pin_to_node[f"node-{node.id}"] = node.id
            for section in node.sections:
                for pin in section.pins:
                    pin_to_node[pin.id] = node.id

        raw_edges: list[FlowGraphEdge] = []
        skipped = 0
        for edge in snapshot.edges:
            source = pin_to_node.get(edge.from_)
            target = pin_to_node.get(edge.to)
            if not source or not target:
                skipped += 1
                continue
            raw_edges.append(FlowGraphEdge.model_validate({"from": source, "to": target}))

        unique_edges = FlowGraphBuilder._dedupe_edges(raw_edges)
        return FlowGraph(
            nodes=list(node_map.values()),
            edges=unique_edges,
            stats=FlowGraphStats(
                node_count=len(node_map),
                edge_count=len(unique_edges),
                skipped_edges=skipped,
            ),
        )

    @staticmethod
    def build_from_pins(snapshot: BlueprintSnapshot) -> FlowGraph:
        pin_nodes: list[FlowGraphPin] = []
        parent_nodes: dict[str, FlowGraphNode] = {}
        pin_map: set[str] = set()
        pin_to_parent: dict[str, str] = {}

        for node in snapshot.nodes:
            effective_name = FlowGraphBuilder._effective_node_name(node)
            parent_nodes[node.id] = FlowGraphNode(
                id=node.id,
                name=effective_name,
                is_decision=FlowGraphBuilder._is_decision_name(effective_name),
                sections=node.sections,
            )

            header_id = f"node-{node.id}"
            pin_nodes.append(
                FlowGraphPin(
                    id=header_id,
                    name=f"{node.name} / HEADER",
                    parent_id=node.id,
                    parent_name=node.name,
                    pin_name="HEADER",
                    side="right",
                )
            )
            pin_map.add(header_id)
            pin_to_parent[header_id] = node.id

            for section in node.sections:
                for pin in section.pins:
                    pin_nodes.append(
                        FlowGraphPin(
                            id=pin.id,
                            name=f"{node.name} / {pin.name}",
                            parent_id=node.id,
                            parent_name=node.name,
                            pin_name=pin.name,
                            side=pin.side or "left",
                            depth=pin.depth,
                        )
                    )
                    pin_map.add(pin.id)
                    pin_to_parent[pin.id] = node.id

        raw_pin_edges: list[FlowGraphEdge] = []
        skipped = 0
        for edge in snapshot.edges:
            if edge.from_ not in pin_map or edge.to not in pin_map:
                skipped += 1
                continue
            raw_pin_edges.append(
                FlowGraphEdge.model_validate(
                    {
                        "from": edge.from_,
                        "to": edge.to,
                        "source": edge.source,
                    }
                )
            )

        pin_edges = FlowGraphBuilder._dedupe_edges(raw_pin_edges)
        connected = {edge.from_ for edge in pin_edges} | {edge.to for edge in pin_edges}
        connected_pin_nodes = [pin for pin in pin_nodes if pin.id in connected]
        pin_lookup = {pin.id: pin for pin in connected_pin_nodes}

        parent_edge_map: dict[tuple[str, str], dict] = {}
        for edge in pin_edges:
            source_parent = pin_to_parent.get(edge.from_)
            target_parent = pin_to_parent.get(edge.to)
            if not source_parent or not target_parent:
                continue
            key = (source_parent, target_parent)
            parent_edge_map.setdefault(
                key,
                {
                    "from": source_parent,
                    "to": target_parent,
                    "pins": [],
                },
            )
            parent_edge_map[key]["pins"].append(
                {
                    "from_pin": pin_lookup.get(edge.from_).pin_name if pin_lookup.get(edge.from_) else edge.from_,
                    "to_pin": pin_lookup.get(edge.to).pin_name if pin_lookup.get(edge.to) else edge.to,
                }
            )

        parent_edges = [FlowGraphEdge.model_validate(edge) for edge in parent_edge_map.values()]
        return FlowGraph(
            nodes=list(parent_nodes.values()),
            edges=parent_edges,
            pin_nodes=connected_pin_nodes,
            pin_edges=pin_edges,
            stats=FlowGraphStats(
                node_count=len(parent_nodes),
                edge_count=len(parent_edges),
                skipped_edges=skipped,
            ),
        )

    @staticmethod
    def _dedupe_edges(edges: list[FlowGraphEdge]) -> list[FlowGraphEdge]:
        unique: list[FlowGraphEdge] = []
        seen: set[tuple[str, str]] = set()
        for edge in edges:
            key = (edge.from_, edge.to)
            if key in seen:
                continue
            seen.add(key)
            unique.append(edge)
        return unique

    @staticmethod
    def _is_decision_name(name: str) -> bool:
        lowered = (name or "").strip().lower()
        if not lowered:
            return False
        return "?" in lowered or " if " in f" {lowered} " or "是否" in lowered or "判断" in lowered or "判定" in lowered

    @staticmethod
    def _is_generic_container(name: str) -> bool:
        return bool(re.match(r"^(group|frame)\s*\d+", (name or "").strip().lower()))

    @classmethod
    def _effective_node_name(cls, node) -> str:
        if not cls._is_generic_container(node.name):
            return node.name
        for section in node.sections:
            for pin in section.pins:
                if cls._is_decision_name(pin.name):
                    return pin.name
        return node.name

