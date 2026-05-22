# Risk → Autonomy Level Map

Adapted from Lens #12 (pair-programming protocol) of the AI-codebase-mastery
research. The 4-level autonomy spectrum is industry consensus:

- **L1 — Inline accept.** Token-by-token autocomplete (Copilot inline). N/A
  here; we don't use inline AI.
- **L2 — Supervised, every step.** Agent proposes; human approves before
  any tool call executes. Used for high-risk surfaces.
- **L3 — Supervised + verification-first.** Agent acts, but every change
  passes through `make check-*` and human review before commit.
- **L4 — Fire-and-review.** Agent can land changes; human reviews the
  aggregated diff afterwards.

The table below assigns a level to each path in this repo. Solo project,
yes — the table is still useful because the *agent* needs the level
even when there's only one human watching.

## Table

| Path / change                                                  | Level | Rationale |
|----------------------------------------------------------------|-------|-----------|
| `literate_python/loader.py` (hot-reload, `sys.meta_path`)       | L3    | Touches Python's import system; subtle bugs surface only on reload |
| `literate_python/server.py` (Flask handler, `server_locals`)    | L3    | Cross-request state; race-prone |
| `literate_python/reloader.py`                                    | L3    | Updates dependent modules in-place; mistake corrupts running session |
| `literate_python/sections.py` (clustering)                       | L4    | Pure-ish; well-tested; no shared state |
| `literate_python/inspector.py` (multimethod dispatch)            | L4    | Pure functions |
| `literate_python/tests/`                                          | L4    | Tests; failures self-evident |
| `literate-org.org` — prose only (Verified-by, comments, NL outline) | L4    | No code change |
| `literate-org.org` — Python src blocks                            | L3    | Tangle output goes to running modules; verification via `make check-*` mandatory before commit |
| `literate-org.org` — elisp src blocks                             | L3    | `literate-elisp-load` picks up new defs at next reload; can break user's editor |
| `literate-org.org` — heading promotion / demotion / restructure   | L3    | INDEX, TOC, anchor drift; depth lint may fire |
| `.claude/rules/*.md`                                              | L3    | Rules constrain *future* agent behavior; review carefully |
| `.claude/hooks/*.sh`                                              | **L2** | Hook misbehavior breaks the entire dev loop. Manual approval before running |
| `.claude/settings.local.json`                                    | **L2** | Hook registration; one wrong matcher and tooling stops |
| `.pre-commit-config.yaml`                                         | L3    | CI gate; misconfiguration silently lets bad commits through |
| `scripts/*.py` (lint scripts)                                    | L4    | Self-contained; tested per run via the lint itself |
| `Makefile`                                                        | L4    | Surface-only; failures visible immediately |
| `pyproject.toml`, `poetry.lock`                                  | **L2** | New dependency = supply-chain risk (Lens #2 — slopsquatting). Manual approval and metadata check |
| `AGENTS.md` / `CLAUDE.md` (symlink)                              | L4    | Prose only |
| `ARCHITECTURE.org`                                                | L4    | Prose only |
| `tasks/lessons.md` entries                                        | L4    | Append-only log |
| `README.org` / `INDEX.org`                                       | L4    | Surface / generated |

## Forced level changes

Some PRs *cross* boundaries. The strictest level wins:

- A PR that touches `literate_python/loader.py` AND `Makefile` runs at L3.
- A PR that adds a new dependency in `pyproject.toml` runs at L2 — even if
  the rest is trivial.
- A PR that adds elisp inside `literate-org.org` runs at L3.

## What "verification-first" means at L3

Before commit, the agent runs (and the human checks):

```bash
make check-structure
make check-nl-outline
poetry run pytest literate_python/tests/
```

If the change is to elisp, also reload in the host Emacs:
`(literate-elisp-load "literate-org.org")` and verify a smoke-test
function still resolves.

If the change is to a hook script (`.claude/hooks/*.sh`), the agent
must manually exercise it with a synthetic JSON payload before
committing — the dev loop depends on these.

## What "supervised every step" means at L2

Agent proposes a tool call (Bash, Edit, Write); human approves *before*
it executes. Claude Code's default permission system already supports
this via per-tool gating; L2 paths should never be in the auto-approve
allowlist of `.claude/settings.local.json`.

## When to revisit

This table is opinion calibrated to current state (solo project, current
architecture). Revisit when:

- New module is added — assign a level explicitly, don't default.
- New collaborator joins — L4 might tighten to L3 across the board.
- Hot-reload semantics or Flask server is replaced — recalibrate `L3`
  rows that were "subtle bugs only show at runtime".
- A specific path causes a real incident — promote one level, write a
  `tasks/lessons.md` entry explaining why.
