## Purpose

Normalize agent trace files from any format into a uniform `list[Session]` for downstream pipeline stages.

## Requirements

### Requirement: Session Data Model

The system SHALL normalize all trace formats into a common data model composed of `Session`, `Exchange`, `ToolCall`, and `Outcome` dataclasses.

A `Session` MUST have: `source` (string, e.g. `"claude-code"`), `timestamp` (datetime), `exchanges` (list of `Exchange`), and optional `outcome` (`Outcome`).
An `Exchange` MUST have: `role` (`"human" | "agent" | "system" | "tool"`), `content` (string), and optional `tool_calls` (`list[ToolCall]`).
A `ToolCall` MUST have: `tool` (string), `input` (Any), `output` (Any), `success` (bool).

#### Scenario: Serialize and deserialize a session
- **WHEN** `Session.to_dict()` is called
- **THEN** it returns a JSON-compatible dict that `Session.from_dict()` can reconstruct without data loss

---

### Requirement: Ingestor Interface

An ingestor SHALL be a Python file with two required functions: `can_handle(path: Path) -> bool` and `ingest(path: Path) -> list[Session]`. No base classes, registration, or decorators are required.

#### Scenario: Ingestor identifies a matching file
- **WHEN** `can_handle` is called with a file path it recognizes
- **THEN** it returns `True`

#### Scenario: Ingestor rejects an unrecognized file
- **WHEN** `can_handle` is called with a file path it does not recognize
- **THEN** it returns `False`

#### Scenario: Ingestor parses a file
- **WHEN** `ingest` is called with a recognized file path
- **THEN** it returns a non-empty `list[Session]` with valid structure

---

### Requirement: Two-Phase Format Detection

The engine SHALL detect file formats in two phases for performance. Phase 1 checks `path.suffix` and `path.name` only (no I/O). Phase 2 reads the first 2KB and matches against content patterns, and SHALL only run when Phase 1 is ambiguous (multiple ingestors match, or none matched).

Ingestors MAY declare `EXTENSIONS`, `FILENAMES`, `CONTENT_PATTERN`, and `PRIORITY` constants. When present, the engine uses them for Phase 1 and skips calling `can_handle` for that phase.

#### Scenario: Fast path resolves via extension
- **WHEN** exactly one ingestor declares a matching `EXTENSIONS` entry
- **THEN** Phase 2 is not run and that ingestor is selected without reading the file

#### Scenario: Content sniffing resolves ambiguity
- **WHEN** multiple ingestors match the same extension in Phase 1
- **THEN** Phase 2 reads the first 2KB and uses `CONTENT_PATTERN` to disambiguate

---

### Requirement: Ingestor Priority Resolution

When multiple ingestors claim the same file, priority SHALL be resolved in order:
1. Source level: user (`.khipu/ingestors/`) > global (`~/.config/khipu/ingestors/`) > built-in
2. Within same level: higher `PRIORITY` value wins
3. Same priority: more specific detector wins (exact filename > extension + content > extension only)
4. `generic` ingestor is always last (`PRIORITY = -100`)

#### Scenario: User ingestor overrides built-in for same extension
- **WHEN** a user ingestor in `.khipu/ingestors/` and a built-in ingestor both match a file
- **THEN** the user ingestor is selected

#### Scenario: Higher PRIORITY wins within same level
- **WHEN** two built-in ingestors match a file and one has a higher `PRIORITY`
- **THEN** the higher-priority ingestor is selected

---

### Requirement: Built-in Ingestors

The system SHALL ship three built-in ingestors:
- `claude_code` — Claude Code JSONL session logs (`.jsonl` files with `"tool_use"` or `"tool_result"` content); `PRIORITY = 10`
- `aider` — Aider chat history (`.aider.chat.history.md` or `.md` files with `####` headers); `PRIORITY = 10`
- `generic` — Any markdown/text conversation with role markers (`Human:`, `User:`, `Assistant:`, etc.); `PRIORITY = -100` (last resort)

#### Scenario: claude_code ingestor handles JSONL trace
- **WHEN** a `.jsonl` file whose first line contains `"tool_use"` or `"tool_result"` is ingested
- **THEN** it produces sessions with `source = "claude-code"` and tool calls populated

#### Scenario: aider ingestor handles chat history file
- **WHEN** a file named `.aider.chat.history.md` is ingested
- **THEN** it produces sessions with roles split on `####` headers

#### Scenario: generic ingestor is the fallback
- **WHEN** no other ingestor matches a markdown file with `Human:` / `Assistant:` role markers
- **THEN** the `generic` ingestor handles it as a last resort

---

### Requirement: Directory and File Input

The engine SHALL accept a file path, a directory (walked recursively), or a mix of both. Each file is offered to ingestors independently. Files that no ingestor can handle SHALL be warned and skipped; processing SHALL continue.

#### Scenario: Recursive directory walk
- **WHEN** a directory path is provided
- **THEN** all files within it (recursively) are individually offered to ingestors

#### Scenario: Unrecognized file skipped with warning
- **WHEN** a file matches no ingestor
- **THEN** a warning is emitted and that file is skipped; other files continue processing

#### Scenario: Parse error skipped with warning
- **WHEN** a matched ingestor raises an exception during `ingest`
- **THEN** a warning is emitted and that file is skipped; other files continue processing

---

### Requirement: Stdin Input

The engine SHALL accept `-` as a path to read from stdin. Because stdin has no path or extension, format detection cannot work; the `--ingestor` flag MUST be specified. Without it, the engine SHALL error with a message listing available ingestors.

#### Scenario: Stdin with ingestor flag succeeds
- **WHEN** `-` is the path and `--ingestor claude_code` is provided
- **THEN** stdin is read and parsed using the specified ingestor

#### Scenario: Stdin without ingestor flag errors
- **WHEN** `-` is the path and no `--ingestor` flag is provided
- **THEN** an error is raised: "Stdin input requires --ingestor flag. Available ingestors: ..."

---

### Requirement: Safe Mode

The `--safe` flag SHALL restrict ingestor loading to built-in ingestors only, ignoring user and project-local ingestors.

#### Scenario: Safe mode blocks user ingestors
- **WHEN** `--safe` is passed and a user ingestor exists in `.khipu/ingestors/`
- **THEN** the user ingestor is not loaded or executed

---

### Requirement: Ingestor Discovery

The engine SHALL auto-discover ingestors from `.khipu/ingestors/` (project-local), `~/.config/khipu/ingestors/` (user-global), and the built-in `ingestors/` package directory. No registration or import statements required — dropping a valid Python file is sufficient.

#### Scenario: Drop-in ingestor discovery
- **WHEN** a Python file with `can_handle` and `ingest` functions is placed in `.khipu/ingestors/`
- **THEN** it is automatically available without any configuration change

---

### Requirement: Empty Input Handling

When zero sessions are produced after ingest (empty directory, all files skipped, or all files parse to empty lists), the system SHALL NOT proceed to analyze or emit. It SHALL emit a warning and exit cleanly.

#### Scenario: Empty directory produces no sessions
- **WHEN** `khipu analyze ./empty-dir/` is run and no files are found
- **THEN** a warning is printed ("No sessions found. Check your trace paths.") and the process exits with a non-zero status code

#### Scenario: All files skipped produces no sessions
- **WHEN** all files in the input fail to parse or match no ingestor
- **THEN** the same warning and non-zero exit applies
