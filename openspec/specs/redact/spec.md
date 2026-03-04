## Purpose

Strip secrets and sensitive data from sessions before any content reaches an LLM backend.

## Requirements

### Requirement: Automatic Redaction

Redaction SHALL run automatically as the second pipeline stage, after ingest and before condense/analyze. It SHALL be on by default and MUST NOT be skippable for external (non-passthrough) backends.

Redacted content SHALL be replaced with `[REDACTED:type]` tokens that preserve the structure of the surrounding text.

#### Scenario: Redaction runs before LLM call
- **WHEN** sessions are passed to the analyze stage
- **THEN** all content has been redacted before any LLM backend receives it

#### Scenario: Redacted token preserves structure
- **WHEN** an API key is found in session content
- **THEN** it is replaced with `[REDACTED:api_key]`, not an empty string

---

### Requirement: Default Redaction Patterns

The system SHALL redact the following patterns by default:
- API keys and tokens: strings starting with `sk-`, `ghp_`, `ghu_`, `Bearer `, `token `, `AKIA`
- Connection strings: `postgres://`, `mongodb://`, `redis://`, `mysql://`
- Private keys: PEM blocks matching `-----BEGIN .* PRIVATE KEY-----`
- Environment variable assignments: `export \w+=` and `\w+=\S+` in `.env` context
- AWS secrets: `aws_secret_access_key`, `aws_session_token`
- Email addresses
- IP addresses

#### Scenario: API key is redacted
- **WHEN** session content contains a string starting with `sk-`
- **THEN** that string is replaced with `[REDACTED:api_key]`

#### Scenario: Connection string is redacted
- **WHEN** session content contains `postgres://user:password@host/db`
- **THEN** the full URI is replaced with `[REDACTED:connection_string]`

#### Scenario: Private key block is redacted
- **WHEN** session content contains a `-----BEGIN RSA PRIVATE KEY-----` block
- **THEN** the entire block is replaced with `[REDACTED:private_key]`

---

### Requirement: Custom Redaction Patterns

Users MAY define additional regex patterns in `.khipu/config.toml` under `[security].custom_patterns`. These SHALL be applied in addition to the default patterns.

#### Scenario: Custom pattern is applied
- **WHEN** `custom_patterns = ["INTERNAL_TOKEN_\\w+"]` is configured and a session contains `INTERNAL_TOKEN_abc123`
- **THEN** it is replaced with `[REDACTED:custom]`

#### Scenario: Invalid custom pattern errors at startup
- **WHEN** a custom pattern is not valid regex
- **THEN** the system errors at startup with the pattern location

---

### Requirement: Passthrough Backends

The system SHALL support a `passthrough_backends` list in `[security]` config. Backends listed there are exempt from mandatory redaction. This is intended for local backends (e.g., `ollama`) where data does not leave the machine.

#### Scenario: Passthrough backend skips redaction
- **WHEN** the active backend is listed in `passthrough_backends`
- **THEN** redaction is skipped

#### Scenario: Non-passthrough backend always redacts
- **WHEN** the active backend is not listed in `passthrough_backends`
- **THEN** redaction runs regardless of any override

---

### Requirement: Heavily Redacted Sessions

When a session's content is almost entirely replaced by `[REDACTED:*]` tokens (≥90% of content replaced), the system SHALL include the session in the pipeline and emit a debug-level log noting the heavy redaction. It SHALL NOT silently drop or error on such sessions.

#### Scenario: Session content is entirely secrets
- **WHEN** a session file consists almost entirely of credential assignments
- **THEN** the session passes through as a heavily-redacted session and a debug log notes the redaction ratio

---

### Requirement: Debug Override

The `--no-redact` flag SHALL disable redaction for debugging purposes. The system MUST print a warning when `--no-redact` is used with a non-passthrough backend.

#### Scenario: --no-redact with external backend warns
- **WHEN** `--no-redact` is passed and the backend is not a passthrough backend
- **THEN** a warning is printed: redaction is disabled, data will reach an external LLM
