from __future__ import annotations

from blueprint_main.domain.flow_graph import FlowGraph, FlowGraphNode
from blueprint_main.domain.structured_flow_tree import StructuredFlowBranch, StructuredFlowNode, StructuredFlowTree


class _TarjanSCC:
    def __init__(self) -> None:
        self.index = 0
        self.stack: list[str] = []
        self.indices: dict[str, int] = {}
        self.lowlink: dict[str, int] = {}
        self.on_stack: dict[str, bool] = {}
        self.scc_list: list[list[str]] = []
        self.adj: dict[str, list[dict]] = {}

    def _dfs(self, node_id: str) -> None:
        self.indices[node_id] = self.index
        self.lowlink[node_id] = self.index
        self.index += 1
        self.stack.append(node_id)
        self.on_stack[node_id] = True

        for edge in self.adj.get(node_id, []):
            target = edge["id"]
            if target not in self.indices:
                self._dfs(target)
                self.lowlink[node_id] = min(self.lowlink[node_id], self.lowlink[target])
            elif self.on_stack.get(target, False):
                self.lowlink[node_id] = min(self.lowlink[node_id], self.indices[target])

        if self.lowlink[node_id] == self.indices[node_id]:
            component: list[str] = []
            while True:
                current = self.stack.pop()
                self.on_stack[current] = False
                component.append(current)
                if current == node_id:
                    break
            self.scc_list.append(component)

    def find_sccs(self, node_ids: list[str], adj: dict[str, list[dict]]) -> list[list[str]]:
        self.index = 0
        self.stack = []
        self.indices = {}
        self.lowlink = {}
        self.on_stack = {}
        self.scc_list = []
        self.adj = adj
        for node_id in node_ids:
            if node_id not in self.indices:
                self._dfs(node_id)
        return self.scc_list


class StructuredFlowTreeBuilder:
    _tarjan = _TarjanSCC()

    @classmethod
    def build(cls, graph: FlowGraph) -> StructuredFlowTree:
        node_map = {node.id: node for node in graph.nodes}
        node_order = {node.id: index for index, node in enumerate(graph.nodes)}
        adjacency = {node.id: [] for node in graph.nodes}
        incoming = {node.id: [] for node in graph.nodes}
        for edge in graph.edges:
            payload = edge.model_dump(by_alias=True)
            adjacency[edge.from_].append({"id": edge.to, **payload})
            incoming[edge.to].append({"id": edge.from_, **payload})

        sccs = cls._tarjan.find_sccs(list(node_map.keys()), adjacency)
        cycle_components = {
            index: component
            for index, component in enumerate(sccs)
            if len(component) > 1 or cls._is_self_loop(component, adjacency)
        }

        node_to_component: dict[str, str] = {}
        component_meta: dict[str, dict] = {}
        for cycle_id, members in cycle_components.items():
            component_id = f"cycle:{cycle_id}"
            entry_nodes = cls._find_external_entry_nodes(members, incoming)
            component_type = "loop_region" if len(entry_nodes) > 1 else "loop"
            component_meta[component_id] = {
                "type": component_type,
                "members": members,
                "entry_nodes": entry_nodes,
            }
            for member in members:
                node_to_component[member] = component_id

        for node_id in node_map:
            if node_id in node_to_component:
                continue
            component_id = f"node:{node_id}"
            component_meta[component_id] = {"type": "node", "members": [node_id]}
            node_to_component[node_id] = component_id

        component_edges: dict[str, list[dict]] = {component_id: [] for component_id in component_meta}
        component_incoming: dict[str, list[dict]] = {component_id: [] for component_id in component_meta}
        seen_edges: set[tuple[str, str, str, str]] = set()
        for edge in graph.edges:
            source_component = node_to_component[edge.from_]
            target_component = node_to_component[edge.to]
            if source_component == target_component:
                continue
            dedupe_key = (source_component, target_component, edge.from_, edge.to)
            if dedupe_key in seen_edges:
                continue
            seen_edges.add(dedupe_key)
            payload = edge.model_dump(by_alias=True)
            component_edges[source_component].append(
                {
                    "id": target_component,
                    "edge": payload,
                }
            )
            component_incoming[target_component].append(
                {
                    "id": source_component,
                    "edge": payload,
                }
            )

        roots = [component_id for component_id, preds in component_incoming.items() if not preds]
        if not roots:
            roots = list(component_meta.keys())

        built_cache: dict[str, StructuredFlowNode] = {}

        def build_component(component_id: str) -> StructuredFlowNode:
            if component_id in built_cache:
                return built_cache[component_id]
            meta = component_meta[component_id]
            if meta["type"] in {"loop", "loop_region"}:
                loop_node = cls._build_loop_node(
                    component_id=component_id,
                    members=meta["members"],
                    component_type=meta["type"],
                    entry_nodes=meta.get("entry_nodes") or [],
                    node_map=node_map,
                    node_order=node_order,
                    adjacency=adjacency,
                    incoming=incoming,
                    node_to_component=node_to_component,
                    component_edges=component_edges,
                )
                outgoing = component_edges.get(component_id, [])
                if not outgoing:
                    node = loop_node
                elif len(outgoing) == 1:
                    node = cls._as_sequence([loop_node, build_component(outgoing[0]["id"])])
                else:
                    branch_node = StructuredFlowNode(
                        type="branch",
                        id=component_id,
                        title=loop_node.title,
                        branches=[
                            StructuredFlowBranch(
                                label=cls._edge_label(item["edge"]),
                                child=build_component(item["id"]),
                            )
                            for item in outgoing
                        ],
                        meta={"source_component": component_id, "after_loop": True},
                    )
                    node = cls._as_sequence([loop_node, branch_node])
            else:
                node = cls._build_acyclic_component(
                    component_id=component_id,
                    node_id=meta["members"][0],
                    node_map=node_map,
                    component_edges=component_edges,
                    build_component=build_component,
                )
            built_cache[component_id] = node
            return node

        root_nodes = [build_component(component_id) for component_id in roots]
        root = cls._as_sequence(root_nodes) if len(root_nodes) > 1 else root_nodes[0]
        return StructuredFlowTree(
            root=root,
            roots=[cls._component_display_name(component_id, component_meta, node_map) for component_id in roots],
            cycle_nodes={component_id: meta["members"] for component_id, meta in component_meta.items() if meta["type"] == "loop"},
        )

    @classmethod
    def _build_acyclic_component(
        cls,
        component_id: str,
        node_id: str,
        node_map: dict[str, FlowGraphNode],
        component_edges: dict[str, list[dict]],
        build_component,
    ) -> StructuredFlowNode:
        step = cls._step_node(node_map[node_id])
        outgoing = component_edges.get(component_id, [])
        if not outgoing:
            return step

        if len(outgoing) == 1 and not node_map[node_id].is_decision:
            child = build_component(outgoing[0]["id"])
            return cls._as_sequence([step, child])

        branch_title = node_map[node_id].name
        branches = []
        for item in outgoing:
            label = cls._edge_label(item["edge"])
            child = build_component(item["id"])
            branches.append(StructuredFlowBranch(label=label, child=child))

        branch_node = StructuredFlowNode(
            type="branch",
            id=node_id,
            title=branch_title,
            branches=branches,
            meta={"source_component": component_id},
        )
        return cls._as_sequence([step, branch_node])

    @classmethod
    def _build_loop_node(
        cls,
        component_id: str,
        members: list[str],
        component_type: str,
        entry_nodes: list[str],
        node_map: dict[str, FlowGraphNode],
        node_order: dict[str, int],
        adjacency: dict[str, list[dict]],
        incoming: dict[str, list[dict]],
        node_to_component: dict[str, str],
        component_edges: dict[str, list[dict]],
    ) -> StructuredFlowNode:
        member_set = set(members)
        entry = cls._pick_loop_entry(members, incoming, member_set, node_order, preferred=entry_nodes)
        ordered_members, back_edges = cls._walk_loop_body(entry, member_set, adjacency)
        if not ordered_members:
            ordered_members = [entry]
        body_roots = cls._ordered_unique(entry_nodes or [entry], node_order=node_order)
        body = cls._build_loop_body(
            root_ids=body_roots,
            member_set=member_set,
            node_map=node_map,
            node_order=node_order,
            adjacency=adjacency,
        )
        exit_edges = []
        for member in members:
            for edge in adjacency.get(member, []):
                if edge["id"] in member_set:
                    continue
                exit_edges.append(edge)

        return StructuredFlowNode(
            type=component_type,
            id=component_id,
            title=node_map[entry].name if entry in node_map else entry,
            entry=entry,
            members=members,
            body=body,
            back_edges=back_edges,
            exit_edges=exit_edges,
            meta={
                "source_component": component_id,
                "exit_targets": [item["id"] for item in component_edges.get(component_id, [])],
                "entry_nodes": entry_nodes,
            },
        )

    @classmethod
    def _build_loop_body(
        cls,
        root_ids: list[str],
        member_set: set[str],
        node_map: dict[str, FlowGraphNode],
        node_order: dict[str, int],
        adjacency: dict[str, list[dict]],
    ) -> StructuredFlowNode:
        root_ids = cls._ordered_unique(root_ids, node_order=node_order)
        covered_members = cls._reachable_members(root_ids, member_set, adjacency)
        remaining = sorted(
            [node_id for node_id in member_set if node_id not in covered_members],
            key=lambda node_id: node_order.get(node_id, 10**9),
        )
        build_roots = root_ids + remaining

        def build_node(node_id: str, path: tuple[str, ...]) -> StructuredFlowNode:
            step = cls._step_node(node_map[node_id])
            internal_edges = [
                edge for edge in adjacency.get(node_id, [])
                if edge["id"] in member_set and edge["id"] not in path
            ]
            internal_edges.sort(
                key=lambda edge: (
                    node_order.get(edge["id"], 10**9),
                    cls._edge_label(edge) or "",
                    edge["id"],
                )
            )
            if not internal_edges:
                return step

            if len(internal_edges) == 1 and not node_map[node_id].is_decision:
                child = build_node(internal_edges[0]["id"], path + (node_id,))
                return cls._as_sequence([step, child])

            branches = [
                StructuredFlowBranch(
                    label=cls._edge_label(edge),
                    child=build_node(edge["id"], path + (node_id,)),
                )
                for edge in internal_edges
            ]
            branch_node = StructuredFlowNode(
                type="branch",
                id=node_id,
                title=node_map[node_id].name,
                branches=branches,
                meta={"inside_loop": True},
            )
            return cls._as_sequence([step, branch_node])

        children = [build_node(node_id, tuple()) for node_id in build_roots]
        return cls._as_sequence(children)

    @staticmethod
    def _find_external_entry_nodes(members: list[str], incoming: dict[str, list[dict]]) -> list[str]:
        member_set = set(members)
        return [node_id for node_id in members if any(edge["from"] not in member_set for edge in incoming.get(node_id, []))]

    @staticmethod
    def _pick_loop_entry(
        members: list[str],
        incoming: dict[str, list[dict]],
        member_set: set[str],
        node_order: dict[str, int],
        preferred: list[str] | None = None,
    ) -> str:
        if preferred:
            return min(preferred, key=lambda node_id: node_order.get(node_id, 10**9))
        for node_id in members:
            if any(edge["from"] not in member_set for edge in incoming.get(node_id, [])):
                return node_id
        return min(members, key=lambda node_id: node_order.get(node_id, 10**9))

    @classmethod
    def _walk_loop_body(cls, entry: str, member_set: set[str], adjacency: dict[str, list[dict]]) -> tuple[list[str], list[dict]]:
        ordered: list[str] = []
        back_edges: list[dict] = []
        seen: set[str] = set()

        def dfs(node_id: str, stack: set[str]) -> None:
            if node_id in seen:
                return
            seen.add(node_id)
            ordered.append(node_id)
            for edge in adjacency.get(node_id, []):
                target = edge["id"]
                if target not in member_set:
                    continue
                if target in stack or target in seen:
                    back_edges.append(edge)
                    continue
                dfs(target, stack | {node_id})

        dfs(entry, {entry})
        for node_id in member_set:
            if node_id not in seen:
                ordered.append(node_id)
        return ordered, back_edges

    @staticmethod
    def _reachable_members(root_ids: list[str], member_set: set[str], adjacency: dict[str, list[dict]]) -> set[str]:
        reachable: set[str] = set()
        stack = [node_id for node_id in root_ids if node_id in member_set]
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            for edge in adjacency.get(node_id, []):
                target = edge["id"]
                if target in member_set and target not in reachable:
                    stack.append(target)
        return reachable

    @staticmethod
    def _ordered_unique(node_ids: list[str], node_order: dict[str, int]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for node_id in sorted(node_ids, key=lambda item: (node_order.get(item, 10**9), item)):
            if node_id in seen:
                continue
            seen.add(node_id)
            ordered.append(node_id)
        return ordered

    @staticmethod
    def _step_node(node: FlowGraphNode) -> StructuredFlowNode:
        return StructuredFlowNode(
            type="step",
            id=node.id,
            title=node.name,
            meta={"is_decision": node.is_decision},
        )

    @staticmethod
    def _as_sequence(children: list[StructuredFlowNode]) -> StructuredFlowNode:
        flattened: list[StructuredFlowNode] = []
        for child in children:
            if child.type == "sequence":
                flattened.extend(child.children)
            else:
                flattened.append(child)
        return StructuredFlowNode(type="sequence", children=flattened)

    @staticmethod
    def _edge_label(edge: dict) -> str | None:
        pins = edge.get("pins") or []
        if not pins:
            return None
        pin = pins[0]
        return pin.get("name") or pin.get("from_pin") or pin.get("to_pin")

    @staticmethod
    def _is_self_loop(component: list[str], adjacency: dict[str, list[dict]]) -> bool:
        if len(component) != 1:
            return False
        node_id = component[0]
        return any(edge["id"] == node_id for edge in adjacency.get(node_id, []))

    @staticmethod
    def _component_display_name(component_id: str, component_meta: dict[str, dict], node_map: dict[str, FlowGraphNode]) -> str:
        meta = component_meta[component_id]
        if meta["type"] in {"loop", "loop_region"}:
            return meta["members"][0]
        node_id = meta["members"][0]
        return node_map[node_id].name if node_id in node_map else node_id
