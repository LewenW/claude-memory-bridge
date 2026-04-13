"""Memory health: near-duplicate detection, staleness, index integrity.

Duplicates found via trigram Jaccard similarity — catches paraphrases
without embeddings. Phase C will add cosine similarity on vectors."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory_bridge.config import SHARED_DIR
from memory_bridge.engine.namespace_manager import NamespaceManager
from memory_bridge.models import HealthReport, Memory
from memory_bridge.store.base import MemoryStore

_STALE_DAYS = 90
_SIMILARITY_THRESHOLD = 0.45

# ── Trigram Jaccard ────────────────────────────────────────────────────────


def _trigrams(text: str) -> set[str]:
    normalized = re.sub(r"[^\w]", " ", text.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) < 3:
        return {normalized} if normalized else set()
    return {normalized[i : i + 3] for i in range(len(normalized) - 2)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── HealthAnalyzer ─────────────────────────────────────────────────────────


class HealthAnalyzer:
    __slots__ = ("_store", "_ns")

    def __init__(self, store: MemoryStore, ns_manager: NamespaceManager) -> None:
        self._store = store
        self._ns = ns_manager

    def analyze(self) -> HealthReport:
        projects = self._store.scan_projects()
        namespaces = self._ns.list_all()

        all_memories: list[Memory] = []
        for p in projects:
            all_memories.extend(self._store.read_project_memories(p.id))
        shared_count = 0
        for ns in namespaces:
            mems = self._store.read_shared_memories(ns.name)
            shared_count += len(mems)
            all_memories.extend(mems)

        duplicates = self._find_duplicates(all_memories)
        stale = self._find_stale(all_memories)
        index_issues = self._audit_indexes(projects, namespaces)
        suggestions = self._build_suggestions(
            projects, namespaces, duplicates, stale, index_issues
        )

        return HealthReport(
            total_projects=len(projects),
            total_memories=len(all_memories),
            total_shared=shared_count,
            namespaces=namespaces,
            duplicates=duplicates,
            stale_memories=stale,
            index_issues=index_issues,
            suggestions=suggestions,
        )

    def _find_duplicates(self, memories: list[Memory]) -> list[dict]:
        if len(memories) < 2:
            return []

        mem_trigrams: list[tuple[Memory, set[str]]] = []
        for m in memories:
            tg = _trigrams(m.content)
            if len(tg) >= 5:
                mem_trigrams.append((m, tg))

        # O(n²) — acceptable while memory count is low (hundreds, not thousands)
        seen: set[str] = set()
        groups: dict[str, list[Memory]] = defaultdict(list)

        for i, (m1, tg1) in enumerate(mem_trigrams):
            for j in range(i + 1, len(mem_trigrams)):
                m2, tg2 = mem_trigrams[j]
                if _jaccard(tg1, tg2) < _SIMILARITY_THRESHOLD:
                    continue
                group_key = m1.id
                if m1.id in seen:
                    for k, members in groups.items():
                        if any(m.id == m1.id for m in members):
                            group_key = k
                            break
                if group_key not in groups:
                    groups[group_key] = [m1]
                    seen.add(m1.id)
                if m2.id not in seen:
                    groups[group_key].append(m2)
                    seen.add(m2.id)

        return [
            {
                "content_preview": group[0].content[:100],
                "similarity": round(
                    max(
                        _jaccard(_trigrams(group[0].content), _trigrams(m.content))
                        for m in group[1:]
                    ),
                    2,
                ),
                "locations": [
                    {"id": m.id, "title": m.title, "source": m.namespace or m.source_project}
                    for m in group
                ],
            }
            for group in groups.values()
            if len(group) >= 2
        ]

    def _find_stale(self, memories: list[Memory]) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_STALE_DAYS)
        return [
            {
                "id": m.id,
                "title": m.title,
                "source": m.namespace or m.source_project,
                "last_updated": m.updated_at.isoformat(),
            }
            for m in memories
            if m.updated_at < cutoff
        ]

    def _audit_indexes(self, projects: list, namespaces: list) -> list[dict]:
        from memory_bridge.store.filesystem import FileSystemStore

        if not isinstance(self._store, FileSystemStore):
            return []

        issues: list[dict] = []

        for p in projects:
            audit = self._store.audit_index(Path(p.memory_dir))
            if audit["orphans"] or audit["dangling"]:
                issues.append({
                    "location": f"project:{p.name}",
                    "mem_dir": str(p.memory_dir),
                    "orphans": sorted(audit["orphans"]),
                    "dangling": sorted(audit["dangling"]),
                })

        for ns in namespaces:
            audit = self._store.audit_index(SHARED_DIR / ns.name)
            if audit["orphans"] or audit["dangling"]:
                issues.append({
                    "location": f"namespace:{ns.name}",
                    "mem_dir": str(SHARED_DIR / ns.name),
                    "orphans": sorted(audit["orphans"]),
                    "dangling": sorted(audit["dangling"]),
                })

        return issues

    def _build_suggestions(
        self,
        projects: list,
        namespaces: list,
        duplicates: list,
        stale: list,
        index_issues: list,
    ) -> list[str]:
        tips: list[str] = []
        if duplicates:
            tips.append(
                f"Found {len(duplicates)} near-duplicate group(s). "
                f"Consider promoting to a shared namespace."
            )
        if stale:
            tips.append(
                f"{len(stale)} memories unchanged for {_STALE_DAYS}+ days. "
                f"Review and remove outdated ones."
            )
        if index_issues:
            orphan_count = sum(len(i["orphans"]) for i in index_issues)
            dangling_count = sum(len(i["dangling"]) for i in index_issues)
            parts = []
            if orphan_count:
                parts.append(f"{orphan_count} file(s) missing from MEMORY.md")
            if dangling_count:
                parts.append(f"{dangling_count} index entries point to missing files")
            tips.append(
                f"Index issues: {'; '.join(parts)}. "
                f"Use get_memory_health with fix_indexes=true to repair."
            )
        if projects and not namespaces:
            tips.append(
                "No shared namespaces yet. Create one with manage_namespaces."
            )
        if len(projects) > 3 and not namespaces:
            tips.append(
                f"You have {len(projects)} projects. Shared namespaces can "
                f"reduce repetition."
            )
        if not tips:
            tips.append("Memory health looks good.")
        return tips
