## Purpose

Command-line interface for running khipu analysis, managing configuration, and accessing utility commands.

## Requirements

### Requirement: analyze Command

`khipu analyze <path>...` SHALL be the primary command. It accepts one or more file paths, directory paths, or `-` for stdin. It SHALL run the full pipeline (ingest → redact → condense → analyze → emit) and print the result to stdout.

#### Scenario: Analyze a directory of traces
- **WHEN** `khipu analyze ./traces/` is run
- **THEN** all files in `./traces/` are ingested, analyzed, and a markdown report is printed to stdout

#### Scenario: Analyze from stdin with explicit ingestor
- **WHEN** `cat session.jsonl | khipu analyze - --ingestor claude_code` is run
- **THEN** stdin is read using the `claude_code` ingestor and the result is printed

#### Scenario: Multiple paths accepted
- **WHEN** `khipu analyze ./a.jsonl ./b.md ./c/` is run
- **THEN** all three inputs are ingested together and analyzed as a single session set

---

### Requirement: analyze Flags

The `analyze` command SHALL support:
- `--only <analyzers>` — comma-separated list of analyzers as a single string (e.g., `--only workflows` or `--only patterns,crystallize`; NOT `--only patterns --only crystallize`)
- `--emit <template>` — output template name (default: `markdown`)
- `--backend <id>` — override LLM backend
- `--model <name>` — override model name
- `--condense` — always deterministic condense
- `--smart-condense` — LLM-based semantic condense
- `--no-condense` — raw sessions (error if too large)
- `--max-sessions N` — cap session count
- `--no-redact` — disable redaction (prints warning for non-passthrough backends)
- `--safe` — built-in ingestors only
- `--ingestor <id>` — required when reading from stdin
- `-v` — log pipeline decisions
- `-vv` — also log raw LLM prompts and responses

#### Scenario: --only runs subset of analyzers
- **WHEN** `khipu analyze ./traces/ --only patterns` is run
- **THEN** only the `patterns` analyzer runs; `workflows` and `crystallize` do not

#### Scenario: --emit json produces parseable output
- **WHEN** `khipu analyze ./traces/ --emit json` is run
- **THEN** valid JSON is printed to stdout

#### Scenario: -vv logs raw prompts and responses
- **WHEN** `khipu analyze ./traces/ -vv` is run
- **THEN** the raw LLM prompt and response for each analyzer are logged

---

### Requirement: Run Summary Line

Every `khipu analyze` run SHALL print a summary line at the end:
```
Analyzed N/M files (X skipped: Y parse errors, Z no matching ingestor)
Ran N analyzers: <list>
```

#### Scenario: Summary reflects skip count
- **WHEN** 17 of 20 files are successfully ingested
- **THEN** the summary reads "Analyzed 17/20 files (3 skipped: ...)"

---

### Requirement: ingest Command

`khipu ingest <path>` SHALL normalize traces and dump them as JSON without running analysis. Useful for inspecting what khipu sees before committing to an LLM call.

#### Scenario: ingest dumps normalized sessions as JSON
- **WHEN** `khipu ingest ./session.jsonl` is run
- **THEN** the normalized session JSON is printed to stdout with no LLM call made

---

### Requirement: mcp Command

`khipu mcp` SHALL start the MCP server using stdio transport (default). `khipu mcp --transport sse` SHALL use SSE transport for remote access.

#### Scenario: mcp starts stdio server
- **WHEN** `khipu mcp` is run
- **THEN** the MCP server starts and listens on stdio

---

### Requirement: Utility Commands

The CLI SHALL provide:
- `khipu backends` — list all configured backends with availability status
- `khipu prompts` — list all available analyzers (user + built-in; excludes `_condense`)
- `khipu emitters` — list all available emitter templates
- `khipu init` — scaffold `.khipu/` with default config, detecting available backends

#### Scenario: khipu init detects available backends
- **WHEN** `khipu init` is run and `ANTHROPIC_API_KEY` is set and `claude` is in PATH
- **THEN** `.khipu/config.toml` is created suggesting `claude-api` and `claude-cli` as options

#### Scenario: khipu prompts excludes _condense
- **WHEN** `khipu prompts` is run
- **THEN** `_condense` does not appear in the output

---

### Requirement: Verbosity Levels

The CLI SHALL support two verbosity flags: `-v` (log pipeline decisions, condensation mode chosen, files skipped, etc.) and `-vv` (additionally log raw LLM prompts sent and raw responses received).

#### Scenario: -v logs pipeline decisions
- **WHEN** `khipu analyze ./traces/ -v` is run
- **THEN** the CLI logs which condensation mode was chosen, which ingestor handled each file, and any files skipped
