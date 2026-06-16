from blueprint_main.services.blueprint_builder import BlueprintBuilder
from blueprint_main.services.flow_graph_builder import FlowGraphBuilder


def _build_snapshot():
    return BlueprintBuilder.build_snapshot(
        {"file_key": "demo"},
        [
            {
                "id": "node-a",
                "name": "Start",
                "sections": [
                    {
                        "title": "MAIN",
                        "pins": [{"id": "pin-a1", "name": "Go Next", "side": "right"}],
                    }
                ],
            },
            {
                "id": "node-b",
                "name": "Frame 1",
                "sections": [
                    {
                        "title": "MAIN",
                        "pins": [{"id": "pin-b1", "name": "是否继续?", "side": "left"}],
                    }
                ],
            },
        ],
        [{"from": "pin-a1", "to": "pin-b1"}],
    )


def test_build_flow_graph_from_nodes_maps_pin_edges_to_parent_nodes():
    graph = FlowGraphBuilder.build_from_nodes(_build_snapshot())

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].from_ == "node-a"
    assert graph.edges[0].to == "node-b"


def test_build_flow_graph_from_pins_promotes_decision_name():
    graph = FlowGraphBuilder.build_from_pins(_build_snapshot())

    node_names = {node.id: node.name for node in graph.nodes}
    assert node_names["node-b"] == "是否继续?"
    assert len(graph.pin_edges) == 1
    assert graph.stats.edge_count == 1
