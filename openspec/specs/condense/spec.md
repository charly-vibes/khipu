## Purpose

Compress sessions into compact representations that preserve workflow signal while dropping raw I/O bulk, so they fit within LLM context windows.

## Requirements

### Requirement: Deterministic Condensation

The default condensation transform SHALL be deterministic (no LLM call). It SHALL strip tool call I/O bodies and retain only structural signal:
- Tool call names and file paths
- Success/failure booleans
- First 100 characters of human messages
- First 80 characters of agent messages
- File paths mentioned in content

The condensed representation SHALL be serialized to JSON and injected into analyzer prompts via the `{sessions}` variable.

#### Scenario: Condensed output strips tool I/O bodies
- **WHEN** a session with large tool call outputs is condensed
- **THEN** the output body is removed and only tool name, target path, and success are retained

#### Scenario: Human message is truncated to 100 chars
- **WHEN** a human exchange has content longer than 100 characters
- **THEN** only the first 100 characters appear in the condensed representation

#### Scenario: Condensed JSON is reused across analyzers
- **WHEN** multiple analyzers run on the same session set
- **THEN** the condensed JSON is serialized once and reused; not recomputed per analyzer call

---

### Requirement: Smart Condensation

The `--smart-condense` flag SHALL enable LLM-based semantic condensation. This makes one extra LLM call per session batch using the internal `_condense.md` prompt to produce semantic summaries with paraphrased intent and action descriptions.

The `_condense.md` prompt SHALL be prefixed with `_` to distinguish it from user-facing analyzers. It SHALL NOT be listed by `khipu prompts` and SHALL NOT be overridable by user prompt files. The underscore prefix IS the protection mechanism — the engine SHALL skip any user-provided prompt file whose filename starts with `_`.

#### Scenario: Smart condense produces semantic summary
- **WHEN** `--smart-condense` is passed
- **THEN** an extra LLM call is made per batch and the result is a semantic summary, not a structural strip

#### Scenario: _condense.md is not listed or overridable
- **WHEN** `khipu prompts` is run
- **THEN** `_condense` does not appear in the output

---

### Requirement: Condensation Modes

The system SHALL support four condensation modes:

| Mode | Trigger | Behavior |
|------|---------|----------|
| `auto` | default | Estimate tokens; if raw sessions fit in 70% of `context_limit`, use raw; otherwise deterministic condense |
| `always` | `--condense` | Always deterministic condense |
| `smart` | `--smart-condense` | LLM-based semantic condensation |
| `never` | `--no-condense` | Raw sessions; error if too large for context |

Token estimation: `len(json_text) / 4`. Reserve 30% of `context_limit` for prompt and response.

#### Scenario: Auto mode uses raw sessions when they fit
- **WHEN** estimated tokens of raw sessions ≤ 70% of backend `context_limit`
- **THEN** raw sessions are used without condensation

#### Scenario: Auto mode condenses when sessions exceed budget
- **WHEN** estimated tokens of raw sessions > 70% of backend `context_limit`
- **THEN** deterministic condensation is applied

#### Scenario: --no-condense errors if sessions exceed context
- **WHEN** `--no-condense` is passed and raw sessions exceed the backend context limit
- **THEN** an error is raised

---

### Requirement: Session Truncation on Overflow

When sessions exceed the backend context limit even after condensation, the system SHALL take the most recent sessions that fit and emit a warning stating how many were skipped. The `--max-sessions N` flag SHALL set an explicit cap on session count before condensation.

#### Scenario: Overflow takes most recent sessions
- **WHEN** condensed sessions still exceed context limit
- **THEN** the oldest sessions are dropped and a warning is emitted: "N sessions skipped (context limit)"

#### Scenario: --max-sessions caps session count
- **WHEN** `--max-sessions 20` is passed and 50 sessions are available
- **THEN** only the 20 most recent sessions are processed

#### Scenario: --max-sessions 0 or negative errors
- **WHEN** `--max-sessions 0` or a negative value is passed
- **THEN** an error is raised: "--max-sessions must be a positive integer"

---

### Requirement: Backend Context Limits

Each backend TOML file SHALL declare a `context_limit` (integer, token count). The condense stage SHALL use this value for auto-mode decisions and overflow handling.

#### Scenario: Context limit read from backend config
- **WHEN** the active backend has `context_limit = 180000` in its TOML
- **THEN** auto-mode uses 180000 as the limit for all condensation decisions
