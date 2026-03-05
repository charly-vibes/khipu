---
id: patterns
version: "1.0"
description: Detect recurring patterns across sessions
depends_on: []
---

You are analyzing agent sessions to detect recurring patterns.

<sessions>
{sessions}
</sessions>

Find patterns — things that keep happening across sessions. Classify each as exactly one of:

- convention: consistent positive practice ("always does X")
- anti-pattern: repeated mistake ("keeps forgetting X")
- gotcha: environmental trap ("X silently fails when Y")
- decision-point: recurring fork with no settled answer yet

For each pattern:
- Describe it specifically (not "follows good practices")
- Cite which sessions demonstrate it (by session_id)
- Rate your confidence (0.0-1.0)

Respond ONLY with a JSON array, no other text:
[{
  "type": "convention|anti-pattern|gotcha|decision-point",
  "description": "...",
  "session_ids": [N, N, ...],
  "confidence": 0.X
}]
