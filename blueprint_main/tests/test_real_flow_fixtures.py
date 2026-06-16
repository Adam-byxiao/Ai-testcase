import json
from pathlib import Path

from blueprint_main.domain.flow_graph import FlowGraph
from blueprint_main.services.structured_flow_tree_builder import StructuredFlowTreeBuilder


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_graph_fixture(name: str) -> FlowGraph:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return FlowGraph.model_validate(payload)


def test_remote_setup_loop_fixture_builds_structured_loop():
    graph = _load_graph_fixture("remote_setup_loop_graph.json")

    structured_tree = StructuredFlowTreeBuilder.build(graph)

    assert structured_tree.root.type == "sequence"
    loop_node = structured_tree.root.children[0]
    assert loop_node.type == "loop"
    assert loop_node.entry == "enter_setup_code"
    assert set(loop_node.members) == {"enter_setup_code", "identify_bot", "remote_setup"}
    assert any(edge["id"] == "enter_setup_code" for edge in loop_node.back_edges)
    assert any(edge["id"] == "finish_enroll" for edge in loop_node.exit_edges)
