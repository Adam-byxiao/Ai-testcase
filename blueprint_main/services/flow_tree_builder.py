from __future__ import annotations

from blueprint_main.domain.flow_graph import FlowGraph
from blueprint_main.domain.flow_tree import FlowCycleBlock, FlowTree, FlowTreeNode, FlowTreeStats


class _TarjanSCC:
    def __init__(self) -> None:
        self.index = 0
        self.stack: list[str] = []
        self.indices: dict[str, int] = {}
        self.lowlink: dict[str, int] = {}
        self.on_stack: dict[str, bool] = {}
        self.scc_map: dict[str, int] = {}
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
            scc: list[str] = []
            while True:
                current = self.stack.pop()
                self.on_stack[current] = False
                scc.append(current)
                if current == node_id:
                    break
            scc_id = len(self.scc_list)
            for item in scc:
                self.scc_map[item] = scc_id
            self.scc_list.append(scc)

    def find_sccs(self, nodes: list[dict], adj: dict[str, list[dict]]) -> tuple[dict[str, int], list[list[str]]]:
        self.index = 0
        self.stack = []
        self.indices = {}
        self.lowlink = {}
        self.on_stack = {}
        self.scc_map = {}
        self.scc_list = []
        self.adj = adj

        for node in nodes:
            node_id = node["id"]
            if node_id not in self.indices:
                self._dfs(node_id)
        return self.scc_map, self.scc_list


class FlowTreeBuilder:
    _tarjan = _TarjanSCC()

    @classmethod
    def build_with_cycles(cls, graph: FlowGraph) -> FlowTree:
        node_payloads = [node.model_dump() for node in graph.nodes]
        edge_payloads = [edge.model_dump(by_alias=True) for edge in graph.edges]

        adjacency: dict[str, list[dict]] = {}
        for node in node_payloads:
            adjacency[node["id"]] = []
        for edge in edge_payloads:
            source = edge["from"]
            target = edge["to"]
            if source in adjacency:
                adjacency[source].append({"id": target, "pins": edge.get("pins") or []})

        _, scc_list = cls._tarjan.find_sccs(node_payloads, adjacency)
        cycles = cls._find_cycle_blocks(scc_list, adjacency)

        in_cycle: dict[str, int] = {}
        for cycle_id, block in cycles.items():
            for node_id in block["internal"]:
                in_cycle[node_id] = cycle_id

        indegree = {node["id"]: 0 for node in node_payloads}
        cycle_external_indegree = {cycle_id: 0 for cycle_id in cycles}
        for edge in edge_payloads:
            source_cycle = in_cycle.get(edge["from"])
            target_cycle = in_cycle.get(edge["to"])
            if source_cycle is not None and source_cycle == target_cycle:
                continue
            indegree[edge["to"]] += 1
            if target_cycle is not None:
                cycle_external_indegree[target_cycle] += 1

        roots = [node_id for node_id, degree in indegree.items() if degree == 0 and node_id not in in_cycle]
        for cycle_id, block in cycles.items():
            if cycle_external_indegree.get(cycle_id, 0) == 0:
                roots.append(block["entry"])
        visited: set[str] = set()

        def build_tree(node_id: str):
            if node_id in visited:
                return None
            visited.add(node_id)

            cycle_id = in_cycle.get(node_id)
            if cycle_id is not None:
                return cls._build_cycle_tree(cycle_id, cycles[cycle_id], adjacency, visited)

            children: list[dict] = []
            for edge in adjacency.get(node_id, []):
                child = build_tree(edge["id"])
                if child:
                    child["edge_pins"] = edge.get("pins") or []
                    children.append(child)
            return {"id": node_id, "children": children}

        trees: list[FlowTreeNode] = []
        for root in roots:
            if root in visited:
                continue
            tree = build_tree(root)
            if tree:
                trees.append(FlowTreeNode.model_validate(tree))

        for cycle_id, block in cycles.items():
            if block["entry"] in visited:
                continue
            tree = cls._build_cycle_tree(cycle_id, block, adjacency, visited)
            trees.append(FlowTreeNode.model_validate(tree))

        return FlowTree(
            roots=roots,
            trees=trees,
            cycles={
                str(cycle_id): FlowCycleBlock(
                    entry=block["entry"],
                    internal=block["internal"],
                    exits=block["exits"],
                )
                for cycle_id, block in cycles.items()
            },
            stats=FlowTreeStats(
                root_count=len(roots),
                node_count=len(node_payloads),
                edge_count=len(edge_payloads),
                cycle_count=len(cycles),
            ),
        )

    @staticmethod
    def build_simple(graph: FlowGraph) -> FlowTree:
        node_payloads = [node.model_dump() for node in graph.nodes]
        edge_payloads = [edge.model_dump(by_alias=True) for edge in graph.edges]
        node_ids = [node["id"] for node in node_payloads]
        indegree = {node_id: 0 for node_id in node_ids}
        adjacency = {node_id: [] for node_id in node_ids}
        for edge in edge_payloads:
            source = edge["from"]
            target = edge["to"]
            if source in adjacency:
                adjacency[source].append({"id": target, "pins": edge.get("pins") or []})
            if target in indegree:
                indegree[target] += 1

        roots = [node_id for node_id, degree in indegree.items() if degree == 0]

        def build(node_id: str, path: set[str]):
            if node_id in path:
                return {"id": node_id, "cycle": True, "children": []}
            children = []
            for child in adjacency.get(node_id, []):
                child_tree = build(child["id"], path | {node_id})
                child_tree["edge_pins"] = child.get("pins") or []
                children.append(child_tree)
            return {"id": node_id, "children": children}

        trees = [FlowTreeNode.model_validate(build(root, set())) for root in roots]
        return FlowTree(
            roots=roots,
            trees=trees,
            stats=FlowTreeStats(
                root_count=len(roots),
                node_count=len(node_payloads),
                edge_count=len(edge_payloads),
            ),
        )

    @classmethod
    def _find_cycle_blocks(cls, sccs: list[list[str]], adjacency: dict[str, list[dict]]) -> dict[int, dict]:
        cycles: dict[int, dict] = {}
        for index, scc in enumerate(sccs):
            if len(scc) <= 1 and not cls._is_self_loop(scc, adjacency):
                continue
            entry = scc[0]
            cycles[index] = {
                "entry": entry,
                "internal": scc,
                "exits": [],
                "nested_in": None,
                "sub_cycles": [],
            }

        cycle_ids = list(cycles.keys())
        for cycle_id in cycle_ids:
            block = cycles[cycle_id]
            for other_cycle_id in cycle_ids:
                if cycle_id == other_cycle_id:
                    continue
                other_internal = set(cycles[other_cycle_id]["internal"])
                for node_id in block["internal"]:
                    if any(edge["id"] in other_internal for edge in adjacency.get(node_id, [])):
                        block["nested_in"] = other_cycle_id
                        cycles[other_cycle_id]["sub_cycles"].append(cycle_id)
                        break

        for cycle_id, block in cycles.items():
            cycle_set = set(block["internal"])
            for node_id in block["internal"]:
                for edge in adjacency.get(node_id, []):
                    if edge["id"] in cycle_set:
                        continue
                    block["exits"].append(
                        {
                            "from": node_id,
                            "to": edge["id"],
                            "pins": edge.get("pins") or [],
                        }
                    )

        return cycles

    @staticmethod
    def _is_self_loop(scc: list[str], adjacency: dict[str, list[dict]]) -> bool:
        if len(scc) != 1:
            return False
        node_id = scc[0]
        return any(edge["id"] == node_id for edge in adjacency.get(node_id, []))

    @classmethod
    def _build_cycle_tree(
        cls,
        cycle_id: int,
        block: dict,
        adjacency: dict[str, list[dict]],
        visited: set[str],
    ) -> dict:
        entry = block["entry"]
        cycle_set = set(block["internal"])

        def build_from(node_id: str, cycle_path: set[str]):
            if node_id in visited:
                return None
            visited.add(node_id)
            children = []

            for edge in adjacency.get(node_id, []):
                target = edge["id"]
                if target in cycle_set:
                    if target in cycle_path:
                        continue
                    child = build_from(target, cycle_path | {node_id})
                    if child:
                        child["edge_pins"] = edge.get("pins") or []
                        children.append(child)
                else:
                    children.append(
                        {
                            "id": target,
                            "exit": True,
                            "edge_pins": edge.get("pins") or [],
                            "children": [],
                        }
                    )

            return {
                "id": node_id,
                "type": "cycle_node",
                "entry_of": cycle_id,
                "children": children,
            }

        tree = build_from(entry, {entry})
        if tree:
            return tree
        return {"id": entry, "type": "cycle_node", "entry_of": cycle_id, "children": []}
