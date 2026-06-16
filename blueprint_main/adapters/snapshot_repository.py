from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Iterable, Optional

from blueprint_main.domain.blueprint import BlueprintSnapshot


class SnapshotRepository:
    def __init__(self, base_dir: str, read_dirs: Optional[Iterable[str]] = None):
        self.base_dir = base_dir
        self.read_dirs = self._build_read_dirs(read_dirs)

    def save(self, snapshot: BlueprintSnapshot) -> str:
        os.makedirs(self.base_dir, exist_ok=True)
        meta = snapshot.meta
        file_key = re.sub(r"[^a-zA-Z0-9._-]", "_", meta.file_key or "unknown")
        folder_name = re.sub(r"[^a-zA-Z0-9._-]", "_", meta.folder or file_key)[:60]
        report_dir = os.path.join(self.base_dir, folder_name)
        os.makedirs(report_dir, exist_ok=True)

        raw_name = meta.name or "snapshot"
        name_safe = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name)[:60]
        node_id = (meta.node_id or "all").replace(":", "-")
        timestamp = int(datetime.now().timestamp())
        filename = f"{file_key}_{node_id}_{name_safe}_{timestamp}.json"
        path = os.path.join(report_dir, filename)

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(snapshot.model_dump(by_alias=True), handle, ensure_ascii=False, indent=2)
        return path

    def load(self, name: str, folder: Optional[str] = None) -> BlueprintSnapshot:
        path = self._find_snapshot_path(name=name, folder=folder)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return BlueprintSnapshot.model_validate(payload)

    def list(self, file_key: Optional[str] = None, node_id: Optional[str] = None, folder: Optional[str] = None) -> list[dict]:
        target_node = (node_id or "").replace(":", "-")
        items: list[dict] = []
        seen_paths: set[str] = set()
        for candidate_dir in self._iter_candidate_dirs(folder):
            for entry in os.scandir(candidate_dir):
                if not entry.is_file() or not entry.name.endswith(".json"):
                    continue
                normalized_path = os.path.normcase(os.path.abspath(entry.path))
                if normalized_path in seen_paths:
                    continue
                if file_key and file_key not in entry.name:
                    continue
                if target_node and target_node not in entry.name:
                    continue
                seen_paths.add(normalized_path)
                items.append(
                    {
                        "name": entry.name,
                        "folder": os.path.basename(candidate_dir),
                        "path": entry.path,
                        "modified_at": entry.stat().st_mtime,
                    }
                )
        items.sort(key=lambda item: item["modified_at"], reverse=True)
        return items

    def latest(self, file_key: Optional[str] = None, node_id: Optional[str] = None, folder: Optional[str] = None) -> Optional[dict]:
        items = self.list(file_key=file_key, node_id=node_id, folder=folder)
        return items[0] if items else None

    def list_folders(self) -> list[str]:
        folders: set[str] = set()
        for base_dir in self.read_dirs:
            if not os.path.exists(base_dir):
                continue
            folders.update(entry.name for entry in os.scandir(base_dir) if entry.is_dir())
        if self._has_root_json_files():
            folders.add("default")
        return sorted(folders)

    def _build_read_dirs(self, read_dirs: Optional[Iterable[str]]) -> list[str]:
        candidates = [self.base_dir]
        if read_dirs:
            candidates.extend(read_dirs)

        normalized: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            normalized_candidate = os.path.normcase(os.path.abspath(candidate))
            if normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            normalized.append(os.path.abspath(candidate))
        return normalized

    def _find_snapshot_path(self, name: str, folder: Optional[str]) -> str:
        for report_dir in self._iter_report_dirs(folder):
            path = os.path.join(report_dir, name)
            if os.path.exists(path):
                return path
        fallback_dir = self._resolve_dir(self.base_dir, folder)
        return os.path.join(fallback_dir, name)

    def _iter_candidate_dirs(self, folder: Optional[str]) -> list[str]:
        candidate_dirs: list[str] = []
        seen: set[str] = set()
        for base_dir in self.read_dirs:
            if folder is None:
                if not os.path.exists(base_dir):
                    continue
                child_dirs = [entry.path for entry in os.scandir(base_dir) if entry.is_dir()]
                if not child_dirs:
                    child_dirs = [base_dir]
            else:
                child_dirs = [self._resolve_dir(base_dir, folder)]

            for child_dir in child_dirs:
                normalized = os.path.normcase(os.path.abspath(child_dir))
                if normalized in seen or not os.path.exists(child_dir):
                    continue
                seen.add(normalized)
                candidate_dirs.append(child_dir)
        return candidate_dirs

    def _iter_report_dirs(self, folder: Optional[str]) -> list[str]:
        report_dirs: list[str] = []
        seen: set[str] = set()
        for base_dir in self.read_dirs:
            report_dir = self._resolve_dir(base_dir, folder)
            normalized = os.path.normcase(os.path.abspath(report_dir))
            if normalized in seen:
                continue
            seen.add(normalized)
            report_dirs.append(report_dir)
        return report_dirs

    def _has_root_json_files(self) -> bool:
        for base_dir in self.read_dirs:
            if not os.path.exists(base_dir):
                continue
            for entry in os.scandir(base_dir):
                if entry.is_file() and entry.name.endswith(".json"):
                    return True
        return False

    def _resolve_dir(self, base_dir: str, folder: Optional[str]) -> str:
        if not folder:
            return base_dir
        folder_name = re.sub(r"[^a-zA-Z0-9._-]", "_", folder)[:60]
        return os.path.join(base_dir, folder_name)
