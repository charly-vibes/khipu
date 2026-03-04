<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

<!-- WAI:START -->
# Workflow Tools

This project uses **wai** to track the *why* behind decisions — research,
reasoning, and design choices that shaped the code. Run `wai status` first
to orient yourself.

Detected workflow tools:
- **wai** — research, reasoning, and design decisions
- **beads (bd)** — issue tracking (tasks, bugs, dependencies)
- **openspec** — specifications and change proposals (see `openspec/AGENTS.md`)

> **CRITICAL**: Apply TDD and Tidy First throughout — not just when writing code:
> - **Planning/task creation**: each ticket should map to a red→green→refactor cycle; refactoring tasks must be separate tickets from feature tasks.
> - **Design**: define the test shape (inputs/outputs) before designing the implementation.
> - **Implementation**: write the failing test first, then make it pass, then tidy in a separate commit.

> **When beginning research or creating a ticket**: run `wai search "<topic>"` to check for existing patterns before writing new content.
> **Ro5**: The Rule of 5 skill is installed. Run `/ro5` after key phase transitions — implement, research, design — for iterative quality review.

## When to Use What

| Need | Tool | Example |
|------|------|---------|
| Record reasoning/research | wai | `wai add research "findings"` |
| Capture design decisions | wai | `wai add design "architecture choice"` |
| Session context transfer | wai | `wai handoff create <project>` |
| Track work items/bugs | beads | `bd create --title="..." --type=task` |
| Find available work | beads | `bd ready` |
| Manage dependencies | beads | `bd dep add <blocked> <blocker>` |
| Propose system changes | openspec | Read `openspec/AGENTS.md` |
| Define requirements | openspec | `openspec validate --strict` |

Key distinction:
- **wai** = *why* decisions were made (reasoning, context, handoffs)
- **beads** = *what* needs to be done (concrete tasks, status tracking)
- **openspec** = *what the system should look like* (specs, requirements, proposals)

## Starting a Session

1. Run `wai status` to see active projects, current phase, and suggestions.
2. Run `bd ready` to find available work items.
   Before claiming: read the relevant source files to confirm
   the issue is not already implemented.
3. Check `openspec list` for active change proposals.
4. Check the phase — it tells you what kind of work is expected:
   - **research** → gather information, explore options
   - **design** → make architectural decisions
   - **plan** → break work into tasks
   - **implement** → write code, guided by research/plans
   - **review** → validate against plans
   - **archive** → wrap up
5. Read existing artifacts with `wai search "<topic>"` before starting new work.

## Capturing Work

Record the reasoning behind your work, not just the output:

```bash
wai add research "findings"         # What you learned, trade-offs
wai add plan "approach"             # How you'll implement, why
wai add design "decisions"          # Architecture choices, rationale
wai add research --file notes.md    # Import longer content
```

Use `--project <name>` if multiple projects exist. Otherwise wai picks the first one.

Phases are a guide, not a gate. Use `wai phase show` / `wai phase next`.

## Tracking Work Across Tools

When beads and openspec are both active, keep them in sync:
- When creating a beads ticket for an openspec task, include the task
  reference in the description (format: `<change-id>:<phase>.<task>`,
  e.g. `add-why-command:7.1`)
- When closing a beads ticket linked to a task, also check the box
  (`[x]`) in the change's `tasks.md`

## Ending a Session

Before saying "done", run this checklist:

```
[ ] wai handoff create <project>   # capture context for next session
[ ] bd close <id>                  # close completed issues; also close parent epic if last sub-task
[ ] bd sync --from-main            # pull beads updates
[ ] openspec tasks.md — mark completed tasks [x]
[ ] openspec list — archive any ✓ Complete changes (`openspec archive <id> --yes`)
[ ] wai reflect                    # update CLAUDE.md with project patterns (every ~5 sessions)
[ ] git add <files> && git commit  # commit code + handoff
```

### Autonomous Loop

One task per session. The resume loop:

1. `wai prime` — orient (shows ⚡ RESUMING if mid-task)
2. Work on the single task
3. `wai close` — capture state (run this before every `/clear`)
4. `git add <files> && git commit`
5. `/clear` — fresh context

→ Next session: `wai prime` shows RESUMING with exact next steps.

When context reaches ~40%: run `wai close`, then `/clear`.
Do NOT skip `wai close` — it enables resume detection.

## Quick Reference

### wai
```bash
wai status                    # Project status and next steps
wai add research "notes"      # Add research artifact
wai add plan "plan"           # Add plan artifact
wai add design "design"       # Add design artifact
wai add skill <name>          # Scaffold a new agent skill
wai search "query"            # Search across artifacts
wai search --tag <tag>        # Filter by tag (repeatable)
wai search --latest           # Most recent match only
wai why "why use TOML?"       # Ask why (LLM-powered oracle)
wai why src/config.rs         # Explain a file's history
wai reflect                   # Synthesize project patterns into CLAUDE.md
wai close                     # Session handoff + pending-resume signal
wai phase show                # Current phase
wai doctor                    # Workspace health
wai pipeline list             # List pipelines
wai pipeline run <n> --topic=<t>  # Start a run; set WAI_PIPELINE_RUN=<id>
wai pipeline advance <run-id> # Mark stage done, get next hint
```

### beads
```bash
bd ready                     # Available work
bd show <id>                 # Issue details
bd create --title="..."      # New issue
bd update <id> --status=in_progress
bd close <id>                # Complete work
```

### openspec
Read `openspec/AGENTS.md` for full instructions.
```bash
openspec list              # Active changes
openspec list --specs      # Capabilities
```

## Structure

The `.wai/` directory organizes artifacts using the PARA method:
- **projects/** — active work with phase tracking and dated artifacts
- **areas/** — ongoing responsibilities (no end date)
- **resources/** — reference material, agent configs, templates
- **archives/** — completed or inactive items

Do not edit `.wai/config.toml` directly. Use `wai` commands instead.

Keep this managed block so `wai init` can refresh the instructions.

<!-- WAI:END -->

<!-- WAI:REFLECT:REF:START -->
## Accumulated Project Patterns

Project-specific conventions, gotchas, and architecture notes live in
`.wai/resources/reflections/`. Run `wai search "<topic>"` to retrieve relevant
context before starting research or creating tickets.

> **Before research or ticket creation**: always run `wai search "<topic>"` to
> check for known patterns. Do not rediscover what is already documented.
<!-- WAI:REFLECT:REF:END -->

