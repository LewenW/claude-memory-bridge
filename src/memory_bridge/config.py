"""Paths and constants."""

from __future__ import annotations

import os
from pathlib import Path

_home = os.environ.get("CLAUDE_HOME")
CLAUDE_HOME: Path = Path(_home) if _home else Path.home() / ".claude"
PROJECTS_DIR: Path = CLAUDE_HOME / "projects"

_shared = os.environ.get("MEMORY_BRIDGE_HOME")
SHARED_DIR: Path = Path(_shared) if _shared else CLAUDE_HOME / "shared-memory"
REGISTRY_FILE: Path = SHARED_DIR / "registry.json"

DEFAULT_SEARCH_LIMIT = 10
PROMOTION_THRESHOLD = 2
MEMORY_INDEX_FILENAME = "MEMORY.md"
