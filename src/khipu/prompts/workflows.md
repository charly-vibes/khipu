---
id: workflows
version: "1.0"
description: Extract repeatable workflows from session traces
depends_on: []
---

You are analyzing agent session traces to discover repeatable workflows.

<sessions>
{sessions}
</sessions>

Find workflows — repeatable sequences of steps toward a goal — that
appear across multiple sessions.

For each workflow:
- Name it concisely
- State the goal
- List the ordered steps (actions like "Write test", "Run linter", not observations)
- Note variants where sessions diverged
- Count how many sessions followed this workflow

Only report workflows seen in 2+ sessions.

Respond ONLY with a JSON array, no other text:
[{
  "name": "...",
  "goal": "...",
  "steps": ["..."],
  "variants": [{"description": "...", "session_count": N}],
  "session_count": N,
  "session_ids": [N, N, ...]
}]
