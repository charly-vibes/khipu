## Purpose

Define the configuration file format, discovery order, and all configurable settings for khipu.

## Requirements

### Requirement: Config File Format

The primary config file SHALL be a TOML file named `config.toml`. It SHALL support the following top-level sections: `[llm]`, `[security]`, `[analysis]`, `[condensation]`, and `[output]`.

#### Scenario: Minimal valid config
- **WHEN** a `config.toml` with only `[llm] backend = "claude-api"` exists
- **THEN** all other settings use built-in defaults

---

### Requirement: Config Discovery Order

The engine SHALL discover and merge config from three locations in priority order (highest to lowest):
1. **Project-local:** `.khipu/config.toml` (current working directory)
2. **User-global:** `~/.config/khipu/config.toml`
3. **Built-in defaults:** shipped with the package

Project-local settings override user-global settings, which override built-in defaults. Settings are merged at the key level — a project config does not need to repeat settings covered by user-global config.

#### Scenario: Project config overrides user config
- **WHEN** user config sets `[llm] model = "claude-haiku-4-5"` and project config sets `[llm] model = "claude-opus-4-6"`
- **THEN** `claude-opus-4-6` is used for that project

#### Scenario: Partial project config inherits user defaults
- **WHEN** project config only sets `[llm] backend = "ollama"` and user config sets `[llm] model = "llama3"`
- **THEN** the effective config is `backend = "ollama"` and `model = "llama3"`

---

### Requirement: LLM Settings

The `[llm]` section SHALL support:
- `backend` (string) — id of the active backend (default: `"claude-api"`)
- `model` (string) — model name passed to the backend as `$model` (default: `"claude-sonnet-4-6"`)

#### Scenario: Default backend is claude-api
- **WHEN** no `[llm]` section exists in any config
- **THEN** the `claude-api` backend is used with `claude-sonnet-4-6`

---

### Requirement: Security Settings

The `[security]` section SHALL support:
- `redact` (bool) — enable/disable redaction (default: `true`; cannot be `false` for non-passthrough backends at runtime — overridden by enforcement)
- `custom_patterns` (list of strings) — additional regex patterns to redact
- `passthrough_backends` (list of strings) — backend ids exempt from mandatory redaction (default: `[]`)

#### Scenario: Custom patterns extend defaults
- **WHEN** `custom_patterns = ["MY_SECRET_\\w+"]` is set
- **THEN** strings matching `MY_SECRET_*` are redacted in addition to all default patterns

---

### Requirement: Analysis Settings

The `[analysis]` section SHALL support:
- `min_sessions` (int) — minimum sessions required to run analysis; fewer sessions produce a warning (default: `2`)
- `analyzers` (list of strings) — default set of analyzers to run (default: `["workflows", "patterns", "crystallize"]`)

#### Scenario: min_sessions warning
- **WHEN** only 1 session is available and `min_sessions = 2`
- **THEN** a warning is emitted: "Only 1 session found; analysis may be unreliable (min_sessions = 2)"

---

### Requirement: Condensation Settings

The `[condensation]` section SHALL support:
- `mode` (string: `"auto" | "always" | "smart" | "never"`) — default condensation mode (default: `"auto"`)

#### Scenario: Config sets default condensation mode
- **WHEN** `[condensation] mode = "always"` is set and no CLI flag overrides it
- **THEN** every run uses deterministic condensation

---

### Requirement: Output Settings

The `[output]` section SHALL support:
- `default_emit` (string) — default emitter template name (default: `"markdown"`)

#### Scenario: Config sets default emit template
- **WHEN** `[output] default_emit = "json"` is set and `--emit` is not passed
- **THEN** the json emitter is used

---

### Requirement: khipu init Scaffolding

`khipu init` SHALL create `.khipu/config.toml` with sensible defaults. It SHALL auto-detect available backends by checking:
- `ANTHROPIC_API_KEY` env var → include `claude-api` as an option
- `ollama` in PATH → include `ollama` as an option
- `claude` in PATH → include `claude-cli` as an option
- `llm` in PATH → include `llm-cli` as an option

The generated config SHALL include the detected backend as the active default and comment out others.

#### Scenario: Init detects ANTHROPIC_API_KEY
- **WHEN** `khipu init` runs and `ANTHROPIC_API_KEY` is set
- **THEN** `.khipu/config.toml` sets `backend = "claude-api"` as the active backend

#### Scenario: Init is idempotent
- **WHEN** `khipu init` is run in a directory that already has `.khipu/config.toml`
- **THEN** the existing file is not overwritten; a message notes the file already exists
