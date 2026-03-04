## Purpose

Render `AnalysisResult` into human- or machine-readable output using Jinja2 templates.

## Requirements

### Requirement: Jinja2 Template Format

An emitter SHALL be a Jinja2 `.j2` file. The filename minus `.j2` becomes the emit name used with `--emit`. Emitters SHALL be discovered automatically from `.khipu/emitters/` (project-local), `~/.config/khipu/emitters/` (user-global), and the built-in `emitters/` package directory.

**Note:** Emitter templates use `{{ variable }}` Jinja2 syntax. This is distinct from analyzer prompt files which use `{variable}` simple substitution. These must not be confused.

#### Scenario: Filename determines emit name
- **WHEN** a file `my_format.md.j2` is placed in `.khipu/emitters/`
- **THEN** `--emit my_format` selects it

#### Scenario: User emitter overrides built-in with same name
- **WHEN** a user emitter file has the same effective name as a built-in emitter
- **THEN** the user file takes precedence

---

### Requirement: Template Context

All emitter templates SHALL receive the following variables:
- `timestamp` — analysis run time
- `session_count` — number of sessions analyzed
- `sessions_skipped` — number skipped (too large, parse errors)
- `workflows` — list of workflow objects (if `workflows` analyzer ran; else `None`)
- `patterns` — list of pattern objects (if `patterns` analyzer ran; else `None`)
- `crystallization` — list of crystallization objects (if `crystallize` ran; else `None`)
- `result` — the complete `AnalysisResult` dict
- Any custom analyzer output, keyed by its `id`

#### Scenario: All standard variables available
- **WHEN** a template references `{{ session_count }}` and `{{ timestamp }}`
- **THEN** both are rendered with correct values

#### Scenario: Custom analyzer output available by id
- **WHEN** a custom analyzer with `id: tech_debt` ran
- **THEN** `{{ tech_debt }}` is available in the template context

---

### Requirement: Built-in Emitters

The system SHALL ship three built-in emitters:
- `markdown` (default) — human-readable report with sections for Workflows, Patterns, and Crystallization Candidates
- `json` — the complete `AnalysisResult` serialized as pretty-printed JSON via `{{ result | tojson(indent=2) }}`
- `claude_md` — a guidance block for appending to CLAUDE.md, formatted with `ALWAYS:`, `NEVER:`, `WATCH OUT:`, and `AUTOMATE:` prefixes wrapped in `<!-- KHIPU:BEGIN -->` / `<!-- KHIPU:END -->` markers

#### Scenario: markdown emitter produces readable report
- **WHEN** `--emit markdown` is used (or no `--emit` flag)
- **THEN** the output is a Markdown document with `## Workflows`, `## Patterns`, and `## Crystallization Candidates` sections

#### Scenario: json emitter produces parseable JSON
- **WHEN** `--emit json` is used
- **THEN** the output is valid JSON that can be piped to `jq`

#### Scenario: claude_md emitter produces CLAUDE.md block
- **WHEN** `--emit claude_md` is used
- **THEN** the output is a block beginning with `<!-- KHIPU:BEGIN` and ending with `<!-- KHIPU:END -->`

---

### Requirement: Template Error Handling

Jinja2 errors SHALL be caught and reported with context including: template file path, line number, and the list of available variables. Missing variables in templates SHALL render as empty string with a warning (not an unhandled exception).

Template syntax errors SHALL be detected at load time (not at render time) with the file and line number reported.

#### Scenario: Missing variable renders empty with warning
- **WHEN** a template references `{{ foobar }}` and `foobar` is not in the context
- **THEN** it renders as empty string and a warning is emitted

#### Scenario: Syntax error caught at load time
- **WHEN** a `.j2` file contains invalid Jinja2 syntax
- **THEN** an error is raised at load time with the file path, line number, and available variable list
