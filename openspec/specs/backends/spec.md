## Purpose

Configure how khipu calls LLMs — via HTTP API or shell command — using TOML files.

## Requirements

### Requirement: Backend TOML Format

A backend SHALL be a TOML file with a `[backend]` section containing: `id` (string), `mode` (`"api"` or `"cli"`), and `context_limit` (integer, token count). Backends SHALL be discovered from `.khipu/backends/` (project-local), `~/.config/khipu/backends/` (user-global), and the built-in `backends/` package directory.

#### Scenario: Backend discovered from project directory
- **WHEN** a valid `.toml` file is placed in `.khipu/backends/`
- **THEN** it is available by its `id` without any other configuration change

#### Scenario: User backend overrides built-in with same id
- **WHEN** a user backend TOML has the same `id` as a built-in backend
- **THEN** the user file takes precedence

---

### Requirement: API Mode

Backends with `mode = "api"` SHALL make HTTP calls. The `[api]` section MUST specify `url`, `method`, and `headers`. The `[api.body]` section SHALL provide a `template` string supporting `$prompt_json`, `$model`, and `$VARNAME` (any env var) substitution. The `[api.response]` section SHALL provide an `extract` jq-style expression to pull the text from the HTTP response.

`$prompt_json` SHALL be the prompt serialized as a JSON-encoded string (with proper escaping for quotes and newlines).

#### Scenario: API backend makes HTTP POST with prompt
- **WHEN** an API-mode backend is active and an analysis runs
- **THEN** an HTTP POST is made to the configured URL with the prompt JSON-encoded in the body template

#### Scenario: $prompt_json safely encodes special characters
- **WHEN** the prompt contains quotes or newlines
- **THEN** `$prompt_json` escapes them correctly so the request body is valid JSON

#### Scenario: Response text extracted via jq expression
- **WHEN** the API response is a JSON object
- **THEN** the `extract` expression (e.g., `.content[0].text`) is applied to retrieve the text

---

### Requirement: CLI Mode

Backends with `mode = "cli"` SHALL shell out to a command. The `[cli]` section MUST specify `command`, `input` (`"stdin"` or `"file"`), and `output` (`"stdout"`).

- `input = "stdin"`: prompt is piped to the command's stdin
- `input = "file"`: khipu writes the prompt to a temp file and passes the path via `$prompt_file`

Any program that reads a prompt and writes a response to stdout is a valid CLI backend.

#### Scenario: stdin-mode CLI backend receives prompt on stdin
- **WHEN** a CLI backend has `input = "stdin"` and an analysis runs
- **THEN** the prompt is piped to the command's stdin

#### Scenario: file-mode CLI backend receives prompt as temp file
- **WHEN** a CLI backend has `input = "file"` and an analysis runs
- **THEN** khipu writes the prompt to a temp file and passes its path as `$prompt_file` in the command

#### Scenario: CLI backend not in PATH errors clearly
- **WHEN** the CLI command is not found in PATH
- **THEN** an error is raised: "Backend '<id>' requires '<command>' which was not found in PATH"

---

### Requirement: Template Variables

Backend configs SHALL support these variable substitutions in command strings and body templates:
- `$prompt_json` — prompt as a JSON-encoded string (API mode)
- `$prompt_file` — path to a temp file containing the prompt (CLI file mode)
- `$model` — model name from the main config `[llm].model`
- `$VARNAME` — any ALL-CAPS name not matching a built-in keyword is resolved from the environment

The built-in keywords (`$prompt_json`, `$prompt_file`, `$model`) take precedence. Any other `$NAME` where `NAME` is entirely uppercase letters (and optionally underscores/digits) SHALL be treated as an environment variable lookup. Mixed-case or lowercase names that don't match a keyword SHALL be left as-is.

#### Scenario: $ANTHROPIC_API_KEY resolves from environment
- **WHEN** a backend header config contains `"x-api-key" = "$ANTHROPIC_API_KEY"`
- **THEN** the value is read from the `ANTHROPIC_API_KEY` environment variable at runtime

---

### Requirement: Built-in Backends

The system SHALL ship four built-in backend configurations:
- `claude-api` — Anthropic HTTP API, `mode = "api"`, `context_limit = 180000`, requires `ANTHROPIC_API_KEY`
- `ollama` — local ollama CLI, `mode = "cli"`, `context_limit = 8000`, requires `ollama` in PATH
- `claude-cli` — claude CLI tool, `mode = "cli"`, `context_limit = 180000`, requires `claude` in PATH
- `llm-cli` — Simon Willison's llm CLI, `mode = "cli"`, `context_limit = 8000`, requires `llm` in PATH

#### Scenario: khipu backends lists and validates all backends
- **WHEN** `khipu backends` is run
- **THEN** each backend is listed with its id, mode, endpoint/command, and availability status (OK or NOT FOUND)

---

### Requirement: Backend Selection

The active backend SHALL be configured via `[llm].backend` in `.khipu/config.toml`. It MAY be overridden per-run with `--backend <id>`. Model MAY be overridden with `--model <name>`.

#### Scenario: --backend flag overrides config
- **WHEN** `--backend ollama` is passed on the command line
- **THEN** the ollama backend is used for that run, regardless of config

#### Scenario: --model flag overrides config model
- **WHEN** `--model claude-opus-4-6` is passed
- **THEN** `$model` in the backend config resolves to `claude-opus-4-6` for that run
