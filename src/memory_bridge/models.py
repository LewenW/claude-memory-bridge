"""Core data models. Thin dataclasses — no business logic lives here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(slots=True)
class Memory:
    id: str
    title: str
    content: str
    file_path: str
    source_project: Optional[str] = None  # None → shared memory
    namespace: Optional[str] = None       # None → project-scoped
    tags: list[str] = field(default_factory=list)
    memory_type: Optional[str] = None     # user/feedback/project/reference
    description: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class SearchResult:
    memory: Memory
    score: float          # Phase A: keyword hit count; Phase C: cosine sim
    match_context: str    # snippet showing where match occurred


@dataclass(slots=True)
class Project:
    id: str               # dir name, e.g. "-Users-me-projects-webapp"
    name: str             # human-readable, e.g. "webapp"
    memory_dir: str       # absolute path to memory/
    memory_count: int = 0


@dataclass(slots=True)
class NamespaceInfo:
    name: str
    description: str
    subscribers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    memory_count: int = 0
    created_at: str = ""


@dataclass(slots=True)
class HealthReport:
    total_projects: int = 0
    total_memories: int = 0
    total_shared: int = 0
    namespaces: list[NamespaceInfo] = field(default_factory=list)
    duplicates: list[dict] = field(default_factory=list)
    stale_memories: list[dict] = field(default_factory=list)
    index_issues: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
