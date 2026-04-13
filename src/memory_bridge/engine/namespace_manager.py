"""Namespace CRUD and project subscription. State lives in registry.json."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from memory_bridge.config import MEMORY_INDEX_FILENAME, REGISTRY_FILE, SHARED_DIR
from memory_bridge.models import NamespaceInfo


_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def _validate_namespace(name: str) -> None:
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid namespace name '{name}'. "
            "Use 1-64 alphanumeric chars, hyphens, or underscores."
        )


def _default_registry() -> dict:
    return {"version": "1.0", "namespaces": {}, "settings": {}}


class NamespaceManager:
    def _read(self) -> dict:
        if REGISTRY_FILE.exists():
            try:
                return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return _default_registry()
        return _default_registry()

    def _write(self, data: dict) -> None:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile + rename avoids partial-write corruption
        fd = tempfile.NamedTemporaryFile(
            mode="w", dir=str(SHARED_DIR), suffix=".json",
            delete=False, encoding="utf-8",
        )
        try:
            json.dump(data, fd, indent=2, ensure_ascii=False)
            fd.close()
            os.replace(fd.name, str(REGISTRY_FILE))
        except BaseException:
            fd.close()
            Path(fd.name).unlink(missing_ok=True)
            raise

    # ── Queries ────────────────────────────────────────────────────────

    def exists(self, namespace: str) -> bool:
        return namespace in self._read()["namespaces"]

    def list_all(self) -> list[NamespaceInfo]:
        data = self._read()
        result: list[NamespaceInfo] = []
        for name, ns in data["namespaces"].items():
            ns_dir = SHARED_DIR / name
            try:
                mem_count = sum(
                    1 for f in ns_dir.iterdir() if f.suffix == ".md" and f.name != MEMORY_INDEX_FILENAME
                ) if ns_dir.is_dir() else 0
            except OSError:
                mem_count = 0
            result.append(NamespaceInfo(
                name=name,
                description=ns.get("description", ""),
                subscribers=ns.get("subscribers", []),
                tags=ns.get("tags", []),
                memory_count=mem_count,
                created_at=ns.get("created_at", ""),
            ))
        return result

    def get_subscriptions(self, project_id: str) -> list[str]:
        data = self._read()
        return [
            name
            for name, ns in data["namespaces"].items()
            if project_id in ns.get("subscribers", [])
            or "*" in ns.get("subscribers", [])
        ]

    # ── Mutations ──────────────────────────────────────────────────────

    def create(self, namespace: str, description: str = "", tags: list[str] | None = None) -> NamespaceInfo:
        _validate_namespace(namespace)
        data = self._read()
        if namespace in data["namespaces"]:
            raise ValueError(f"Namespace '{namespace}' already exists")

        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "description": description,
            "created_at": now,
            "subscribers": [],
            "tags": tags or [],
        }
        data["namespaces"][namespace] = entry
        self._write(data)
        (SHARED_DIR / namespace).mkdir(parents=True, exist_ok=True)
        return NamespaceInfo(name=namespace, description=description, tags=tags or [], created_at=now)

    def delete(self, namespace: str) -> bool:
        data = self._read()
        if namespace not in data["namespaces"]:
            return False
        del data["namespaces"][namespace]
        self._write(data)
        # Files kept on disk — user may want them
        return True

    def subscribe(self, namespace: str, project_id: str) -> bool:
        data = self._read()
        if namespace not in data["namespaces"]:
            raise ValueError(f"Namespace '{namespace}' does not exist")
        subs = data["namespaces"][namespace].setdefault("subscribers", [])
        if project_id in subs:
            return False
        subs.append(project_id)
        self._write(data)
        return True

    def unsubscribe(self, namespace: str, project_id: str) -> bool:
        data = self._read()
        if namespace not in data["namespaces"]:
            return False
        subs = data["namespaces"][namespace].get("subscribers", [])
        if project_id not in subs:
            return False
        subs.remove(project_id)
        self._write(data)
        return True
