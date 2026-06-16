from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from blueprint_main.domain.blueprint import BlueprintSection


class FlowGraphNode(BaseModel):
    id: str
    name: str
    is_decision: bool = False
    sections: list[BlueprintSection] = Field(default_factory=list)


class FlowGraphPin(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None
    parent_name: Optional[str] = None
    pin_name: Optional[str] = None
    side: Optional[str] = None
    depth: Optional[int] = None


class FlowGraphEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    pins: list[dict] = Field(default_factory=list)
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class FlowGraphStats(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    skipped_edges: int = 0


class FlowGraph(BaseModel):
    nodes: list[FlowGraphNode] = Field(default_factory=list)
    edges: list[FlowGraphEdge] = Field(default_factory=list)
    pin_nodes: list[FlowGraphPin] = Field(default_factory=list)
    pin_edges: list[FlowGraphEdge] = Field(default_factory=list)
    stats: FlowGraphStats = Field(default_factory=FlowGraphStats)

