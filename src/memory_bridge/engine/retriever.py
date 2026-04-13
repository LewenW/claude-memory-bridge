"""Cross-project memory retrieval with project-name resolution."""

from __future__ import annotations

from memory_bridge.models import SearchResult
from memory_bridge.store.base import MemoryStore


class Retriever:
    __slots__ = ("_store",)

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def _project_id_to_name(self) -> dict[str, str]:
        return {p.id: p.name for p in self._store.scan_projects()}

    def search(
        self,
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        if project:
            for p in self._store.scan_projects():
                if p.name == project or p.id == project:
                    project = p.id
                    break

        return self._store.search(query, scope=scope, project=project, limit=limit)

    def format_results(self, results: list[SearchResult]) -> str:
        if not results:
            return "No memories found."

        id_to_name = self._project_id_to_name()

        lines: list[str] = []
        for i, r in enumerate(results, 1):
            m = r.memory
            if m.namespace:
                loc = f"namespace:{m.namespace}"
            else:
                display_name = id_to_name.get(m.source_project or "", m.source_project or "unknown")
                loc = f"project:{display_name}"
            lines.append(
                f"{i}. **{m.title}** ({loc}, score={r.score:.2f})\n"
                f"   {r.match_context}\n"
                f"   id=`{m.id}`"
            )
        return "\n".join(lines)
