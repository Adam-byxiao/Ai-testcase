from blueprint_main.domain.flow_graph import FlowGraph, FlowGraphEdge, FlowGraphNode
from blueprint_main.services.flow_tree_builder import FlowTreeBuilder


def test_build_simple_tree_for_linear_graph():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="A"),
            FlowGraphNode(id="B", name="B"),
            FlowGraphNode(id="C", name="C"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
        ],
    )

    tree = FlowTreeBuilder.build_simple(graph)

    assert tree.roots == ["A"]
    assert tree.stats.node_count == 3
    assert tree.trees[0].id == "A"
    assert tree.trees[0].children[0].id == "B"
    assert tree.trees[0].children[0].children[0].id == "C"


def test_build_cycle_tree_with_exit_node():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="A"),
            FlowGraphNode(id="B", name="B"),
            FlowGraphNode(id="C", name="C"),
            FlowGraphNode(id="D", name="D"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "D"}),
        ],
    )

    tree = FlowTreeBuilder.build_with_cycles(graph)

    assert tree.roots == ["A"]
    assert tree.stats.cycle_count == 1
    assert tree.trees[0].id == "A"
    cycle_entry = tree.trees[0].children[0]
    assert cycle_entry.type == "cycle_node"
    assert cycle_entry.id in {"B", "C"}
    exit_nodes = []
    for child in cycle_entry.children:
        exit_nodes.extend([grandchild.id for grandchild in child.children if grandchild.exit])
        if child.exit:
            exit_nodes.append(child.id)
    assert "D" in exit_nodes


def test_build_with_cycles_preserves_indegree_for_non_cycle_edges():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="A"),
            FlowGraphNode(id="B", name="B"),
            FlowGraphNode(id="C", name="C"),
            FlowGraphNode(id="D", name="D"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B", "pins": [{"name": "yes"}]}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "A", "to": "D", "pins": [{"name": "no"}]}),
        ],
    )

    tree = FlowTreeBuilder.build_with_cycles(graph)

    assert tree.roots == ["A"]
    assert [child.id for child in tree.trees[0].children] == ["B", "D"]
