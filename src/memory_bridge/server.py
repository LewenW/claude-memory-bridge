"""MCP server — 6 tools over stdio. Zero startup cost: no DB, no index build."""

from __future__ import annotations

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from memory_bridge.engine.health_analyzer import HealthAnalyzer
from memory_bridge.engine.namespace_manager import NamespaceManager
from memory_bridge.engine.promoter import Promoter
from memory_bridge.engine.retriever import Retriever
from memory_bridge.store.filesystem import FileSystemStore

# ── Bootstrap ──────────────────────────────────────────────────────────────

_INSTRUCTIONS = """\
You have cross-session, cross-project memory via memory-bridge.

When the user asks if you remember something from another session or project, \
use search_memories to look it up — don't say you lack memory. When the user \
teaches you something that applies to multiple projects (coding style, tool \
preferences, team conventions), offer to save it to a shared namespace with \
promote_memory.

Three memory layers:
- Global: ~/.claude/CLAUDE.md (always loaded)
- Namespace: ~/.claude/shared-memory/<ns>/ (opt-in, shared across projects)
- Project: ~/.claude/projects/<proj>/memory/ (project-scoped)

Use search_memories at session start to check for relevant shared knowledge. \
Use manage_namespaces to create or list namespaces. Use get_memory_health to \
find duplicates or stale entries."""

mcp = FastMCP("memory-bridge", instructions=_INSTRUCTIONS)

_store = FileSystemStore()
_ns = NamespaceManager()
_retriever = Retriever(_store, _ns)
_promoter = Promoter(_store, _ns)
_health = HealthAnalyzer(_store, _ns)

# ── Tool 1: search_memories ────────────────────────────────────────────────


@mcp.tool()
def search_memories(
    query: str,
    scope: str = "all",
    project: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search memories saved in previous sessions, across all projects and shared namespaces.
    Use this when the user asks if you remember something, references past conversations,
    or when you want to check for existing knowledge before a task.

    Args:
        query: Keywords to search for.
        scope: "all" | "shared" | "project" | a namespace name.
        project: Limit to a specific project (name or id).
        limit: Max results (default 10).
    """
    return _retriever.search_and_format(query, scope=scope, project=project, limit=limit)


# ── Tool 2: promote_memory ─────────────────────────────────────────────────


@mcp.tool()
def promote_memory(
    content: str,
    target_namespace: str,
    source_project: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    memory_type: Optional[str] = None,
    tags: Optional[str] = None,
    source_memory_id: Optional[str] = None,
    remove_source: bool = False,
) -> str:
    """Save a memory to a shared namespace so it persists across sessions
    and multiple projects can access it. Use when the user teaches you something
    that applies beyond the current project.

    Args:
        content: The memory content to promote.
        target_namespace: Namespace to promote into (created if missing).
        source_project: Original project (name or id).
        title: Title for the shared memory.
        description: One-line description.
        memory_type: user / feedback / project / reference.
        tags: Comma-separated tags.
        source_memory_id: If promoting an existing memory, its id.
        remove_source: Remove the original after promotion.
    """
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    result = _promoter.promote(
        content=content,
        target_namespace=target_namespace,
        source_project=source_project,
        title=title,
        description=description,
        memory_type=memory_type,
        tags=tag_list or None,
        remove_source=remove_source,
        source_memory_id=source_memory_id,
    )
    return json.dumps(result, indent=2)


# ── Tool 3: list_shared_memories ───────────────────────────────────────────


@mcp.tool()
def list_shared_memories(namespace: Optional[str] = None) -> str:
    """List memories saved across sessions in shared namespaces.
    If namespace is omitted, shows all namespaces and their summaries.

    Args:
        namespace: A specific namespace to list memories from.
    """
    if namespace:
        if not _ns.exists(namespace):
            return f"Namespace '{namespace}' does not exist."
        memories = _store.read_shared_memories(namespace)
        if not memories:
            return f"Namespace '{namespace}' is empty."
        lines = [f"## Namespace: {namespace} ({len(memories)} memories)\n"]
        for m in memories:
            lines.append(f"- **{m.title}** (id=`{m.id}`)")
            if m.description:
                lines.append(f"  {m.description}")
        return "\n".join(lines)

    namespaces = _ns.list_all()
    if not namespaces:
        return "No shared namespaces yet. Use manage_namespaces to create one."

    lines = ["## Shared Memory Namespaces\n"]
    for ns in namespaces:
        subs = f"{len(ns.subscribers)} subscribers" if ns.subscribers else "no subscribers"
        lines.append(f"- **{ns.name}**: {ns.description} ({ns.memory_count} memories, {subs})")
    return "\n".join(lines)


# ── Tool 4: sync_memory ───────────────────────────────────────────────────


@mcp.tool()
def sync_memory(
    content: str,
    target_projects: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    memory_type: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """Copy a memory to one or more specific projects so they can use it in future sessions.

    Args:
        content: The memory content.
        target_projects: Comma-separated list of project names or ids.
        title: Memory title.
        description: One-line description.
        memory_type: user / feedback / project / reference.
        tags: Comma-separated tags.
    """
    from memory_bridge.models import Memory
    from datetime import datetime, timezone

    targets = [t.strip() for t in target_projects.split(",") if t.strip()]
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    now = datetime.now(timezone.utc)

    all_projects: dict[str, str] = {}
    for p in _store.scan_projects():
        # Only map name→id if unique; id→id is always safe
        if p.name not in all_projects:
            all_projects[p.name] = p.id
        else:
            all_projects[p.name] = "__ambiguous__"
        all_projects[p.id] = p.id

    results: list[dict] = []
    for target in targets:
        project_id = all_projects.get(target)
        if not project_id or project_id == "__ambiguous__":
            status = "ambiguous_name" if project_id == "__ambiguous__" else "not_found"
            results.append({"project": target, "status": status})
            continue

        try:
            mem = Memory(
                id="",
                title=title or "synced-memory",
                content=content,
                file_path="",
                source_project=project_id,
                tags=tag_list,
                memory_type=memory_type,
                description=description,
                created_at=now,
                updated_at=now,
            )
            written = _store.write_memory(mem)
            entry = {"project": target, "status": "ok", "memory_id": written.id}
            if written.index_full:
                entry["warning"] = "MEMORY.md index full (200 lines). Run get_memory_health with fix_indexes=true."
            results.append(entry)
        except (OSError, ValueError) as e:
            results.append({"project": target, "status": "error", "error": str(e)})

    return json.dumps(results, indent=2)


# ── Tool 5: get_memory_health ──────────────────────────────────────────────


@mcp.tool()
def get_memory_health(fix_indexes: bool = False) -> str:
    """Analyze saved memory health across all projects and sessions. Reports duplicates,
    stale memories, index integrity, and actionable suggestions.

    Args:
        fix_indexes: If true, rebuild all MEMORY.md indexes from actual files on disk.
    """
    if fix_indexes:
        from pathlib import Path
        fixed: list[str] = []
        for p in _store.scan_projects():
            count = _store.rebuild_index(Path(p.memory_dir))
            fixed.append(f"{p.name}: {count} entries")
        registered = {ns.name for ns in _ns.list_all()}
        for ns_dir in _store._namespace_dirs(registered=registered):
            count = _store.rebuild_index(ns_dir)
            fixed.append(f"ns:{ns_dir.name}: {count} entries")
        return "## Indexes Rebuilt\n\n" + "\n".join(f"- {f}" for f in fixed)

    report = _health.analyze()

    lines = [
        "## Memory Health Report\n",
        f"- **Projects**: {report.total_projects}",
        f"- **Total memories**: {report.total_memories}",
        f"- **Shared memories**: {report.total_shared}",
        f"- **Namespaces**: {len(report.namespaces)}",
    ]

    if report.duplicates:
        lines.append(f"\n### Near-Duplicates ({len(report.duplicates)} groups)")
        for d in report.duplicates[:5]:
            locs = ", ".join(f"{l['source']}" for l in d["locations"])
            sim = d.get("similarity", "?")
            lines.append(f"- \"{d['content_preview'][:60]}...\" (similarity={sim}) → {locs}")

    if report.index_issues:
        lines.append(f"\n### Index Issues ({len(report.index_issues)} locations)")
        for iss in report.index_issues:
            loc = iss["location"]
            if iss["orphans"]:
                lines.append(f"- {loc}: {len(iss['orphans'])} file(s) not in index: {', '.join(iss['orphans'][:3])}")
            if iss["dangling"]:
                lines.append(f"- {loc}: {len(iss['dangling'])} index entries point to missing files: {', '.join(iss['dangling'][:3])}")

    if report.stale_memories:
        lines.append(f"\n### Stale ({len(report.stale_memories)} memories)")
        for s in report.stale_memories[:5]:
            lines.append(f"- {s['title']} ({s['source']}, last updated: {s['last_updated'][:10]})")

    lines.append("\n### Suggestions")
    for tip in report.suggestions:
        lines.append(f"- {tip}")

    return "\n".join(lines)


# ── Tool 6: manage_namespaces ──────────────────────────────────────────────


@mcp.tool()
def manage_namespaces(
    action: str,
    namespace: Optional[str] = None,
    description: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[str] = None,
) -> str:
    """Create, delete, subscribe, unsubscribe, or list namespaces.

    Args:
        action: "create" | "delete" | "subscribe" | "unsubscribe" | "list"
        namespace: Namespace name (required for all except "list").
        description: Description (for "create").
        project: Project name or id (for "subscribe" / "unsubscribe").
        tags: Comma-separated tags (for "create").
    """
    if action == "list":
        namespaces = _ns.list_all()
        if not namespaces:
            return "No namespaces. Use action='create' to make one."
        lines = []
        for ns in namespaces:
            subs = ", ".join(ns.subscribers) if ns.subscribers else "none"
            lines.append(
                f"- **{ns.name}**: {ns.description}\n"
                f"  memories={ns.memory_count}, subscribers=[{subs}]"
            )
        return "\n".join(lines)

    if not namespace:
        return "Error: 'namespace' is required for this action."

    if action == "create":
        tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
        try:
            ns = _ns.create(namespace, description=description or "", tags=tag_list)
            return f"Created namespace '{ns.name}'."
        except ValueError as e:
            return f"Error: {e}"

    if action == "delete":
        ok = _ns.delete(namespace)
        return f"Deleted namespace '{namespace}'." if ok else f"Namespace '{namespace}' not found."

    if action in ("subscribe", "unsubscribe"):
        if not project:
            return "Error: 'project' is required for subscribe/unsubscribe."
        matched = False
        for p in _store.scan_projects():
            if p.name == project or p.id == project:
                project = p.id
                matched = True
                break
        if not matched:
            return f"Error: project '{project}' not found. Use the project's directory-based id for exact matching."
        try:
            if action == "subscribe":
                ok = _ns.subscribe(namespace, project)
                return f"Subscribed '{project}' to '{namespace}'." if ok else "Already subscribed."
            else:
                ok = _ns.unsubscribe(namespace, project)
                return f"Unsubscribed '{project}' from '{namespace}'." if ok else "Not subscribed."
        except ValueError as e:
            return f"Error: {e}"

    return f"Unknown action '{action}'. Use: create, delete, subscribe, unsubscribe, list."


# ── Prompts ────────────────────────────────────────────────────────────────


@mcp.prompt()
def check_memory(topic: str = "") -> str:
    """Check what you remember about a topic from previous sessions."""
    if topic:
        return f"Search my saved memories for anything related to: {topic}"
    return (
        "List all shared namespaces and show me what memories are saved "
        "across my projects."
    )


@mcp.prompt()
def save_knowledge(knowledge: str, namespace: str = "general") -> str:
    """Save knowledge to a shared namespace so all projects can use it."""
    return (
        f"Save this to the '{namespace}' shared namespace so all my "
        f"projects can use it in future sessions:\n\n{knowledge}"
    )


# ── Entry point ────────────────────────────────────────────────────────────


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
