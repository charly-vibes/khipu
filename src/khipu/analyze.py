"""Analysis engine: prompt loader, DAG runner, backend executor."""

from __future__ import annotations

import importlib.resources
import json
import re
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from khipu.model import Session

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ResultMetadata:
    backend: str
    model: str
    condensation_mode: str  # "auto" | "always" | "never"
    prompt_versions: dict[str, str]  # analyzer_id -> version
    duration_ms: int


@dataclass
class AnalysisResult:
    timestamp: datetime
    session_count: int
    sessions_skipped: int
    workflows: list[dict[str, Any]] | None = None
    patterns: list[dict[str, Any]] | None = None
    crystallization: list[dict[str, Any]] | None = None
    custom: dict[str, list[dict[str, Any]]] | None = None
    metadata: ResultMetadata | None = None


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FM_LIST_RE = re.compile(r"^\[([^\]]*)\]$")


@dataclass
class PromptSpec:
    id: str
    version: str
    description: str
    depends_on: list[str]
    body: str
    source_path: Path | None = None


def _parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Parse minimal YAML frontmatter (no external deps)."""
    result: dict[str, str | list[str]] = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        m = _FM_LIST_RE.match(val)
        if m:
            items = [x.strip().strip('"').strip("'") for x in m.group(1).split(",") if x.strip()]
            result[key] = items
        else:
            result[key] = val
    return result


def load_prompt(path: Path) -> PromptSpec:
    text = path.read_text()
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"Prompt file {path} is missing YAML frontmatter")
    fm = _parse_frontmatter(m.group(1))
    body = text[m.end() :].strip()
    depends_on = fm.get("depends_on", [])
    if isinstance(depends_on, str):
        depends_on = [depends_on] if depends_on else []
    return PromptSpec(
        id=str(fm.get("id", path.stem)),
        version=str(fm.get("version", "unknown")),
        description=str(fm.get("description", "")),
        depends_on=depends_on,
        body=body,
        source_path=path,
    )


def _builtin_prompts() -> dict[str, PromptSpec]:
    prompts: dict[str, PromptSpec] = {}
    pkg = importlib.resources.files("khipu.prompts")
    for item in pkg.iterdir():
        if item.name.endswith(".md"):
            path = Path(str(item))  # Traversable → Path (no __fspath__ on Traversable)
            spec = load_prompt(path)
            prompts[spec.id] = spec
    return prompts


_USER_PROMPT_DIRS = [
    Path(".khipu/prompts"),
    Path.home() / ".config" / "khipu" / "prompts",
]


def discover_prompts(requested: list[str]) -> dict[str, PromptSpec]:
    """Load built-in prompts then overlay user prompts; return only requested + deps."""
    all_prompts = _builtin_prompts()
    for d in _USER_PROMPT_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                spec = load_prompt(f)
                all_prompts[spec.id] = spec
            except Exception as exc:  # noqa: BLE001
                print(f"WARNING: failed to load prompt {f}: {exc}", file=sys.stderr)

    # Expand requested to include all transitive deps
    needed: set[str] = set()
    queue = list(requested)
    while queue:
        aid = queue.pop()
        if aid in needed:
            continue
        needed.add(aid)
        dep_spec = all_prompts.get(aid)
        if dep_spec is None:
            available = ", ".join(sorted(all_prompts))
            raise ValueError(f"Unknown analyzer '{aid}'. Available: {available}")
        queue.extend(dep_spec.depends_on)

    return {aid: all_prompts[aid] for aid in needed}


# ---------------------------------------------------------------------------
# DAG resolution
# ---------------------------------------------------------------------------


def topo_sort(prompts: dict[str, PromptSpec]) -> list[str]:
    """Return analyzer ids in dependency-first topological order.

    Uses iterative DFS with two marker sets:
    - ``visiting``: nodes currently on the DFS stack (grey). Seeing a grey node
      means we have a back-edge → cycle detected.
    - ``visited``:  nodes whose entire subtree is resolved (black). Safe to skip.

    A node is appended to ``order`` only after all its dependencies are resolved,
    guaranteeing that every dependency appears before the nodes that require it.

    Raises ValueError on cycles or missing dependencies.
    """
    order: list[str] = []
    visited: set[str] = set()  # fully resolved (black nodes)
    visiting: set[str] = set()  # on current DFS path (grey nodes) — cycle sentinel

    def visit(aid: str) -> None:
        if aid in visited:
            return  # subtree already resolved; skip
        if aid in visiting:
            # We reached this node again while still resolving it → cycle
            raise ValueError(f"Circular dependency detected involving analyzer '{aid}'")
        visiting.add(aid)  # mark grey: entering DFS subtree
        spec = prompts[aid]
        for dep in spec.depends_on:
            if dep not in prompts:
                raise ValueError(
                    f"Analyzer '{aid}' depends on '{dep}', but '{dep}' is not in the run set"
                )
            visit(dep)  # recurse: resolve dependency first
        visiting.remove(aid)  # DFS subtree done; un-grey
        visited.add(aid)  # mark black: fully resolved
        order.append(aid)  # append after all deps → correct topo order

    for aid in prompts:
        visit(aid)
    return order


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Strip fences/preamble/postamble and parse JSON. Raises ValueError on failure."""
    # Strip markdown fences
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1)

    # Strip preamble before first [ or {
    start = min(
        (text.find(c) for c in ("[", "{") if text.find(c) != -1),
        default=-1,
    )
    if start == -1:
        raise ValueError("No JSON array or object found in response")
    try:
        value, _ = json.JSONDecoder().raw_decode(text, start)
        return value
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Backend loading and execution
# ---------------------------------------------------------------------------


@dataclass
class BackendConfig:
    id: str
    mode: str
    context_limit: int
    cli_command: str | None = None
    cli_input: str | None = None  # "stdin" | "file"
    model: str = "claude-sonnet-4-5"


def _builtin_backend(name: str) -> BackendConfig:
    pkg = importlib.resources.files("khipu.backends")
    path = Path(str(pkg.joinpath(f"{name}.toml")))  # Traversable → Path
    return _load_backend_toml(path)


def _load_backend_toml(path: Path) -> BackendConfig:
    with path.open("rb") as f:
        data = tomllib.load(f)
    b = data["backend"]
    cli = data.get("cli", {})
    return BackendConfig(
        id=b["id"],
        mode=b["mode"],
        context_limit=b.get("context_limit", 180_000),
        cli_command=cli.get("command"),
        cli_input=cli.get("input", "stdin"),
    )


def load_backend(backend_id: str | None) -> BackendConfig:
    if backend_id is None:
        return _builtin_backend("claude_cli")
    # Check user dirs first
    user_dirs = [Path(".khipu/backends"), Path.home() / ".config" / "khipu" / "backends"]
    for d in user_dirs:
        candidate = d / f"{backend_id}.toml"
        if candidate.exists():
            return _load_backend_toml(candidate)
    # Try built-in
    try:
        return _builtin_backend(backend_id)
    except FileNotFoundError:
        pass
    raise ValueError(f"Unknown backend '{backend_id}'. Place a TOML file in .khipu/backends/")


def _run_cli_backend(backend: BackendConfig, prompt: str, model: str | None) -> str:
    """Execute a CLI backend and return its stdout."""
    command = backend.cli_command or "claude -p $prompt_file --output-format text"
    effective_model = model or backend.model

    if backend.cli_input == "file":
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(prompt)
            prompt_file = Path(tmp.name)
        try:
            cmd = command.replace("$prompt_file", str(prompt_file))
            cmd = cmd.replace("$model", effective_model)
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return result.stdout
        finally:
            prompt_file.unlink(missing_ok=True)
    else:
        # stdin mode
        cmd = command.replace("$model", effective_model)
        result = subprocess.run(
            cmd, shell=True, input=prompt, capture_output=True, text=True, check=True
        )
        return result.stdout


def call_backend(backend: BackendConfig, prompt: str, model: str | None = None) -> str:
    """Send prompt to backend and return raw text response."""
    if backend.mode == "cli":
        return _run_cli_backend(backend, prompt, model)
    raise ValueError(f"Unsupported backend mode '{backend.mode}'")


# ---------------------------------------------------------------------------
# Main analyze function
# ---------------------------------------------------------------------------

_RESULT_FIELD: dict[str, str] = {
    "workflows": "workflows",
    "patterns": "patterns",
    "crystallize": "crystallization",
}


def analyze_sync(
    sessions: list[Session],
    *,
    analyzers: list[str] | None = None,
    backend: str | None = None,
    model: str | None = None,
    condense: bool | None = None,
    redact: bool = True,
    sessions_skipped: int = 0,
    condensation_mode: str = "auto",
) -> AnalysisResult:
    """Run the analysis pipeline on sessions (synchronous)."""
    if analyzers is None:
        analyzers = ["workflows", "patterns", "crystallize"]

    start_ms = int(time.time() * 1000)

    # Redact
    if redact:
        from khipu.redact import redact_sessions

        sessions = redact_sessions(sessions)

    # Load backend
    backend_cfg = load_backend(backend)

    # Condense
    from khipu.condense import condense_sessions

    if condense is True:
        mode = "always"
    elif condense is False:
        mode = "never"
    else:
        mode = "auto"
    sessions = condense_sessions(sessions, mode=mode, context_limit=backend_cfg.context_limit)

    # Serialize sessions once (cached for all analyzers)
    sessions_json = json.dumps([s.to_dict() for s in sessions], indent=2)

    # Load and order prompts
    prompts = discover_prompts(analyzers)
    order = topo_sort(prompts)

    # Only run requested analyzers (deps run first but aren't in final "requested" list
    # unless explicitly requested — they still need to run to provide {variables})
    requested_set = set(analyzers)

    # Run DAG
    results: dict[str, Any] = {}  # analyzer_id -> parsed JSON result
    prompt_versions: dict[str, str] = {}

    result = AnalysisResult(
        timestamp=datetime.now(tz=UTC),
        session_count=len(sessions),
        sessions_skipped=sessions_skipped,
    )

    for aid in order:
        spec = prompts[aid]
        prompt_versions[aid] = spec.version

        # Build template variables
        variables: dict[str, str] = {"sessions": sessions_json}
        dep_missing = False
        for dep in spec.depends_on:
            if dep not in results:
                print(
                    f"WARNING: skipping '{aid}' — dependency '{dep}' failed or was skipped",
                    file=sys.stderr,
                )
                dep_missing = True
                break
            variables[dep] = json.dumps(results[dep], indent=2)
        if dep_missing:
            continue

        # Substitute template variables
        prompt_text = spec.body
        for var, val in variables.items():
            prompt_text = prompt_text.replace(f"{{{var}}}", val)

        # Call backend
        try:
            raw = call_backend(backend_cfg, prompt_text, model)
        except subprocess.CalledProcessError as exc:
            print(f"WARNING: backend error for '{aid}': {exc}", file=sys.stderr)
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: unexpected error calling backend for '{aid}': {exc}", file=sys.stderr)
            continue

        # Extract JSON with one retry
        parsed: Any
        try:
            parsed = extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            retry_prompt = (
                prompt_text + "\n\nYour previous response was not valid JSON. "
                "Respond ONLY with the JSON array, nothing else."
            )
            try:
                raw2 = call_backend(backend_cfg, retry_prompt, model)
                parsed = extract_json(raw2)
            except Exception as exc2:  # noqa: BLE001
                print(
                    f"WARNING: '{aid}' returned invalid JSON after retry: {exc2}\n"
                    f"Raw response: {raw[:500]}",
                    file=sys.stderr,
                )
                continue

        results[aid] = parsed

        # Store on result object
        if aid == "workflows":
            result.workflows = parsed
        elif aid == "patterns":
            result.patterns = parsed
        elif aid == "crystallize":
            result.crystallization = parsed
        elif aid in requested_set:
            if result.custom is None:
                result.custom = {}
            result.custom[aid] = parsed

    duration_ms = int(time.time() * 1000) - start_ms
    result.metadata = ResultMetadata(
        backend=backend_cfg.id,
        model=model or backend_cfg.model,
        condensation_mode=condensation_mode,
        prompt_versions=prompt_versions,
        duration_ms=duration_ms,
    )
    return result


async def analyze(
    sessions: list[Session],
    *,
    analyzers: list[str] | None = None,
    backend: str | None = None,
    model: str | None = None,
    condense: bool | None = None,
    redact: bool = True,
    sessions_skipped: int = 0,
    condensation_mode: str = "auto",
) -> AnalysisResult:
    """Async wrapper around analyze_sync for use in async contexts."""
    import asyncio

    return await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: analyze_sync(
            sessions,
            analyzers=analyzers,
            backend=backend,
            model=model,
            condense=condense,
            redact=redact,
            sessions_skipped=sessions_skipped,
            condensation_mode=condensation_mode,
        ),
    )
