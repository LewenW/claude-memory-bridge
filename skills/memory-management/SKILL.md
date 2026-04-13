# Memory Bridge — Cross-Project Memory Sharing

## When to use
- User mentions something they've "already told Claude" in another project
- User says "same as in project X" or "like we do in the other project"
- User sets up conventions that clearly apply across multiple projects
- Session start: check if current project subscribes to any shared namespaces

## How it works
This plugin provides shared memory across Claude projects via **namespaces**.
Think of namespaces like shared folders that multiple projects can subscribe to.

Three-layer model:
- **Global** (`~/.claude/CLAUDE.md`) — loaded everywhere (Claude native)
- **Namespace** (`~/.claude/shared-memory/<ns>/`) — opt-in shared layer (memory-bridge)
- **Project** (`~/.claude/projects/<project>/memory/`) — project-only (Claude native)

## At session start
1. Use `manage_namespaces(action="list")` to check available namespaces
2. Use `search_memories(query="...", scope="shared")` to find relevant shared knowledge
3. If no namespaces exist yet, mention memory-bridge is available

## When user teaches something generalizable
If the user provides feedback or corrections applicable beyond this project
(coding style, tool preferences, team conventions), suggest:
"This seems useful across projects. Want me to save it to a shared
namespace so your other projects can use it too?"

Then use `promote_memory` to save it.

## Available tools
- `search_memories` — Search across all projects and shared namespaces
- `promote_memory` — Move a project memory to a shared namespace
- `list_shared_memories` — View what's in shared namespaces
- `sync_memory` — Copy a memory to specific projects
- `get_memory_health` — Check for duplicates, stale memories, stats
- `manage_namespaces` — Create/delete namespaces, subscribe/unsubscribe projects

## Token efficiency
- Always pass `limit` to search to avoid flooding context
- Prefer `list_shared_memories` over broad searches for browsing
- Use `get_memory_health` sparingly — it scans everything
