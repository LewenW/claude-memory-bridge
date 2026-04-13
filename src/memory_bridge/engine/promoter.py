"""Memory promotion: project-scoped → shared namespace."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from memory_bridge.engine.namespace_manager import NamespaceManager
from memory_bridge.models import Memory
from memory_bridge.store.base import MemoryStore


class Promoter:
    __slots__ = ("_store", "_ns")

    def __init__(self, store: MemoryStore, ns_manager: NamespaceManager) -> None:
        self._store = store
        self._ns = ns_manager

    def promote(
        self,
        content: str,
        target_namespace: str,
        *,
        source_project: str | None = None,
        title: str | None = None,
        description: str | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        remove_source: bool = False,
        source_memory_id: str | None = None,
    ) -> dict:
        if not self._ns.exists(target_namespace):
            self._ns.create(target_namespace, description="Auto-created for promotion")

        source_mem: Optional[Memory] = None
        if source_memory_id:
            source_mem = self._store.get_memory(source_memory_id)
            if source_mem:
                content = content or source_mem.content
                title = title or source_mem.title
                description = description or source_mem.description
                memory_type = memory_type or source_mem.memory_type
                tags = tags or source_mem.tags
                source_project = source_project or source_mem.source_project

        now = datetime.now(timezone.utc)
        new_mem = Memory(
            id="",
            title=title or "promoted-memory",
            content=content,
            file_path="",
            namespace=target_namespace,
            tags=tags or [],
            memory_type=memory_type,
            description=description,
            created_at=now,
            updated_at=now,
        )

        written = self._store.write_memory(new_mem)

        removed = False
        if remove_source and source_mem:
            removed = self._store.delete_memory(source_mem.id)

        return {
            "promoted_memory_id": written.id,
            "namespace": target_namespace,
            "file_path": written.file_path,
            "source_removed": removed,
            "source_project": source_project,
        }
