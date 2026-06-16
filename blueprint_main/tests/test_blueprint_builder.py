from blueprint_main.domain.blueprint import BlueprintMeta
from blueprint_main.services.blueprint_builder import BlueprintBuilder


def test_build_node_from_root_groups_pins_by_section():
    root = {
        "id": "screen-1",
        "name": "Shopping Cart",
        "type": "FRAME",
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 400, "height": 800},
        "children": [
            {
                "id": "header-1",
                "name": "Header Title",
                "type": "TEXT",
                "absoluteBoundingBox": {"x": 0, "y": 0, "width": 300, "height": 50},
            },
            {
                "id": "btn-1",
                "name": "Confirm Button",
                "type": "INSTANCE",
                "absoluteBoundingBox": {"x": 0, "y": 700, "width": 200, "height": 40},
            },
            {
                "id": "scroll-1",
                "name": "Scroll Content",
                "type": "FRAME",
                "absoluteBoundingBox": {"x": 0, "y": 60, "width": 300, "height": 500},
            },
        ],
    }

    node = BlueprintBuilder.build_node_from_root(root)

    assert node.id == "screen-1"
    assert [section.title for section in node.sections] == ["SCROLLS", "HEADER", "MAIN"]
    pins_by_section = {section.title: section.pins for section in node.sections}
    assert pins_by_section["HEADER"][0].name == "Header Title"
    assert pins_by_section["MAIN"][0].side == "right"


def test_build_snapshot_normalizes_meta_nodes_and_edges():
    snapshot = BlueprintBuilder.build_snapshot(
        BlueprintMeta(file_key="demo-file", node_id="10:1"),
        [
            {
                "id": "screen-1",
                "name": "Shopping Cart",
                "sections": [],
            }
        ],
        [{"from": "node-screen-1", "to": "pin-2"}],
    )

    assert snapshot.meta.file_key == "demo-file"
    assert snapshot.nodes[0].name == "Shopping Cart"
    assert snapshot.edges[0].from_ == "node-screen-1"

