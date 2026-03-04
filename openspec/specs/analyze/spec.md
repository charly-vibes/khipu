## Purpose

Run LLM-based analysis passes over condensed sessions using prompt files, producing structured JSON results.

## Requirements

### Requirement: Analyzer File Format

An analyzer SHALL be a Markdown file with YAML frontmatter containing at minimum: `id` (string), `version` (string), and `depends_on` (list of analyzer IDs). The prompt body uses `{variable}` placeholders for variable substitution (simple string replacement, not Jinja2).

Analyzers SHALL be discovered automatically from `.khipu/prompts/` (project-local), `~/.config/khipu/prompts/` (user-global), and the built-in `prompts/` package directory. Dropping a file is sufficient — no registration required.

#### Scenario: Analyzer discovered from project directory
- **WHEN** a `.md` file with valid frontmatter is placed in `.khipu/prompts/`
- **THEN** it is available as an analyzer without any configuration change

#### Scenario: User analyzer overrides built-in with same id
- **WHEN** a user prompt file has the same `id` as a built-in analyzer
- **THEN** the user file takes precedence

---

### Requirement: Built-in Analyzers

The system SHALL ship three built-in analyzers:
- `workflows` — extracts repeatable step sequences toward a goal; `depends_on: []`
- `patterns` — detects conventions, anti-patterns, gotchas, and decision-points; `depends_on: []`
- `crystallize` — scores pattern readiness for crystallization with concrete implementation suggestions; `depends_on: [patterns]`

All three SHALL return JSON arrays. Each SHALL be documented with example output shapes.

#### Scenario: workflows returns JSON array
- **WHEN** the `workflows` analyzer runs
- **THEN** it returns a JSON array where each item has `name`, `goal`, `steps`, `variants`, `session_count`, `session_ids`

#### Scenario: patterns returns JSON array
- **WHEN** the `patterns` analyzer runs
- **THEN** it returns a JSON array where each item has `type`, `description`, `session_ids`, `confidence`

#### Scenario: crystallize returns JSON array with scores
- **WHEN** the `crystallize` analyzer runs
- **THEN** it returns a JSON array where each item has `pattern_index`, `convergence`, `stability`, `score`, `recommendation`, `suggested_implementation`

---

### Requirement: Analyzer DAG

Analyzers with non-empty `depends_on` SHALL form a directed acyclic graph (DAG). The engine SHALL run analyzers in dependency order and inject upstream results as template variables (e.g., `{patterns}` injects the JSON output of the `patterns` analyzer).

The engine SHALL detect and error on circular dependencies at load time. It SHALL error at load time if a `depends_on` entry references a missing analyzer.

#### Scenario: Downstream analyzer receives upstream output
- **WHEN** `crystallize` (which `depends_on: [patterns]`) runs
- **THEN** `{patterns}` in the crystallize prompt is replaced with the JSON output from the `patterns` analyzer

#### Scenario: Circular dependency errors at load time
- **WHEN** analyzer A depends on B and B depends on A
- **THEN** an error is raised at load time describing the cycle

#### Scenario: Missing dependency errors at load time
- **WHEN** an analyzer lists a `depends_on` entry that has no matching analyzer file
- **THEN** an error is raised at load time naming the missing analyzer and which prompt references it

#### Scenario: Upstream failure skips downstream
- **WHEN** an upstream analyzer fails (LLM error, JSON parse failure)
- **THEN** downstream analyzers that depend on it are skipped with a warning, and partial results are returned

---

### Requirement: Template Variables

Prompt files SHALL support the following substitution variables:
- `{sessions}` — condensed session JSON (always available)
- `{workflows}` — output from `workflows` analyzer (if in `depends_on`)
- `{patterns}` — output from `patterns` analyzer (if in `depends_on`)
- `{crystallization}` — output from `crystallize` analyzer (if in `depends_on`)
- `{<id>}` — output from any custom analyzer by its `id` (if in `depends_on`)

A variable SHALL only be substituted if the corresponding analyzer is listed in `depends_on`. An undeclared `{variable}` in a prompt file SHALL be left as the literal string `{variable}` (not substituted) and a warning SHALL be emitted. It SHALL NOT silently resolve to empty, which would corrupt the prompt.

#### Scenario: {sessions} is always available
- **WHEN** any analyzer prompt is rendered
- **THEN** `{sessions}` is replaced with the condensed session JSON

#### Scenario: Custom analyzer output is injectable
- **WHEN** a custom analyzer with `id: tech_debt` runs and another lists `depends_on: [tech_debt]`
- **THEN** `{tech_debt}` is substituted with the output of the `tech_debt` analyzer

---

### Requirement: JSON Extraction

LLM responses SHALL be processed to extract valid JSON using a multi-step strategy:
1. Strip markdown code fences (` ```json ... ``` `)
2. Strip preamble text before the first `[` or `{`
3. Strip postamble text after the last `]` or `}`
4. Attempt JSON parse
5. On failure: retry once with the message "Your previous response was not valid JSON. Respond ONLY with valid JSON (array or object), nothing else."
6. On second failure: report error with raw LLM response for debugging

#### Scenario: Markdown fences are stripped
- **WHEN** the LLM response wraps JSON in ` ```json ... ``` `
- **THEN** the fences are stripped and the inner JSON is parsed successfully

#### Scenario: Preamble is stripped
- **WHEN** the LLM response contains text before the opening `[`
- **THEN** that preamble is discarded and only the JSON portion is parsed

#### Scenario: One retry on parse failure
- **WHEN** the first JSON parse attempt fails
- **THEN** exactly one retry request is sent with a correction prompt

#### Scenario: Second failure returns error with raw response
- **WHEN** both parse attempts fail
- **THEN** an error is reported with the raw LLM response included for debugging

---

### Requirement: Per-Analyzer LLM Calls

Each analyzer SHALL make a separate LLM call with its own copy of `{sessions}`. The condensed session JSON SHALL be cached in memory and reused across analyzers — serialized once, not recomputed per call.

#### Scenario: Each analyzer makes an independent LLM call
- **WHEN** three analyzers (workflows, patterns, crystallize) run
- **THEN** three separate LLM calls are made

#### Scenario: Condensed JSON is computed once
- **WHEN** multiple analyzers share the same session set
- **THEN** the condensed JSON object is serialized once and the same string is reused in each prompt

---

### Requirement: Total Analyzer Failure

When all analyzers fail (e.g., backend unavailable), the system SHALL exit with a non-zero status code and print the error for each failed analyzer. It SHALL NOT silently emit an `AnalysisResult` with all-None fields.

#### Scenario: All analyzers fail with unavailable backend
- **WHEN** every analyzer fails due to a backend error
- **THEN** the process exits non-zero and each analyzer's error is printed before exit
