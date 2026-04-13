"""Phase A storage — reads/writes Claude-native Markdown memory files.

Design decisions:
* Markdown files are source of truth — no shadow DB, no migration.
* Memory ID = SHA-256(path relative to CLAUDE_HOME)[:12]. Stable, deterministic.
* Frontmatter parsed with a zero-dep regex parser (no PyYAML).
* Search scores with TF-IDF-lite: word-boundary hits / sqrt(doc_length).
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memory_bridge.config import (
    CLAUDE_HOME,
    MEMORY_INDEX_FILENAME,
    PROJECTS_DIR,
    SHARED_DIR,
)
from memory_bridge.models import Memory, Project, SearchResult
from memory_bridge.store.base import MemoryStore

# ── Helpers ────────────────────────────────────────────────────────────────


def _memory_id(path: str | Path) -> str:
    rel = os.path.relpath(str(path), str(CLAUDE_HOME))
    # Normalize to forward slashes so IDs are consistent across platforms
    rel = rel.replace("\\", "/")
    return hashlib.sha256(rel.encode()).hexdigest()[:12]


_FM_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.DOTALL)
_FM_KV = re.compile(r"^(\w[\w_]*):\s*(.*)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    kvs = {k: v.strip().strip("\"'") for k, v in _FM_KV.findall(m.group(1))}
    return kvs, text[m.end() :]


def _render_frontmatter(fm: dict[str, str], body: str) -> str:
    lines = ["---"]
    for k, v in fm.items():
        v = str(v).replace("\n", " ").replace("\r", "")
        if ":" in v or v.startswith('"') or v.startswith("'") or "---" in v:
            v = '"' + v.replace('"', '\\"') + '"'
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    fd = tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), suffix=".tmp",
        delete=False, encoding="utf-8",
    )
    try:
        fd.write(content)
        fd.close()
        os.replace(fd.name, str(path))
    except BaseException:
        fd.close()
        Path(fd.name).unlink(missing_ok=True)
        raise


def _file_mtime(p: Path) -> datetime:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(tz=timezone.utc)


def _project_readable_name(dir_name: str) -> str:
    """Recover last path component from Claude's encoding.

    Claude encodes '/Users/me/projects/my-app' as '-Users-me-projects-my-app'.
    Naive split('-') breaks hyphens in directory names like 'my-app'.
    """
    # Naive decode: '-' back to '/' — works when original path has no hyphens
    if dir_name.startswith("-"):
        original = "/" + dir_name[1:].replace("-", "/")
        if os.path.isdir(original):
            return os.path.basename(original)

    # Hyphens in the dir name made naive decode wrong ('my-app' → 'my/app').
    # Try joining trailing segments with hyphens and check if the path exists.
    parts = [p for p in dir_name.split("-") if p]
    if not parts:
        return dir_name
    for i in range(len(parts)):
        candidate_name = "-".join(parts[i:])
        candidate_path = "/" + "/".join(parts[:i]) + "/" + candidate_name if i > 0 else "/" + candidate_name
        if os.path.isdir(candidate_path):
            return candidate_name
    return parts[-1]


# ── Scorer ─────────────────────────────────────────────────────────────────


def _score_text(
    text: str,
    terms: list[str],
    patterns: list[re.Pattern] | None = None,
) -> tuple[float, str]:
    text_lower = text.lower()
    words = text_lower.split()
    if not words:
        return 0.0, ""

    if patterns is None:
        patterns = [
            re.compile(r"(?<![a-zA-Z0-9])" + re.escape(t) + r"(?![a-zA-Z0-9])")
            for t in terms
        ]

    hits = 0
    first_match_pos = -1
    first_match_term = ""
    for t, pattern in zip(terms, patterns):
        matches = list(pattern.finditer(text_lower))
        hits += len(matches)
        if matches and first_match_pos < 0:
            first_match_pos = matches[0].start()
            first_match_term = t

    if hits == 0:
        return 0.0, ""

    score = hits / (len(words) ** 0.5)

    if first_match_pos >= 0:
        start = max(0, first_match_pos - 60)
        end = min(len(text), first_match_pos + len(first_match_term) + 60)
        snippet = ("..." if start > 0 else "") + text[start:end].strip()
        if end < len(text):
            snippet += "..."
        return score, snippet

    return score, ""


# ── FileSystemStore ────────────────────────────────────────────────────────


class FileSystemStore(MemoryStore):

    def __init__(self) -> None:
        self._id_to_path: dict[str, str] = {}
        self._cache_built = False

    def _ensure_cache(self) -> None:
        if self._cache_built:
            return
        self._id_to_path.clear()
        for proj in self.scan_projects():
            mem_dir = Path(proj.memory_dir)
            try:
                for f in mem_dir.iterdir():
                    if f.suffix == ".md" and f.name != MEMORY_INDEX_FILENAME:
                        self._id_to_path[_memory_id(f)] = str(f)
            except OSError:
                continue
        for ns_dir in self._namespace_dirs():
            try:
                for f in ns_dir.iterdir():
                    if f.suffix == ".md" and f.name != MEMORY_INDEX_FILENAME:
                        self._id_to_path[_memory_id(f)] = str(f)
            except OSError:
                continue
        self._cache_built = True

    def _invalidate_cache(self) -> None:
        self._cache_built = False

    # ── Discovery ──────────────────────────────────────────────────────

    def scan_projects(self) -> list[Project]:
        if not PROJECTS_DIR.is_dir():
            return []
        projects: list[Project] = []
        for entry in sorted(PROJECTS_DIR.iterdir()):
            mem_dir = entry / "memory"
            if not mem_dir.is_dir():
                continue
            try:
                md_files = [f for f in mem_dir.iterdir() if f.suffix == ".md"]
            except OSError:
                continue
            count = sum(1 for f in md_files if f.name != MEMORY_INDEX_FILENAME)
            projects.append(
                Project(
                    id=entry.name,
                    name=_project_readable_name(entry.name),
                    memory_dir=str(mem_dir),
                    memory_count=count,
                )
            )
        return projects

    # ── Read ───────────────────────────────────────────────────────────

    def _parse_memory_file(
        self,
        path: Path,
        *,
        source_project: str | None = None,
        namespace: str | None = None,
    ) -> Memory:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = _parse_frontmatter(text)
        mtime = _file_mtime(path)
        return Memory(
            id=_memory_id(path),
            title=fm.get("name", path.stem),
            content=body.strip(),
            file_path=str(path),
            source_project=source_project,
            namespace=namespace,
            tags=[t.strip() for t in fm.get("tags", "").split(",") if t.strip()],
            memory_type=fm.get("type"),
            description=fm.get("description"),
            created_at=mtime,
            updated_at=mtime,
        )

    def _read_dir_memories(
        self,
        mem_dir: Path,
        *,
        source_project: str | None = None,
        namespace: str | None = None,
    ) -> list[Memory]:
        if not mem_dir.is_dir():
            return []
        results: list[Memory] = []
        for f in sorted(mem_dir.iterdir()):
            if f.suffix != ".md" or f.name == MEMORY_INDEX_FILENAME:
                continue
            try:
                results.append(
                    self._parse_memory_file(
                        f, source_project=source_project, namespace=namespace
                    )
                )
            except OSError:
                continue
        return results

    def read_project_memories(self, project_id: str) -> list[Memory]:
        return self._read_dir_memories(
            PROJECTS_DIR / project_id / "memory", source_project=project_id
        )

    def read_shared_memories(self, namespace: str) -> list[Memory]:
        ns_dir = SHARED_DIR / namespace
        if not ns_dir.resolve().is_relative_to(SHARED_DIR.resolve()):
            return []
        return self._read_dir_memories(ns_dir, namespace=namespace)

    def get_memory(self, memory_id: str) -> Memory | None:
        self._ensure_cache()
        path_str = self._id_to_path.get(memory_id)
        if not path_str:
            return None
        path = Path(path_str)
        if not path.exists():
            self._invalidate_cache()
            return None
        source_project = None
        namespace = None
        try:
            rel = path.relative_to(PROJECTS_DIR)
            source_project = rel.parts[0]
        except ValueError:
            try:
                rel = path.relative_to(SHARED_DIR)
                namespace = rel.parts[0]
            except ValueError:
                pass
        return self._parse_memory_file(
            path, source_project=source_project, namespace=namespace
        )

    # ── Write ──────────────────────────────────────────────────────────

    def write_memory(self, memory: Memory) -> Memory:
        if memory.namespace:
            target_dir = SHARED_DIR / memory.namespace
        elif memory.source_project:
            target_dir = PROJECTS_DIR / memory.source_project / "memory"
        else:
            raise ValueError("Memory must have namespace or source_project")

        target_dir.mkdir(parents=True, exist_ok=True)

        slug = re.sub(r"[^\w\-]", "-", memory.title.lower()).strip("-")[:60]
        path = target_dir / f"{slug}.md"
        # Use O_EXCL to atomically claim the filename (no TOCTOU race)
        counter = 1
        while True:
            try:
                fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                counter += 1
                path = target_dir / f"{slug}-{counter}.md"

        fm: dict[str, str] = {"name": memory.title}
        if memory.description:
            fm["description"] = memory.description
        if memory.memory_type:
            fm["type"] = memory.memory_type
        if memory.tags:
            fm["tags"] = ", ".join(memory.tags)

        _atomic_write(path, _render_frontmatter(fm, memory.content))

        memory.file_path = str(path)
        memory.id = _memory_id(path)
        self._update_index(target_dir, memory)
        self._invalidate_cache()
        return memory

    def _update_index(self, mem_dir: Path, memory: Memory) -> None:
        index = mem_dir / MEMORY_INDEX_FILENAME
        slug = Path(memory.file_path).name
        entry = f"- [{memory.title}]({slug})"
        if memory.description:
            entry += f" — {memory.description}"

        if index.exists():
            existing = index.read_text(encoding="utf-8")
            if f"]({slug})" in existing:
                return
            text = existing.rstrip() + "\n" + entry + "\n"
        else:
            text = entry + "\n"

        _atomic_write(index, text)

    def delete_memory(self, memory_id: str) -> bool:
        mem = self.get_memory(memory_id)
        if not mem:
            return False
        path = Path(mem.file_path)
        if not path.exists():
            return False
        path.unlink()
        index = path.parent / MEMORY_INDEX_FILENAME
        if index.exists():
            lines = index.read_text(encoding="utf-8").splitlines()
            marker = f"]({path.name})"
            lines = [l for l in lines if marker not in l]
            _atomic_write(index, "\n".join(lines) + "\n" if lines else "")
        self._invalidate_cache()
        return True

    # ── Search ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        scope: str = "all",
        project: str | None = None,
        limit: int = 10,
        registered_namespaces: set[str] | None = None,
    ) -> list[SearchResult]:
        terms = [re.sub(r"[^\w-]", "", t.lower()) for t in query.split() if len(t) >= 2]
        terms = [t for t in terms if t]
        if not terms:
            return []

        # Precompile search patterns once instead of per-file
        patterns = [
            re.compile(r"(?<![a-zA-Z0-9])" + re.escape(t) + r"(?![a-zA-Z0-9])")
            for t in terms
        ]

        candidates: list[Memory] = []
        is_named_ns = scope not in ("all", "shared", "project")

        if scope in ("all", "project"):
            for proj in self.scan_projects():
                if project and proj.id != project and proj.name != project:
                    continue
                candidates.extend(self.read_project_memories(proj.id))

        if scope in ("all", "shared"):
            for ns_dir in self._namespace_dirs(registered=registered_namespaces):
                candidates.extend(self.read_shared_memories(ns_dir.name))
        elif is_named_ns:
            candidates.extend(self.read_shared_memories(scope))

        results: list[SearchResult] = []
        for mem in candidates:
            searchable = f"{mem.title} {mem.description or ''} {mem.content}"
            score, ctx = _score_text(searchable, terms, patterns)
            if score > 0:
                results.append(SearchResult(memory=mem, score=score, match_context=ctx))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # ── Index Audit ────────────────────────────────────────────────────

    _INDEX_LINK_RE = re.compile(r"\[.*?\]\(([^)]+\.md)\)")

    def audit_index(self, mem_dir: Path) -> dict:
        """Compare MEMORY.md against actual files on disk.

        Returns orphans (on disk, not indexed) and dangling (indexed, not on disk).
        """
        index_path = mem_dir / MEMORY_INDEX_FILENAME

        on_disk = {
            f.name for f in mem_dir.iterdir()
            if f.suffix == ".md" and f.name != MEMORY_INDEX_FILENAME
        } if mem_dir.is_dir() else set()

        indexed: set[str] = set()
        if index_path.exists():
            text = index_path.read_text(encoding="utf-8")
            indexed = set(self._INDEX_LINK_RE.findall(text))

        return {
            "indexed": indexed,
            "on_disk": on_disk,
            "orphans": on_disk - indexed,
            "dangling": indexed - on_disk,
        }

    def rebuild_index(self, mem_dir: Path) -> int:
        """Rebuild MEMORY.md from files on disk. Returns entry count."""
        if not mem_dir.is_dir():
            return 0
        entries: list[str] = []
        for f in sorted(mem_dir.iterdir()):
            if f.suffix != ".md" or f.name == MEMORY_INDEX_FILENAME:
                continue
            fm, _ = _parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            title = fm.get("name", f.stem)
            desc = fm.get("description", "")
            line = f"- [{title}]({f.name})"
            if desc:
                line += f" — {desc}"
            entries.append(line)
        index_path = mem_dir / MEMORY_INDEX_FILENAME
        _atomic_write(index_path, "\n".join(entries[:200]) + "\n" if entries else "")
        return len(entries)

    # ── Internal ───────────────────────────────────────────────────────

    def _namespace_dirs(self, registered: set[str] | None = None) -> list[Path]:
        """Return namespace directories. If registered is provided, only include those."""
        if not SHARED_DIR.is_dir():
            return []
        dirs = [
            d
            for d in sorted(SHARED_DIR.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]
        if registered is not None:
            dirs = [d for d in dirs if d.name in registered]
        return dirs
