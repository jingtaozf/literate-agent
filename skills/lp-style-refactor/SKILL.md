---
name: lp-style-refactor
description: |
  Audit and refactor a literate-programming .org file under `lp/<sub>/` so a
  senior engineer with no domain background can read it end-to-end.
  Use this skill whenever the user asks to "improve LP style", "review this
  org file", "make it readable", "refactor for literate programming",
  "the docs are stale", "this .org is too dense", or mentions any specific
  file under `lp/`. Also use proactively after `/lp-resync` brings in upstream
  code changes — LP narrative drift is the likely follow-up. The skill enforces
  a one-iteration contract (one small improvement + one small cleanup, then
  commit + push), so it is safe to wire into a cron for batch readability work.
---

## What this skill does

> *Origin*: edo-literate. The skill is shaped to edo's
> `lp/<sub>/` multi-submodule layout and its `scripts/audit_lp.py`.
> Adapt the script paths when porting to another LP project.

ONE iteration of: audit → pick 1 high-impact improvement + 1 cleanup → apply
the edits to the `.org` → verify byte-equivalent tangle (or green tests if
code changed) → commit. Each invocation is intentionally SMALL (≤ ~120 net
LP lines, ≤ 1 commit per repo).

For batch readability work (e.g. 10 iterations), the user wires this skill
into a cron via `CronCreate` and the per-iteration contract here keeps each
firing self-bounded. See § "Cron-mode notes" at the bottom.

## Prerequisites

- Meta-repo is `edo-literate`. You are on branch `jt` in both meta-repo and
  any touched submodule. CWD does not matter — paths in this skill are absolute.
- `make tangle FILE=<lp/sub/file.org>` works for the target file.
- `python3` is on PATH.

## Workflow

### Step 1 — Audit (≤ 30s, scripted, no LLM)

```bash
python3 .claude/skills/lp-style-refactor/scripts/audit_lp.py lp/<sub>/<file>.org
```

The script emits a markdown report listing concrete findings:

- Heading depth violations (> 5)
- Grab-bag section names (`Functions`, `Helpers`, `Misc`, …)
- Src-blocks > 80 lines without noweb (candidates for noweb-split)
- Functions ≥ 40 LOC without NL outline (`# # one-sentence` comments)
- Bare cross-file mentions (`=other.org=`) that should be `[[file:...][...]]`
- Sections referenced ≥ 2 times without a stable `:CUSTOM_ID:` anchor
- AI-PROVENANCE blocks with `Date range` ending > 6 months ago
- Likely prose↔docstring duplication (same paragraph in both)

The report is the input for Step 2. If it is completely empty: you may STOP —
the file is in good shape.

### Step 2 — Triage (judgment, single pass)

Read the report. Pick exactly **one** improvement and **one** cleanup, in this
preference order (cheap+high-impact first):

| Priority | Improvement category                                          |
|---------:|---------------------------------------------------------------|
| 1        | Bare cross-file ref → org link `[[file:x.org::*Y][text]]`     |
| 2        | Undefined jargon → 2–5 sentence plain-English definition      |
| 3        | Function ≥ 40 LOC → add `# # one-sentence` NL outline         |
| 4        | Referenced-section without anchor → add `:CUSTOM_ID:` + link  |
| 5        | Big class (> 80 lines) → noweb-split (see noweb-split-template) |
| 6        | Hub section without "See also" footer → add bullet-link list  |
| 7        | Misleading / outdated table or ASCII diagram → fix            |

| Priority | Cleanup category                                              |
|---------:|---------------------------------------------------------------|
| 1        | Replace bare text mention with org link (combines with #1 above) |
| 2        | Drop docstring sentence that LP prose now duplicates          |
| 3        | Drop stale AI-PROVENANCE block (date > 6mo + no recent pivots)|
| 4        | Drop resolved TODO / FIXME / "deferred 2026-X" comments       |
| 5        | Drop redundant blank lines / wrong comments                   |
| 6        | Drop unused imports (`ruff check --select F401`)              |

Read `references/lp-rubric.md` for the full criteria with "good vs bad"
examples. Read `references/worked-example.md` to see one validator.org
iteration end-to-end.

### Step 3 — Apply (Edit ops)

Make the change to the `.org` file. **Never** edit the tangled `.py` directly
(repo PreToolUse hook rejects it). For noweb-split, follow
`references/noweb-split-template.md` strictly — getting the skeleton
indent wrong breaks tangle byte-equivalence.

Keep diffs surgical. Do not reformat unrelated lines.

### Step 4 — Verify (scripted)

```bash
bash .claude/skills/lp-style-refactor/scripts/verify_tangle.sh lp/<sub>/<file>.org
```

The script:

1. `make tangle FILE=<file>` from meta-repo root
2. `git -C repos/<sub> diff --stat` — must be empty for prose-only edits
3. If code did change: prints the substantive non-blank line count per file
   so you can confirm intent. Does NOT auto-run tests (you decide which
   subset).

If the diff has unintended files, STOP. The change leaked. Either:

- Edit again to keep prose-only, OR
- Accept the code change as deliberate and run the submodule's test gate
  (`cd repos/<sub> && source .env && uv run pytest -m "not llm and not slow"`)
  before committing.

### Step 5 — Commit

**Pre-commit index check (mandatory — protects against concurrent-agent race)**

Before staging anything, snapshot the existing index in both the
submodule and the meta-repo. A concurrent agent (cron, sibling parallel
iter, even your previous step) may have left files staged but
un-committed; if you `git add` your own paths now, `git commit` would
silently include theirs.

```bash
# In the submodule:
cd repos/<sub>
git diff --cached --name-only > /tmp/preexisting-staged-<sub>.txt
# In the meta-repo:
cd <meta-repo>
git diff --cached --name-only > /tmp/preexisting-staged-meta.txt
```

If either file is **non-empty**, STOP. Either:

- Unstage the foreign paths (`git restore --staged <path>`) and proceed
  knowing they will be picked up by their owning agent, OR
- Wait 30s and retry (the other agent is likely about to commit), OR
- Report "skipped — index race with another agent on <list of paths>"
  and exit.

Do NOT commit through a pre-existing-staged index without first
restoring it.

**Then proceed with one of two cases.**

**Case A: prose-only (submodule diff empty)**

```bash
cd <meta-repo>
git add lp/<sub>/<file>.org
git diff --cached --name-only           # MUST list only your file(s)
git commit -m "lp(<sub>): <short improvement description>"
git push
```

**Case B: code changed (submodule has diffs)**

Submodule first (so meta-repo pointer is bumpable):

```bash
cd repos/<sub>
git add <specific files>                 # NEVER `git add -A`
git diff --cached --name-only            # MUST list only your file(s)
git commit -m "chore(lp): <reason> (<short>)"
git push
```

Meta-repo second:

```bash
cd <meta-repo>
git add lp/<sub>/<file>.org repos/<sub>
git diff --cached --name-only            # MUST list only your file(s)
git commit -m "lp(<sub>): <short improvement description>"
git push
```

The `git diff --cached --name-only` line is the final guard. If it
lists anything you don't recognize as yours, abort the commit with
`git reset HEAD` and go back to the pre-commit index check.

For 10-iter batch use, format the meta subject as
`lp(<sub>): readability iter N/10 — <short>` so the counter at Step 1
of the next invocation can read git log to know which iter to run.

Stage only the files you touched. **Never** `git add -A`. Per repo
rules in `.claude/rules/no-auto-commit.md` and per the meta-repo's
pointer-bump discipline, unrelated drift must stay unstaged.

#### Race incident — why this check matters

In one parallel-13-agent run, an agent for `skill-enhance-server`
staged its `lp/skill-enhance-server/tests.org` while another agent for
`mega-code/tests.org` had ALREADY left `lp/mega-code/tests.org`
staged but un-committed. The first agent's `git commit` swept up both
files, producing a commit whose subject was about skill-enhance-server
but whose diff included an unrelated mega-code change. No corruption —
the changes were both intended — but the commit was hard to bisect and
the second agent's report ended with "my commit landed in someone
else's commit, please figure out which". The Step 5 pre-check above
makes this race visible before staging instead of after.

### Step 6 — Exit cleanly

Do NOT chain more iterations. Do NOT schedule additional work. If the user
wanted a batch, they wired a cron — that fires the skill again.

## Cron-mode notes

When the cron prompt asks for 10 iterations, this skill self-bounds via the
git-log counter:

```bash
N=$(git log --oneline jt | grep -c "lp(<sub>): readability iter")
```

If `N >= 10`, run `CronList` → `CronDelete <id>` for the matching job, then
exit without changes.

## Hard constraints

- ≤ ~120 net LP lines per iteration. Anything bigger → split across iters.
- Never reformat unrelated lines.
- Never commit unrelated drift in `lp/<other-sub>/*` or other submodule
  pointers. Per the meta-repo's `lp-resync` discipline.
- Never push to `main` of any repo.
- Never delete `.cache/` directories or passing tests.

## Anti-patterns (read this before editing)

- **Don't add prose that says WHAT the code does.** The code already shows
  that. Prose should say WHY the code is shaped this way, or define jargon.
- **Don't introduce new abbreviations without defining them.**
- **Don't noweb-split a class < 80 lines.** The skeleton overhead exceeds
  the readability gain at small sizes.
- **Don't trim AI-PROVENANCE blocks aggressively** — they're cheap blame
  trail; only drop when clearly stale per the audit rule.
- **Don't `git add -A`.** Stage by explicit path.
- **Don't generate "improvements" the audit didn't flag.** The audit is the
  spec; if nothing is flagged AND prose reads well, stop.

## Why this skill exists

LP value is realized only when a fresh reader can read the `.org` end-to-end
and follow the WHY without reading the code. Drift between prose and code is
the failure mode — fixed by audit + small iterations, not by big-bang
rewrites. The repo already has rules covering the *what* of good LP
(`.claude/rules/literate-programming-document-first.md`,
`lp-module-section-hierarchy.md`, `lp-noweb-for-big-blocks.md`,
`tests-embedded-in-narrative.md`). This skill enforces the *how* of
incrementally moving an existing file toward those rules.

References:

- Knuth's "psychological order" principle (the `.org` is read top-to-bottom
  by humans even though `make tangle` reorders chunks for the compiler).
- Shi et al., "Natural Language Outlines for Code", FSE 2025 — the source
  of the 40-LOC threshold and 4–5-statement guidance.
- Anthropic skill design: pushy descriptions, progressive disclosure,
  bundle-scripts-for-repeated-work.
