from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FlowTreeEdgePin(BaseModel):
    from_pin: Optional[str] = None
    to_pin: Optional[str] = None
    name: Optional[str] = None


class FlowTreeNode(BaseModel):
    id: str
    children: list["FlowTreeNode"] = Field(default_factory=list)
    type: Optional[str] = None
    exit: bool = False
    cycle: bool = False
    entry_of: Optional[int] = None
    edge_pins: list[dict] = Field(default_factory=list)


class FlowCycleBlock(BaseModel):
    entry: str
    internal: list[str] = Field(default_factory=list)
    exits: list[dict] = Field(default_factory=list)


class FlowTreeStats(BaseModel):
    root_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    cycle_count: int = 0


class FlowTree(BaseModel):
    roots: list[str] = Field(default_factory=list)
    trees: list[FlowTreeNode] = Field(default_factory=list)
    cycles: dict[str, FlowCycleBlock] = Field(default_factory=dict)
    stats: FlowTreeStats = Field(default_factory=FlowTreeStats)


FlowTreeNode.model_rebuild()

