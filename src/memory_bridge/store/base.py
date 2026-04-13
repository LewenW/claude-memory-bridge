"""Abstract storage interface. Phase A implements FileSystemStore; B/C swap in
SQLite and vector backends without touching engine or server layers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from memory_bridge.models import Memory, Project, SearchResult


class MemoryStore(ABC):
    """Storage contract.  Every method is synchronous — Phase A does pure I/O
    and even Phase C embeddings are cheap enough to block on."""

    # ── Discovery ──────────────────────────────────────────────────────

    @abstractmethod
    def scan_projects(self) -> list[Project]:
        """Return every project that has a memory/ directory."""

    # ── Read ───────────────────────────────────────────────────────────

    @abstractmethod
    def read_project_memories(self, project_id: str) -> list[Memory]:
        """All memories in a single project."""

    @abstractmethod
    def read_shared_memories(self, namespace: str) -> list[Memory]:
        """All memories in a shared namespace."""

    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Fetch one memory by ID, or None."""

    # ── Write ──────────────────────────────────────────────────────────

    @abstractmethod
    def write_memory(self, memory: Memory) -> Memory:
        """Persist a Memory (project or shared). Returns the written Memory
        with its final file_path populated."""

    @abstractmethod
    def delete_memory(self, memory_id: str) -> bool:
        """Remove a memory file. Returns True if it existed."""

    # ── Search ─────────────────────────────────────────────────────────

    @abstractmethod
    def search(
        self,
        query: str,
        scope: str = "all",
        project: Optional[str] = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Keyword search (Phase A) or semantic search (Phase C)."""
