## Purpose

Python library API for embedding khipu analysis directly into agent frameworks and tools.

## Requirements

### Requirement: Public API Functions

The `khipu` package SHALL expose three top-level functions: `ingest`, `analyze`, and `emit`. These SHALL be importable directly from `khipu`.

```python
from khipu import analyze, ingest, emit
```

#### Scenario: Top-level functions are importable
- **WHEN** `from khipu import analyze, ingest, emit` is executed
- **THEN** all three names are available without importing submodules

---

### Requirement: ingest Function

`ingest(path, *, ingestor=None, safe=False) -> list[Session]` SHALL normalize trace files into Sessions. It SHALL accept a file path, directory (recursive), or `"-"` for stdin. The `ingestor` parameter forces a specific ingestor by id. The `safe` parameter restricts to built-in ingestors only.

#### Scenario: ingest a directory
- **WHEN** `ingest("./traces/")` is called
- **THEN** it returns a list of `Session` objects from all recognized files in the directory

#### Scenario: ingest with forced ingestor
- **WHEN** `ingest("./session.jsonl", ingestor="claude_code")` is called
- **THEN** the `claude_code` ingestor is used regardless of auto-detection

---

### Requirement: analyze Function

`analyze` SHALL be an async function: `async def analyze(sessions, *, analyzers=["workflows", "patterns", "crystallize"], backend=None, model=None, condense=None, redact=True) -> AnalysisResult`. Implementations SHOULD provide a synchronous convenience wrapper (e.g., `analyze_sync`) for contexts that do not use asyncio.

`condense=None` means auto mode. `condense=True` means always. `condense=False` means never. `condense="smart"` means LLM-based. Implementations SHOULD also accept a `Literal["auto", "always", "never", "smart"]` string for clarity — the mixed bool/None/str signature is a known trade-off for backward compatibility with the CLI's flag model.

#### Scenario: analyze with default parameters
- **WHEN** `analyze(sessions)` is called
- **THEN** all three analyzers run with auto condensation, redaction enabled, and the configured backend

#### Scenario: analyze with custom analyzers
- **WHEN** `analyze(sessions, analyzers=["patterns"])` is called
- **THEN** only the `patterns` analyzer runs

#### Scenario: analyze with condense=False
- **WHEN** `analyze(sessions, condense=False)` is called
- **THEN** raw sessions are used without condensation (error if too large)

---

### Requirement: emit Function

`emit(result, template="markdown") -> str` SHALL render an `AnalysisResult` through a named Jinja2 emitter template and return the rendered string.

#### Scenario: emit renders markdown by default
- **WHEN** `emit(result)` is called
- **THEN** it returns a markdown-formatted report string

#### Scenario: emit with json template
- **WHEN** `emit(result, template="json")` is called
- **THEN** it returns a valid JSON string

---

### Requirement: AnalysisResult Type

`AnalysisResult` SHALL be a dataclass with: `timestamp` (datetime), `session_count` (int), `sessions_skipped` (int), `workflows` (list[dict] | None), `patterns` (list[dict] | None), `crystallization` (list[dict] | None), `custom` (dict[str, list[dict]] | None), and `metadata` (ResultMetadata | None).

`ResultMetadata` SHALL have: `backend` (str), `model` (str), `condensation_mode` (str: `"auto"|"always"|"never"|"smart"`), `prompt_versions` (dict[str, str] mapping analyzer_id to version), `duration_ms` (int).

#### Scenario: AnalysisResult has expected fields
- **WHEN** `analyze(sessions)` returns a result
- **THEN** `result.session_count`, `result.patterns`, `result.workflows`, and `result.metadata.backend` are all accessible

#### Scenario: Unused analyzers produce None fields
- **WHEN** `analyze(sessions, analyzers=["patterns"])` is called
- **THEN** `result.workflows` is `None` and `result.patterns` is a list

---

### Requirement: Type Safety

All public API functions and data models SHALL be fully typed with Python type annotations. The library SHALL pass mypy strict mode with no errors.

#### Scenario: mypy strict passes on library code
- **WHEN** `mypy src/khipu` is run in strict mode
- **THEN** no type errors are reported
