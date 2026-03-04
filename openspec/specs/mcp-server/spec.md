## Purpose

Expose khipu's analysis capabilities as MCP tools, enabling any MCP client (Claude, Cursor, VS Code, Windsurf, Copilot) to analyze agent traces natively.

## Requirements

### Requirement: Stateless Tool Design

The MCP server SHALL be stateless — each tool call is self-contained. Tools SHALL return results directly without maintaining cached state between calls. This eliminates concurrency issues and makes all tools safe for parallel invocation.

#### Scenario: Concurrent tool calls are safe
- **WHEN** two `analyze_traces` calls are made simultaneously with different paths
- **THEN** both complete independently without interference

---

### Requirement: analyze_traces Tool

The server SHALL expose an `analyze_traces` tool that accepts `paths` (required, list of strings), `analyzers` (optional, default `["workflows", "patterns", "crystallize"]`), `output` (optional, default `"json"`), and `condense` (optional, enum `"auto"|"always"|"never"|"smart"`, default `"auto"`). It SHALL return the full analysis result as a string.

#### Scenario: analyze_traces with default parameters
- **WHEN** `analyze_traces` is called with `{"paths": ["./traces/"]}`
- **THEN** all three analyzers run with auto condensation and the result is returned as JSON

#### Scenario: analyze_traces with custom analyzers and template
- **WHEN** `analyze_traces` is called with `{"paths": ["./traces/"], "analyzers": ["patterns"], "output": "markdown"}`
- **THEN** only the `patterns` analyzer runs and the result is rendered as markdown

---

### Requirement: get_crystallization_candidates Tool

The server SHALL expose a `get_crystallization_candidates` tool that accepts `paths` (required, list of strings) and `min_score` (optional, float, default `0.6`). It SHALL run `patterns` and `crystallize` analyzers internally and return only candidates scoring at or above `min_score` with their concrete implementation suggestions.

#### Scenario: get_crystallization_candidates filters by score
- **WHEN** `get_crystallization_candidates` is called with `{"paths": ["./traces/"], "min_score": 0.7}`
- **THEN** only crystallization candidates with `score >= 0.7` are returned

#### Scenario: get_crystallization_candidates returns JSON array
- **WHEN** `get_crystallization_candidates` is called
- **THEN** the return value is a JSON array of candidate objects

---

### Requirement: Transport Modes

The MCP server SHALL support two transport modes:
- **stdio** (default, `khipu mcp`) — for local MCP clients (Claude Desktop, Cursor, VS Code)
- **SSE** (`khipu mcp --transport sse`) — for remote/network MCP clients

#### Scenario: stdio transport for local client
- **WHEN** an MCP client is configured with `{"command": "khipu", "args": ["mcp"]}`
- **THEN** the server communicates over stdin/stdout

#### Scenario: SSE transport for remote client
- **WHEN** `khipu mcp --transport sse` is started
- **THEN** the server accepts SSE connections over a network port

---

### Requirement: Tool Error Handling

On analysis failure (backend unavailable, no sessions found, LLM timeout, etc.), MCP tools SHALL return a structured error string rather than raising an unhandled exception. The error string SHALL describe the failure clearly so MCP clients can present it to the user.

#### Scenario: Backend unavailable during tool call
- **WHEN** `analyze_traces` is called but the configured LLM backend is unreachable
- **THEN** the tool returns a string beginning with "Error:" describing the failure, rather than propagating an exception

#### Scenario: No sessions found during tool call
- **WHEN** `analyze_traces` is called with paths that yield zero sessions
- **THEN** the tool returns a structured error: "Error: No sessions found at the provided paths"

---

### Requirement: MCP Tool Schema

The `analyze_traces` and `get_crystallization_candidates` tools SHALL expose formal JSON Schema input schemas so MCP clients can validate inputs and generate UI.

#### Scenario: Tool schema is valid JSON Schema
- **WHEN** an MCP client requests the tool list
- **THEN** each tool has a valid `inputSchema` with `type`, `properties`, and `required` fields
