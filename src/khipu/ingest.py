"""Ingestor discovery engine."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Protocol

from khipu.model import Session

# Built-in ingestor module names (relative to khipu.ingestors)
_BUILTIN_IDS = ["claude_code", "generic"]

# User drop-in directories (in priority order)
_USER_DIRS = [
    Path(".khipu/ingestors"),
    Path.home() / ".config" / "khipu" / "ingestors",
]


class _IngestorModule(Protocol):
    PRIORITY: int

    def can_handle(self, path: Path) -> bool: ...
    def ingest(self, path: Path) -> list[Session]: ...


def _load_builtin(name: str) -> ModuleType:
    return importlib.import_module(f"khipu.ingestors.{name}")


def _load_file(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load ingestor from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _discover(*, safe: bool = False) -> list[tuple[str, ModuleType]]:
    """Return (id, module) pairs sorted by PRIORITY descending."""
    modules: list[tuple[str, ModuleType]] = []

    # Built-ins
    for name in _BUILTIN_IDS:
        mod = _load_builtin(name)
        modules.append((name, mod))

    # User drop-ins
    if not safe:
        for user_dir in _USER_DIRS:
            if not user_dir.is_dir():
                continue
            for py_file in sorted(user_dir.glob("*.py")):
                mod_id = py_file.stem
                if mod_id in dict(modules):
                    continue  # don't shadow built-ins by id
                try:
                    mod = _load_file(py_file)
                    modules.append((mod_id, mod))
                except Exception as exc:  # noqa: BLE001
                    print(f"WARNING: failed to load ingestor {py_file}: {exc}", file=sys.stderr)

    # Sort by PRIORITY descending (higher = checked first)
    modules.sort(key=lambda t: getattr(t[1], "PRIORITY", 0), reverse=True)
    return modules


def _pick_ingestor(
    path: Path,
    modules: list[tuple[str, ModuleType]],
) -> ModuleType | None:
    """Two-phase detection: extension/content-pattern first, then can_handle."""
    # Phase 1: metadata constants
    for _id, mod in modules:
        extensions = getattr(mod, "EXTENSIONS", None)
        filenames = getattr(mod, "FILENAMES", None)
        content_pat = getattr(mod, "CONTENT_PATTERN", None)

        ext_ok = extensions is None or path.suffix in extensions
        name_ok = filenames is None or path.name in filenames
        if not (ext_ok and name_ok):
            continue
        if content_pat is not None:
            try:
                snippet = path.read_text(errors="replace")[:2000]
                if not re.search(content_pat, snippet):
                    continue
            except OSError:
                continue
        return mod

    # Phase 2: can_handle fallback
    for _id, mod in modules:
        try:
            if mod.can_handle(path):
                return mod
        except Exception:  # noqa: BLE001
            continue
    return None


def ingest(
    path: str | Path,
    *,
    ingestor: str | None = None,
    safe: bool = False,
) -> list[Session]:
    """Normalize trace files into Sessions.

    Accepts a file path, directory (recursive), or "-" for stdin.
    """
    is_stdin = str(path) == "-"
    p = None if is_stdin else Path(path)

    modules = _discover(safe=safe)
    id_map = dict(modules)

    # Stdin
    if is_stdin:
        if ingestor is None:
            available = ", ".join(id_map)
            raise ValueError(
                f"Stdin input requires --ingestor flag. Available ingestors: {available}"
            )
        if ingestor not in id_map:
            raise ValueError(f"Unknown ingestor '{ingestor}'. Available: {', '.join(id_map)}")
        # Write stdin to a temp file so ingestors can use Path API
        import tempfile
        data = sys.stdin.buffer.read()
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return id_map[ingestor].ingest(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    assert p is not None

    # Force a specific ingestor
    if ingestor is not None:
        if ingestor not in id_map:
            raise ValueError(f"Unknown ingestor '{ingestor}'. Available: {', '.join(id_map)}")
        mod = id_map[ingestor]
        if p.is_dir():
            return _ingest_dir(p, lambda f: mod)
        return mod.ingest(p)

    # Auto-detect
    if p.is_dir():
        return _ingest_dir(p, lambda f: _pick_ingestor(f, modules))

    mod = _pick_ingestor(p, modules)
    if mod is None:
        raise ValueError(f"No ingestor found for '{p}'. Try --ingestor <name>.")
    return mod.ingest(p)


def _ingest_dir(
    directory: Path,
    pick_fn: object,
) -> list[Session]:
    """Recursively ingest all parseable files in *directory*."""
    from typing import Callable
    pick: Callable[[Path], ModuleType | None] = pick_fn  # type: ignore[assignment]
    sessions: list[Session] = []
    for file in sorted(directory.rglob("*")):
        if not file.is_file():
            continue
        # Skip files inside hidden directories (e.g. .git, .venv)
        if any(part.startswith(".") for part in file.relative_to(directory).parts[:-1]):
            continue
        mod = pick(file)
        if mod is None:
            continue
        try:
            sessions.extend(mod.ingest(file))
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: failed to ingest {file}: {exc}", file=sys.stderr)
    return sessions
