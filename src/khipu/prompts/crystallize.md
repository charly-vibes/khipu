---
id: crystallize
version: "1.0"
description: Score pattern readiness for crystallization
depends_on: [patterns]
---

You are evaluating detected patterns for crystallization — whether
they are stable enough to become permanent rules, scripts, or config.

<patterns>
{patterns}
</patterns>

<sessions>
{sessions}
</sessions>

For each pattern, score:
- convergence: Do sessions consistently follow the same approach? (0-1)
- stability: Has the pattern been consistent in recent sessions? (0-1)
- recommendation: explore | monitor | crystallize | automate

Score interpretation:
- explore (0.0-0.3): Still diverging. Agent discovery is valuable.
- monitor (0.3-0.6): Showing convergence. Keep watching.
- crystallize (0.6-0.8): Stable enough to encode as checklist/rule.
- automate (0.8-1.0): Ready for deterministic script/hook/config.

If recommending crystallize or automate, suggest a CONCRETE implementation
("Add pre-commit hook that runs X", "Add rule to CLAUDE.md: always Y").

Respond ONLY with a JSON array, no other text:
[{
  "pattern_index": N,
  "convergence": 0.X,
  "stability": 0.X,
  "score": 0.X,
  "recommendation": "explore|monitor|crystallize|automate",
  "suggested_implementation": "..."
}]
