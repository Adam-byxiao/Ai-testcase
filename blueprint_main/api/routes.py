from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from blueprint_main.adapters.snapshot_repository import SnapshotRepository
from blueprint_main.domain.blueprint import BlueprintSnapshot
from blueprint_main.services.flow_graph_builder import FlowGraphBuilder
from blueprint_main.services.structured_flow_tree_builder import StructuredFlowTreeBuilder
from blueprint_main.services.flow_tree_builder import FlowTreeBuilder

router = APIRouter(prefix="/api/blueprint-main", tags=["Blueprint Main"])


class SaveSnapshotResponse(BaseModel):
    ok: bool = True
    path: str
    snapshot: BlueprintSnapshot


class GraphBuildRequest(BaseModel):
    snapshot: Optional[BlueprintSnapshot] = None
    name: Optional[str] = None
    folder: Optional[str] = None
    scope: str = "pin"
    save_output: bool = False


class TreeBuildRequest(BaseModel):
    snapshot: Optional[BlueprintSnapshot] = None
    name: Optional[str] = None
    folder: Optional[str] = None
    scope: str = "pin"
    cycle_aware: bool = True
    include_structured: bool = True
    save_output: bool = False


class GraphBuildResponse(BaseModel):
    ok: bool = True
    graph: dict
    path: Optional[str] = None


class TreeBuildResponse(BaseModel):
    ok: bool = True
    tree: dict
    structured_tree: Optional[dict] = None
    path: Optional[str] = None


def get_snapshot_repository() -> SnapshotRepository:
    base_dir = os.getenv(
        "BLUEPRINT_MAIN_SNAPSHOT_DIR",
        os.path.join(os.getcwd(), "output", "blueprint_snapshots"),
    )
    legacy_dir = os.getenv(
        "BLUEPRINT_MAIN_LEGACY_SNAPSHOT_DIR",
        os.path.join(os.getcwd(), "blueprint_flow", "output", "blueprint_snapshots"),
    )
    return SnapshotRepository(base_dir=base_dir, read_dirs=[legacy_dir])


def get_flow_output_dir() -> str:
    return os.getenv(
        "BLUEPRINT_MAIN_FLOW_DIR",
        os.path.join(os.getcwd(), "output", "blueprint_flow"),
    )


def _resolve_snapshot(payload_snapshot: Optional[BlueprintSnapshot], name: Optional[str], folder: Optional[str], repository: SnapshotRepository) -> BlueprintSnapshot:
    if payload_snapshot is not None:
        return payload_snapshot
    if name:
        return repository.load(name=name, folder=folder)
    raise HTTPException(status_code=400, detail="Either snapshot or name must be provided")


def _save_json_output(base_dir: str, prefix: str, name: str, payload: dict) -> str:
    os.makedirs(base_dir, exist_ok=True)
    filename = f"{prefix}_{os.path.splitext(name)[0]}.json"
    path = os.path.join(base_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    return path


@router.post("/snapshots", response_model=SaveSnapshotResponse)
def save_snapshot(
    snapshot: BlueprintSnapshot,
    repository: SnapshotRepository = Depends(get_snapshot_repository),
):
    path = repository.save(snapshot)
    return SaveSnapshotResponse(path=path, snapshot=snapshot)


@router.get("/snapshots")
def list_snapshots(
    file_key: Optional[str] = Query(default=None),
    node_id: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    repository: SnapshotRepository = Depends(get_snapshot_repository),
):
    return {
        "items": repository.list(file_key=file_key, node_id=node_id, folder=folder),
    }


@router.get("/snapshots/latest")
def latest_snapshot(
    file_key: Optional[str] = Query(default=None),
    node_id: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    repository: SnapshotRepository = Depends(get_snapshot_repository),
):
    item = repository.latest(file_key=file_key, node_id=node_id, folder=folder)
    if not item:
        raise HTTPException(status_code=404, detail="no snapshots")
    return item


@router.get("/snapshots/folders")
def snapshot_folders(repository: SnapshotRepository = Depends(get_snapshot_repository)):
    return {"folders": repository.list_folders()}


@router.get("/snapshots/{name}")
def get_snapshot(
    name: str,
    folder: Optional[str] = Query(default=None),
    repository: SnapshotRepository = Depends(get_snapshot_repository),
):
    try:
        snapshot = repository.load(name=name, folder=folder)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="snapshot not found") from None
    return snapshot.model_dump(by_alias=True)


@router.post("/graphs/build", response_model=GraphBuildResponse)
def build_graph(
    request: GraphBuildRequest,
    repository: SnapshotRepository = Depends(get_snapshot_repository),
):
    snapshot = _resolve_snapshot(request.snapshot, request.name, request.folder, repository)
    scope = (request.scope or "pin").lower()
    graph = (
        FlowGraphBuilder.build_from_nodes(snapshot)
        if scope == "node"
        else FlowGraphBuilder.build_from_pins(snapshot)
    )
    payload = graph.model_dump(by_alias=True)
    path = None
    if request.save_output:
        output_name = request.name or snapshot.meta.name or "snapshot"
        path = _save_json_output(get_flow_output_dir(), "flow_graph", output_name, payload)
    return GraphBuildResponse(graph=payload, path=path)


@router.post("/trees/build", response_model=TreeBuildResponse)
def build_tree(
    request: TreeBuildRequest,
    repository: SnapshotRepository = Depends(get_snapshot_repository),
):
    snapshot = _resolve_snapshot(request.snapshot, request.name, request.folder, repository)
    scope = (request.scope or "pin").lower()
    graph = (
        FlowGraphBuilder.build_from_nodes(snapshot)
        if scope == "node"
        else FlowGraphBuilder.build_from_pins(snapshot)
    )
    tree = (
        FlowTreeBuilder.build_with_cycles(graph)
        if request.cycle_aware
        else FlowTreeBuilder.build_simple(graph)
    )
    payload = tree.model_dump(by_alias=True)
    structured_payload = None
    if request.include_structured:
        structured_tree = StructuredFlowTreeBuilder.build(graph)
        structured_payload = structured_tree.model_dump(by_alias=True)
    path = None
    if request.save_output:
        output_name = request.name or snapshot.meta.name or "snapshot"
        path = _save_json_output(get_flow_output_dir(), "flow_tree", output_name, payload)
        if structured_payload is not None:
            _save_json_output(get_flow_output_dir(), "structured_flow_tree", output_name, structured_payload)
    return TreeBuildResponse(tree=payload, structured_tree=structured_payload, path=path)
