from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

SECTION_ORDER = ["FIXED", "SCROLLS", "HEADER", "FOOTER", "MAIN"]


class BlueprintMeta(BaseModel):
    file_key: str = "unknown"
    node_id: Optional[str] = None
    mode: Optional[str] = None
    folder: Optional[str] = None
    name: Optional[str] = None
    timestamp: Optional[str] = None


class BlueprintPin(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    depth: Optional[int] = None
    path: Optional[str] = None
    bbox: Optional[list[float]] = None
    section: Optional[str] = None
    side: Optional[str] = None


class BlueprintSection(BaseModel):
    title: str
    pins: list[BlueprintPin] = Field(default_factory=list)


class BlueprintNode(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    bbox: Optional[list[float]] = None
    sections: list[BlueprintSection] = Field(default_factory=list)
    source_ref: Optional[dict[str, Any]] = None


class BlueprintEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: Optional[str] = None
    source: Optional[str] = None

    model_config = {"populate_by_name": True}


class BlueprintSnapshot(BaseModel):
    meta: BlueprintMeta
    nodes: list[BlueprintNode] = Field(default_factory=list)
    edges: list[BlueprintEdge] = Field(default_factory=list)


def sort_sections(sections: list[BlueprintSection]) -> list[BlueprintSection]:
    by_title = {section.title: section for section in sections}
    ordered: list[BlueprintSection] = []
    for title in SECTION_ORDER:
        if title in by_title:
            ordered.append(by_title.pop(title))
    ordered.extend(by_title.values())
    return ordered

