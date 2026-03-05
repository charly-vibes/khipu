Tracer bullet implementation plan for khipu.

## Goal
End-to-end slice: ingest Claude Code JSONL → redact → condense (deterministic) → analyze (workflows + patterns + crystallize) → emit markdown. Uses Claude CLI backend. All three built-in analyzers included. No MCP, no smart condense, no custom backends in scope.

## Task Breakdown

### 1. Project scaffold
- pyproject.toml with uv/hatch, khipu package, typer CLI entry point
- khipu analyze <path> wired to a no-op stub
- khipu --version works

### 2. Trace model
- Session, Exchange, ToolCall, Outcome dataclasses in khipu/model.py
- to_dict / from_dict serialization

### 3. Ingestor engine + claude_code ingestor
- Engine: discover ingestors, two-phase detection (extension → content), priority resolution
- Built-in: claude_code.py (JSONL), generic.py (markdown fallback)
- khipu analyze runs ingest stage visibly

### 4. Redaction
- Default patterns: API keys, connection strings, private keys, env vars, AWS secrets, emails, IPs
- [REDACTED:type] token replacement
- --no-redact flag with warning

### 5. Condensation (deterministic only)
- Strip tool call I/O, keep names/paths/success booleans
- First 100 chars of human messages, 80 chars of agent messages
- Output: structured JSON summary per session
- auto mode: estimate tokens (len/4), condense if sessions > 70% of context_limit
- --condense (always) and --no-condense (never) flags

### 6. Analysis engine + prompts + Claude CLI backend
- Engine: load prompt files, resolve depends_on DAG, inject {sessions}/{patterns}/{workflows}
- Backends: CLI mode via TOML config, shell out to claude CLI
- Built-in prompts: workflows.md, patterns.md, crystallize.md
- JSON extraction with retry logic

### 7. Emitter
- Jinja2 markdown template (default)
- emit() function renders AnalysisResult
- --emit flag on CLI

### 8. Wire end-to-end
- khipu analyze <path> runs all 5 stages
- Progress output to stderr, result to stdout
- khipu analyze - --ingestor claude_code (stdin support)

## Backend Config (Claude CLI)
backends/claude_cli.toml:
  mode = cli
  command = 'claude -p ""'
  context_limit = 180000

## Acceptance Criteria
khipu analyze ./traces/ produces a markdown report with workflows, patterns, and crystallization scores from real Claude Code session files.
