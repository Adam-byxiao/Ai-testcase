from blueprint_main.domain.flow_graph import FlowGraph, FlowGraphEdge, FlowGraphNode
from blueprint_main.services.structured_flow_tree_builder import StructuredFlowTreeBuilder


def test_build_structured_sequence():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Start"),
            FlowGraphNode(id="B", name="Input"),
            FlowGraphNode(id="C", name="Submit"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert [child.id for child in tree.root.children] == ["A", "B", "C"]


def test_build_structured_branch():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="是否继续?", is_decision=True),
            FlowGraphNode(id="B", name="Continue"),
            FlowGraphNode(id="C", name="Cancel"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B", "pins": [{"name": "yes"}]}),
            FlowGraphEdge.model_validate({"from": "A", "to": "C", "pins": [{"name": "no"}]}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert tree.root.children[0].type == "step"
    assert tree.root.children[1].type == "branch"
    labels = [branch.label for branch in tree.root.children[1].branches]
    assert labels == ["yes", "no"]


def test_build_structured_loop_with_exit():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Enter setup code"),
            FlowGraphNode(id="B", name="Identify this Bot"),
            FlowGraphNode(id="C", name="Remote setup"),
            FlowGraphNode(id="D", name="Finish"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "A", "pins": [{"name": "cancel"}]}),
            FlowGraphEdge.model_validate({"from": "C", "to": "D", "pins": [{"name": "next"}]}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    loop_node = tree.root.children[0]
    assert loop_node.type == "loop"
    assert set(loop_node.members) == {"A", "B", "C"}
    assert loop_node.entry in {"A", "B", "C"}
    assert any(edge["id"] == "A" for edge in loop_node.back_edges)
    assert any(edge["id"] == "D" for edge in loop_node.exit_edges)


def test_build_structured_branch_with_merge_like_tail():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="是否继续?", is_decision=True),
            FlowGraphNode(id="B", name="Path Yes"),
            FlowGraphNode(id="C", name="Path No"),
            FlowGraphNode(id="D", name="Merged Tail"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B", "pins": [{"name": "yes"}]}),
            FlowGraphEdge.model_validate({"from": "A", "to": "C", "pins": [{"name": "no"}]}),
            FlowGraphEdge.model_validate({"from": "B", "to": "D"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "D"}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert tree.root.children[1].type == "branch"
    yes_branch = tree.root.children[1].branches[0].child
    no_branch = tree.root.children[1].branches[1].child
    assert yes_branch.type == "sequence"
    assert no_branch.type == "sequence"
    assert [child.id for child in yes_branch.children] == ["B", "D"]
    assert [child.id for child in no_branch.children] == ["C", "D"]


def test_build_structured_loop_followed_by_branch():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Enter setup code"),
            FlowGraphNode(id="B", name="Identify bot"),
            FlowGraphNode(id="C", name="Remote setup"),
            FlowGraphNode(id="D", name="是否完成?", is_decision=True),
            FlowGraphNode(id="E", name="Success"),
            FlowGraphNode(id="F", name="Retry later"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "A", "pins": [{"name": "cancel"}]}),
            FlowGraphEdge.model_validate({"from": "C", "to": "D", "pins": [{"name": "next"}]}),
            FlowGraphEdge.model_validate({"from": "D", "to": "E", "pins": [{"name": "yes"}]}),
            FlowGraphEdge.model_validate({"from": "D", "to": "F", "pins": [{"name": "no"}]}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert tree.root.children[0].type == "loop"
    assert tree.root.children[1].id == "D"
    assert tree.root.children[2].type == "branch"
    assert [branch.label for branch in tree.root.children[2].branches] == ["yes", "no"]


def test_build_structured_multiple_entry_subgraphs():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Root A"),
            FlowGraphNode(id="B", name="Tail A"),
            FlowGraphNode(id="X", name="Root X"),
            FlowGraphNode(id="Y", name="Tail X"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "X", "to": "Y"}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert tree.roots == ["Root A", "Root X"]
    assert [child.id for child in tree.root.children] == ["A", "B", "X", "Y"]


def test_build_structured_branch_inside_loop():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Input code"),
            FlowGraphNode(id="B", name="是否识别成功?", is_decision=True),
            FlowGraphNode(id="C", name="Retry"),
            FlowGraphNode(id="D", name="Enroll"),
            FlowGraphNode(id="E", name="Finish"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C", "pins": [{"name": "no"}]}),
            FlowGraphEdge.model_validate({"from": "B", "to": "D", "pins": [{"name": "yes"}]}),
            FlowGraphEdge.model_validate({"from": "C", "to": "A", "pins": [{"name": "retry"}]}),
            FlowGraphEdge.model_validate({"from": "D", "to": "E"}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    loop_node = tree.root.children[0]
    assert loop_node.type == "loop"
    assert set(loop_node.members) == {"A", "B", "C"}
    assert loop_node.body is not None
    assert loop_node.body.type == "sequence"
    body_ids = [child.id for child in loop_node.body.children]
    assert body_ids[:2] == ["A", "B"]
    assert any(child.type == "branch" for child in loop_node.body.children)
    assert any(edge["id"] == "A" for edge in loop_node.back_edges)
    assert any(edge["id"] == "D" for edge in loop_node.exit_edges)
    assert tree.root.children[1].id == "D"
    assert tree.root.children[2].id == "E"


def test_build_structured_loop_body_keeps_internal_branch_shape():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Enter Code"),
            FlowGraphNode(id="B", name="Is Valid?", is_decision=True),
            FlowGraphNode(id="C", name="Retry Input"),
            FlowGraphNode(id="D", name="Choose Device"),
            FlowGraphNode(id="E", name="Confirm Device"),
            FlowGraphNode(id="F", name="Finish"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C", "pins": [{"name": "no"}]}),
            FlowGraphEdge.model_validate({"from": "B", "to": "D", "pins": [{"name": "yes"}]}),
            FlowGraphEdge.model_validate({"from": "C", "to": "A", "pins": [{"name": "retry"}]}),
            FlowGraphEdge.model_validate({"from": "D", "to": "E"}),
            FlowGraphEdge.model_validate({"from": "E", "to": "A", "pins": [{"name": "reselect"}]}),
            FlowGraphEdge.model_validate({"from": "E", "to": "F", "pins": [{"name": "confirm"}]}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    loop_node = tree.root.children[0]
    assert loop_node.type == "loop"
    assert loop_node.body is not None
    assert loop_node.body.type == "sequence"
    assert loop_node.body.children[0].id == "A"
    assert loop_node.body.children[1].id == "B"
    branch_node = loop_node.body.children[2]
    assert branch_node.type == "branch"
    assert [branch.label for branch in branch_node.branches] == ["no", "yes"]
    assert branch_node.branches[0].child.type == "step"
    assert branch_node.branches[0].child.id == "C"
    assert branch_node.branches[1].child.type == "sequence"
    assert [child.id for child in branch_node.branches[1].child.children] == ["D", "E"]
    assert any(edge["id"] == "F" for edge in loop_node.exit_edges)


def test_build_structured_self_loop_as_loop():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Retry same step"),
            FlowGraphNode(id="B", name="Done"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "A", "pins": [{"name": "retry"}]}),
            FlowGraphEdge.model_validate({"from": "A", "to": "B", "pins": [{"name": "continue"}]}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    loop_node = tree.root.children[0]
    assert loop_node.type == "loop"
    assert loop_node.entry == "A"
    assert loop_node.members == ["A"]
    assert any(edge["id"] == "A" for edge in loop_node.back_edges)
    assert any(edge["id"] == "B" for edge in loop_node.exit_edges)


def test_build_structured_complex_cycle_region_keeps_loop_block():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="A"),
            FlowGraphNode(id="B", name="B"),
            FlowGraphNode(id="C", name="C"),
            FlowGraphNode(id="D", name="D"),
            FlowGraphNode(id="E", name="E"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "D"}),
            FlowGraphEdge.model_validate({"from": "D", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "D", "to": "E"}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert tree.root.children[0].id == "A"
    loop_node = tree.root.children[1]
    assert loop_node.type == "loop"
    assert set(loop_node.members) == {"B", "C", "D"}
    assert any(edge["id"] == "E" for edge in loop_node.exit_edges)


def test_build_structured_nested_loop_region():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="A", name="Outer Start"),
            FlowGraphNode(id="B", name="Inner Start"),
            FlowGraphNode(id="C", name="Inner Middle"),
            FlowGraphNode(id="D", name="Inner End"),
            FlowGraphNode(id="E", name="Outer End"),
            FlowGraphNode(id="F", name="Finish"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "A", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "D"}),
            FlowGraphEdge.model_validate({"from": "D", "to": "B", "pins": [{"name": "retry inner"}]}),
            FlowGraphEdge.model_validate({"from": "D", "to": "E", "pins": [{"name": "inner done"}]}),
            FlowGraphEdge.model_validate({"from": "E", "to": "A", "pins": [{"name": "retry outer"}]}),
            FlowGraphEdge.model_validate({"from": "E", "to": "F", "pins": [{"name": "finish"}]}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    loop_node = tree.root.children[0]
    assert loop_node.type in {"loop", "loop_region"}
    assert set(loop_node.members) == {"A", "B", "C", "D", "E"}
    assert any(edge["id"] == "A" for edge in loop_node.back_edges)
    assert any(edge["id"] == "F" for edge in loop_node.exit_edges)


def test_build_structured_multi_entry_region_as_loop_region():
    graph = FlowGraph(
        nodes=[
            FlowGraphNode(id="S1", name="Entry One"),
            FlowGraphNode(id="S2", name="Entry Two"),
            FlowGraphNode(id="A", name="Shared A"),
            FlowGraphNode(id="B", name="Shared B"),
            FlowGraphNode(id="C", name="Shared C"),
            FlowGraphNode(id="Z", name="Exit"),
        ],
        edges=[
            FlowGraphEdge.model_validate({"from": "S1", "to": "A"}),
            FlowGraphEdge.model_validate({"from": "S2", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "A", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "B", "to": "C"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "A"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "B"}),
            FlowGraphEdge.model_validate({"from": "C", "to": "Z"}),
        ],
    )

    tree = StructuredFlowTreeBuilder.build(graph)

    assert tree.root.type == "sequence"
    assert tree.roots == ["Entry One", "Entry Two"]
    region_nodes = [child for child in tree.root.children if child.type == "loop_region"]
    assert region_nodes
    region = region_nodes[0]
    assert set(region.members) == {"A", "B", "C"}
    assert set(region.meta.get("entry_nodes") or []) == {"A", "B"}
    assert any(edge["id"] == "Z" for edge in region.exit_edges)
    assert region.body is not None
    assert region.body.type == "sequence"
    body_ids = [child.id for child in region.body.children if child.type == "step"]
    assert "A" in body_ids
    assert "B" in body_ids
