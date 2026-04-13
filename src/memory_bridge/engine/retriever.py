"""Cross-project memory retrieval with project-name resolution."""

from __future__ import annotations

from memory_bridge.engine.namespace_manager import NamespaceManager
from memory_bridge.models import SearchResult
from memory_bridge.store.base import MemoryStore


class Retriever:
    __slots__ = ("_store", "_ns")

    def __init__(self, store: MemoryStore, ns_manager: NamespaceManager) -> None:
        self._store = store
        self._ns = ns_manager

    def search(
        self,
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 10,
    ) -> tuple[list[SearchResult], list]:
        # Resolve project name once; also cache project list for format_results
        projects = self._store.scan_projects()
        if project:
            for p in projects:
                if p.name == project or p.id == project:
                    project = p.id
                    break

        registered = {ns.name for ns in self._ns.list_all()}
        return self._store.search(
            query, scope=scope, project=project, limit=limit,
            registered_namespaces=registered,
        ), projects

    def search_and_format(
        self,
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 10,
    ) -> str:
        results, projects = self.search(query, scope=scope, project=project, limit=limit)
        return self._format(results, projects)

    def _format(self, results: list[SearchResult], projects: list) -> str:
        if not results:
            return "No memories found."

        id_to_name = {p.id: p.name for p in projects}

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
