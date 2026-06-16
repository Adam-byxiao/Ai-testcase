from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StructuredFlowBranch(BaseModel):
    label: Optional[str] = None
    child: "StructuredFlowNode"


class StructuredFlowNode(BaseModel):
    type: str
    id: Optional[str] = None
    title: Optional[str] = None
    children: list["StructuredFlowNode"] = Field(default_factory=list)
    branches: list[StructuredFlowBranch] = Field(default_factory=list)
    body: Optional["StructuredFlowNode"] = None
    entry: Optional[str] = None
    members: list[str] = Field(default_factory=list)
    back_edges: list[dict] = Field(default_factory=list)
    exit_edges: list[dict] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class StructuredFlowTree(BaseModel):
    root: StructuredFlowNode
    roots: list[str] = Field(default_factory=list)
    cycle_nodes: dict[str, list[str]] = Field(default_factory=dict)


StructuredFlowNode.model_rebuild()
StructuredFlowBranch.model_rebuild()

