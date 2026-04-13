# memory-bridge

Cross-project memory sharing for Claude Code and Cowork. Stop teaching Claude the same thing twice.

```bash
pip install mcp
python scripts/install.py    # auto-detects Cowork desktop + Claude Code CLI
```

## What it solves

Claude's memory is project-isolated. Teach it "use pnpm" in project A, repeat yourself in project B. memory-bridge adds a shared layer — **namespaces** — between global and project scope.

```
Global      ~/.claude/CLAUDE.md                      (Claude native)
Namespace   ~/.claude/shared-memory/<ns>/*.md         (memory-bridge)
Project     ~/.claude/projects/<proj>/memory/*.md     (Claude native)
```

Solves [#36561](https://github.com/anthropics/claude-code/issues/36561) and [#39195](https://github.com/anthropics/claude-code/issues/39195).

## Tools

| Tool | What it does |
|------|-------------|
| `search_memories` | Search across all projects and shared namespaces |
| `promote_memory` | Move a memory from project → shared namespace |
| `sync_memory` | Copy a memory to specific projects |
| `list_shared_memories` | Browse namespace contents |
| `manage_namespaces` | Create, delete, subscribe, unsubscribe |
| `get_memory_health` | Find duplicates, stale entries, broken indexes |

## Quick start

```
# Create a shared namespace
> manage_namespaces action=create namespace=frontend description="React conventions"

# Share a memory
> promote_memory content="Use pnpm, not npm" target_namespace=frontend

# Subscribe a project
> manage_namespaces action=subscribe namespace=frontend project=dashboard

# Search across everything
> search_memories query="pnpm"
```

## Client compatibility

| Client | Auto | Manual |
|--------|------|--------|
| Claude Code (CLI) | ✅ | ✅ |
| Cowork — Code mode | ✅ | ✅ |
| Cowork — Cowork mode | ❌ | ✅ mention "memory-bridge" or tool name |

Cowork mode loads the MCP tools but doesn't inject server `instructions`, so Claude won't use them unprompted. Workaround: say "use search_memories" or mention "memory-bridge". This will work automatically once Cowork supports MCP instructions.

## How it works

- Reads/writes Claude's native `~/.claude/projects/*/memory/*.md` directly — no database
- Shared memories in `~/.claude/shared-memory/<namespace>/`
- `registry.json` tracks namespace subscriptions
- Word-boundary TF-IDF search scoring
- Trigram Jaccard similarity for duplicate detection (threshold 0.45)

## Install / uninstall

```bash
python scripts/install.py            # install to all detected clients
python scripts/install.py --check    # show current config
python scripts/install.py --remove   # uninstall from all clients
```

## Project structure

```
src/memory_bridge/
├── server.py              MCP server, 6 tools
├── config.py              Paths + constants
├── models.py              Dataclasses
├── store/
│   ├── base.py            MemoryStore interface
│   └── filesystem.py      File I/O + keyword search
└── engine/
    ├── retriever.py       Cross-project search
    ├── promoter.py        Project → namespace promotion
    ├── namespace_manager.py   Namespace CRUD
    └── health_analyzer.py     Dedup + staleness + index audit
```

## License

MIT
