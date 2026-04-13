# memory-bridge

Cross-project memory sharing for Claude Code and Cowork. Stop teaching Claude the same thing twice.

Claude's memory is project-isolated. Teach it "use pnpm" in project A, repeat yourself in project B. memory-bridge adds a shared layer — **namespaces** — between global and project scope. Solves [#36561](https://github.com/anthropics/claude-code/issues/36561) and [#39195](https://github.com/anthropics/claude-code/issues/39195).

```
Global      ~/.claude/CLAUDE.md                      (Claude native)
Namespace   ~/.claude/shared-memory/<ns>/*.md         (memory-bridge)
Project     ~/.claude/projects/<proj>/memory/*.md     (Claude native)
```

## Install

### Claude Code (one command)

```bash
claude mcp add memory-bridge -- uvx claude-memory-bridge
```

Done. No clone, no config files. Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

### Cowork Desktop

Add to your config file (`Settings` > `Developer` > `Edit Config`):

```json
{
  "mcpServers": {
    "memory-bridge": {
      "command": "uvx",
      "args": ["claude-memory-bridge"]
    }
  }
}
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Then restart Cowork.

### Manual install (advanced)

```bash
git clone https://github.com/LewenW/claude-memory-bridge.git
cd claude-memory-bridge
pip install -e .
python scripts/install.py
```

## Tools

| Tool | What it does |
|------|-------------|
| `search_memories` | Search across all projects and shared namespaces |
| `promote_memory` | Move a memory from project to shared namespace |
| `sync_memory` | Copy a memory to specific projects |
| `list_shared_memories` | Browse namespace contents |
| `manage_namespaces` | Create, delete, subscribe, unsubscribe |
| `get_memory_health` | Find duplicates, stale entries, broken indexes |

## Quick start

In a Claude Code or Cowork session:

```
# Create a namespace
"Create a shared namespace called 'frontend' for React conventions"

# Share knowledge
"Promote 'Use pnpm, not npm' to the frontend namespace"

# Subscribe a project
"Subscribe my dashboard project to the frontend namespace"

# Search across everything
"Search memories for pnpm"
```

## Client compatibility

| Client | Auto | Manual |
|--------|------|--------|
| Claude Code (CLI) | Yes | Yes |
| Cowork — Code mode | Yes | Yes |
| Cowork — Cowork mode | :( | Yes — mention "memory-bridge" or tool name |

Cowork mode loads the MCP tools but doesn't inject server `instructions`, so Claude won't use them unprompted. Workaround: say "use search_memories" or mention "memory-bridge". This will work automatically once Cowork supports MCP instructions.

## How it works

- Reads/writes Claude's native `~/.claude/projects/*/memory/*.md` directly — no database
- Shared memories in `~/.claude/shared-memory/<namespace>/`
- `registry.json` tracks namespace subscriptions
- Word-boundary TF-IDF search scoring
- Trigram Jaccard similarity for duplicate detection (threshold 0.45)

## Uninstall

```bash
claude mcp remove memory-bridge    # Claude Code
```

Or remove the `memory-bridge` entry from your Cowork config file.

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
