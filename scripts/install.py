"""Install memory-bridge MCP server into all detected Claude clients.

Usage:
    python scripts/install.py           # install
    python scripts/install.py --check   # show what would be configured
    python scripts/install.py --remove  # remove from all clients
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parent.parent / "src"


def _find_python() -> str:
    """Find a stable Python path — avoid venv-specific executables."""
    exe = sys.executable
    # If inside a venv, prefer the base prefix Python
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        candidates = [
            shutil.which("python3"),
            shutil.which("python"),
        ]
        for c in candidates:
            if c and "venv" not in c and ".venv" not in c:
                return c
    return exe


MCP_ENTRY = {
    "command": _find_python(),
    "args": ["-m", "memory_bridge.server"],
    "env": {"PYTHONPATH": str(PACKAGE_SRC)},
}


def _find_clients() -> dict[str, Path]:
    """Detect installed Claude clients and their config file paths."""
    clients: dict[str, Path] = {}

    # Claude Code CLI
    claude_home = Path.home() / ".claude"
    if claude_home.is_dir():
        clients["Claude Code CLI"] = claude_home / "settings.json"

    # Cowork desktop (macOS)
    if platform.system() == "Darwin":
        cowork = Path.home() / "Library" / "Application Support" / "Claude"
        if cowork.is_dir():
            clients["Cowork (macOS)"] = cowork / "claude_desktop_config.json"

    # Cowork desktop (Windows)
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            cowork_win = Path(appdata) / "Claude"
            if cowork_win.is_dir():
                clients["Cowork (Windows)"] = cowork_win / "claude_desktop_config.json"

    return clients


def _read_config(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def install():
    clients = _find_clients()
    if not clients:
        print("No Claude clients found.")
        return

    for name, config_path in clients.items():
        config = _read_config(config_path)
        servers = config.setdefault("mcpServers", {})

        if "memory-bridge" in servers:
            print(f"  {name}: already configured, updating")
        else:
            print(f"  {name}: adding memory-bridge")

        servers["memory-bridge"] = MCP_ENTRY
        _write_config(config_path, config)

    print(f"\nDone. Restart your Claude client(s) to connect.")
    print(f"MCP server: {sys.executable} -m memory_bridge.server")
    print(f"Source: {PACKAGE_SRC}")


def check():
    clients = _find_clients()
    if not clients:
        print("No Claude clients found.")
        return

    for name, config_path in clients.items():
        config = _read_config(config_path)
        has_it = "memory-bridge" in config.get("mcpServers", {})
        status = "installed" if has_it else "not installed"
        print(f"  {name}: {config_path}")
        print(f"    memory-bridge: {status}")


def remove():
    clients = _find_clients()
    removed = 0
    for name, config_path in clients.items():
        config = _read_config(config_path)
        servers = config.get("mcpServers", {})
        if "memory-bridge" in servers:
            del servers["memory-bridge"]
            if not servers:
                del config["mcpServers"]
            _write_config(config_path, config)
            print(f"  {name}: removed")
            removed += 1
        else:
            print(f"  {name}: not installed, skipping")

    if removed:
        print(f"\nRemoved from {removed} client(s). Restart to take effect.")


if __name__ == "__main__":
    if "--check" in sys.argv:
        print("Detected Claude clients:\n")
        check()
    elif "--remove" in sys.argv:
        print("Removing memory-bridge:\n")
        remove()
    else:
        print("Installing memory-bridge:\n")
        install()
