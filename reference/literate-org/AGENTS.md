# AGENTS.md

(Anthropic's Claude Code reads this file via the symlink `CLAUDE.md`.)

literate-org is a literate-programming runtime for Python: code lives in
`literate-org.org`; tangling produces `literate_python/*.py`; `import`
works on either via the custom `LiterateImporter`. Optional Flask server
(`make server`) supports live exec + cross-module hot reload.

## Where to look

- **Source of truth:** `literate-org.org` (~3300 lines, both Python and Emacs Lisp).
- **Architecture / invariants:** `ARCHITECTURE.org` — invariant ledger, trust boundaries, "looks refactorable but isn't".
- **Module map:** `INDEX.org` lists every `:LITERATE_ORG_MODULE:` → tangle path.
- **Rules** (read once, agent obeys without re-prompting):
  - `.claude/rules/literate-org-document-first.md` — LP discipline, depth ≤ 5 guardrail, NL outlines, prose-before-src.
  - `.claude/rules/tests-embedded-in-narrative.md` — tests live next to the code; "Verified by:" cross-refs for legacy.
  - `.claude/rules/code-quality-over-feature.md` — Simplicity-First, errors propagate.
  - `.claude/rules/no-auto-commit.md` — never `git commit`/`push` without explicit ask.
  - `.claude/rules/autonomy-levels.md` — risk→L2/L3/L4 table per file path.
- **Lessons loop:** `tasks/lessons.md` — every user correction adds an entry; ≥ 3 of one kind promotes to a rule.

## Build / lint / tangle

```bash
make tangle FILE=literate-org.org   # batch tangle (host-Emacs path is preferred; this is the fallback)
make check-structure                # depth ≤ 5, no grab-bag headings, prose before src
make check-nl-outline               # functions ≥ 40 lines need '# # ' partition comments
make index                          # regenerate INDEX.org
make lint                           # black + flake8 on tangled .py
poetry run pytest literate_python/tests/
make server                         # Flask on $LITERATE_PYTHON_HOST:$LITERATE_PYTHON_PORT (127.0.0.1:7330)
```

## Auto-tangle lifecycle (DO NOT bypass without reason)

`.org` edits trigger tangle automatically via two paths that both end at
`literate-org-tangle-buffer` (whole-buffer `org-babel-tangle` + Black):

1. PostToolUse hook on `Edit/Write/MultiEdit` → `emacsclient` → `literate-org-tangle-by-path`; falls back to `make tangle FILE=…` if host Emacs is down.
2. Saving the buffer in Emacs (`C-x C-s`) → `literate-org-mode` after-save-hook.

**IMPORTANT:** you do not need to call `make tangle` yourself unless the hook reports failure. Set `LITERATE_ORG_NO_AUTO_TANGLE=1` to bypass for bulk patches.

## NEVER

- **NEVER** edit `literate_python/*.py` directly — PreToolUse hook rejects it; the file is tangle output. Edit the org section.
- **NEVER** add `Co-Authored-By:` lines to commits.
- **NEVER** use relative imports in Python.
- **NEVER** commit `.env` files or write secrets in source.
- **NEVER** delete files in `.cache/`.
- **NEVER** add a bare `except Exception` — catch the specific type or let it propagate.
- **NEVER** open a new section in `literate-org.org` with `#+begin_src` directly; prose preamble first.

## ALWAYS

- **ALWAYS** edit `literate-org.org` for code changes; auto-tangle keeps `.py` in sync.
- **ALWAYS** add a prose paragraph above any new `#+begin_src` block (see `literate-org-document-first.md`).
- **ALWAYS** name a section by the *concept*, not the phase (no `Functions/Helpers/Utilities/Misc`).
- **ALWAYS** confirm a non-trivial design before implementing.
- **ALWAYS** record a user correction in `tasks/lessons.md` before continuing.

## Environment

- `LITERATE_PYTHON_HOST` (default `127.0.0.1`)
- `LITERATE_PYTHON_PORT` (default `7330`)
- `LITERATE_ORG_NO_AUTO_TANGLE=1` bypasses the post-edit tangle hook
