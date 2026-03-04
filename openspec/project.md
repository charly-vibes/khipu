# Project Context

## Purpose

khipu (Quechua: knotted-string record) is a tool-agnostic agent trace analyzer. It reads what AI agents actually did across sessions and answers three questions:

1. What workflows keep recurring?
2. What patterns (good and bad) are emerging?
3. What's stable enough to become a permanent rule (crystallization)?

khipu implements the pattern recognition phase: reads traces from many sessions, detects which behaviors are converging, and scores their readiness for crystallization. It does not perform crystallization itself.

## Tech Stack

- **Language:** Python ≥ 3.11
- **CLI:** typer
- **Templates:** Jinja2
- **HTTP:** httpx
- **MCP:** mcp ≥ 1.0
- **Build:** hatchling via uv
- **Dev:** pytest, pytest-cov, ruff, mypy (strict)

## Project Conventions

### Code Style

- Formatter and linter: ruff (line length 100, target py311)
- Type checking: mypy strict mode
- All public APIs must be fully typed
- Use dataclasses for data models (`Session`, `Exchange`, `ToolCall`, `AnalysisResult`, `ResultMetadata`)

### Architecture Patterns

- **Five-stage pipeline:** ingest → redact → condense → analyze → emit
- **Three interfaces, one core:** CLI (typer), MCP server, Python library all share `src/khipu/` core
- **Extensible via files, not code:** new ingestor = drop a Python file; new analyzer = drop a `.md` file; new emitter = drop a `.j2` file; new backend = drop a `.toml` file. No registration, no build step.
- **Config discovery order:** project (`.khipu/`) > user (`~/.config/khipu/`) > built-in (shipped with package). Same-id files: project wins.
- **LLM is the analysis engine.** No heuristic pipelines, no clustering algorithms, no statistical models. Dead simple.

### Testing Strategy

- Tests live in `tests/` with fixture files under `tests/fixtures/`
- Golden file testing for emitter output (`tests/fixtures/expected/`)
- Fixture data: `tests/fixtures/claude_code_sessions/`, `tests/fixtures/aider_histories/`
- Prompt quality evaluation separate: `tests/eval/`
- Coverage threshold: 80% enforced via pytest-cov
- Run: `just test` or `uv run pytest`

### Git Workflow

- Single main branch; feature work via PRs
- Pre-commit hooks via prek: ruff lint+format, trailing whitespace, YAML/TOML checks
- Commit message convention: conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`)

## Domain Context

- **Session:** a single agent conversation, normalized from any source format
- **Exchange:** one turn in a session (human, agent, system, or tool role)
- **ToolCall:** a single tool invocation within an exchange
- **Ingestor:** a Python file that converts a trace format into `list[Session]`
- **Analyzer:** a prompt `.md` file with YAML frontmatter that runs an LLM analysis pass
- **Emitter:** a Jinja2 `.j2` template that renders `AnalysisResult` to a string
- **Backend:** a TOML file configuring how to call an LLM (API or CLI mode)
- **Condensation:** deterministic compression of session data to fit LLM context windows
- **Crystallization:** the process of recognizing when agent behavior has converged enough to encode as permanent rules/scripts/config

## Important Constraints

- **Redaction is on by default** and cannot be disabled for external API backends (only passthrough for local backends like ollama)
- **Stdin input requires `--ingestor` flag** — format auto-detection cannot work without a path
- **Ingestors are executed Python code** — trust model same as `make` or `source .env`. Use `--safe` to restrict to built-ins only.
- **Prompt files use `{variable}` substitution** (simple string replacement). Emitter templates use `{{ variable }}` (Jinja2). Do not mix.
- **`crystallize` analyzer depends on `patterns`** — both must be in the analyzer list or an error is raised at load time.

## External Dependencies

- **Anthropic API** (`claude-api` backend): requires `ANTHROPIC_API_KEY` env var
- **ollama** (`ollama` backend): requires `ollama` in PATH
- **claude CLI** (`claude-cli` backend): requires `claude` in PATH
- **llm CLI** (`llm-cli` backend): requires `llm` in PATH
- **MCP clients** (Claude Desktop, Cursor, VS Code, Windsurf, Copilot): connect via stdio or SSE transport
