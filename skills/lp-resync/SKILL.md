---
name: lp-resync
description: Sync a project's upstream source state back into the LP layer's `.org` files. Use when the user asks to "sync from upstream", "pull latest back to LP", "merge origin/main into LP", "new docs/code, fold into lp", or "resync all submodules". The skill handles three independent surfaces — code drift (source files that upstream changed), new files (paths upstream added that LP doesn't yet cover), and doc changes (added/modified files under the project's `docs/` tree) — each routed through its own triage path under human oversight. Generalised from the original <meta-repo> `lp-resync` skill; works for any project whose source root is configured via `LITERATE_AGENT_TANGLED_ROOTS` and LP root via `LITERATE_AGENT_LP_ROOT`.
---

# LP Resync

This skill walks an agent through *re-syncing* a project's upstream
state into the LP layer. Three surfaces are processed independently:

1. **Code drift** — files upstream edited that the corresponding
   `<LP_ROOT>/<sub>/<x>.org` tangle target now disagrees with.
2. **New files** — paths upstream added that no LP section covers.
3. **Doc changes** — files under `<TANGLED_ROOT>/<sub>/docs/` that
   upstream added or modified.

Each surface has its own triage path; the surfaces are evaluated in
order, with human checkpoints between.

## Project conventions consumed

The skill is project-agnostic via `LITERATE_AGENT_*` env vars (set
per-project in `.claude/hooks/_env.sh`):

| Env var | Default | Role |
|---------|---------|------|
| `LITERATE_AGENT_LP_ROOT` | `lp` | where the `.org` source-of-truth files live (relative to repo root) |
| `LITERATE_AGENT_TANGLED_ROOTS` | (empty) | one or more prefixes (comma-sep) where tangled source lives (e.g. `repos/`, `src/`) |
| `LITERATE_AGENT_DEFAULT_BRANCH` | `main` | which branch the LP author works on; merges target this |
| `LITERATE_AGENT_TANGLE_MAKE_TARGET` | `tangle` | which `make` target rebuilds tangle output |

A project missing any of these falls back to default; if defaults
do not match the project's actual layout, the project's `_env.sh`
must override before running this skill.

## Triggers

User says any of:

- "sync from upstream"
- "pull latest back to LP"
- "merge origin/main into LP"
- "resync <sub>"
- "resync all submodules" (batch — runs the single-target workflow
  once per submodule, alphabetically)

## Inputs

- **Required**: a target name — either a single submodule directory
  under `<TANGLED_ROOT>` or the literal "all" for batch mode.
- **Optional**: `--merge-strategy` one of `ff-only` (default) /
  `rebase` / `merge`. If `ff-only` fails the skill STOPS and asks.
- **Optional**: `--resync-strategy` one of `engine` (default — the
  3-pass `lp_sync_engine.py` flow that preserves prose) / `reimport`
  (fast, lossy: Phase-C wholesale re-imports each drifted `.org` via
  `literate-org-import`, skipping the per-def diff. Prose inside
  re-imported sections is LOST. See `Phase-C′` below for the
  trade-offs and the PIN safety check).

## Hard rules

1. **Working branch discipline preserved.** All work happens on the
   project's configured branch (`LITERATE_AGENT_DEFAULT_BRANCH`).
   Never silently switch branches.

2. **Submodule push only when needed.** After `ff-merge origin/<default-branch>`,
   if the local branch SHA now equals upstream (no independent
   commits), there's nothing to push — meta-repo's pointer bump
   alone is enough. If the branch has independent commits AND we
   backfilled prose during this resync, push only AFTER confirming
   the new content tangles byte-equivalent to the working tree.

3. **`.org` is the source of truth.** When a source file and the
   matching `.org` src block have both diverged independently, the
   `.org` wins by default — but the conflict is *reported*, not
   silently resolved, and a severe divergence (anything beyond
   cosmetic whitespace) STOPS for user judgment.

4. **Upstream `docs/` left untouched.** The submodule's history is
   the submodule's concern. LP doc changes are routed via Phase E.

5. **Tangle round-trip must end byte-equivalent.** A resync that
   leaves `git -C <repo> diff --stat` non-empty (excluding the merge
   itself) is incomplete. Either finish the backfill or STOP.

6. **Metadata schema kept consistent.** Per `rules/lp-resync-metadata.md`
   + `rules/lp-resync-noweb-discipline.md`, the `LITERATE_ORG_SOURCE_SHA`
   stamp + `:LITERATE_ORG_BLOCK_KIND:` + `:LITERATE_ORG_CONTAINS_DEFS:`
   must end the resync in a consistent state. The audit script
   (`audit_lp_sync_metadata.py`) verifies this at Phase F.

## Phase-A: pre-flight

```bash
# Must be clean on the configured branch
git -C <TANGLED_ROOT>/<sub> branch --show-current   # must == $LITERATE_AGENT_DEFAULT_BRANCH
git -C <TANGLED_ROOT>/<sub> diff --quiet            # must succeed (clean)
git -C <TANGLED_ROOT>/<sub> diff --cached --quiet   # must succeed

# Metadata pre-flight (NEW in v4): every .org under LP_ROOT/<sub>/
# must have LITERATE_ORG_SOURCE_SHA stamped
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/audit_lp_sync_metadata.py \
    <LP_ROOT>/<sub>/ --check-presence
```

If any of these fail, STOP. Surface the state and ask the user
what to do.

Bootstrap path for missing SHA (legacy `.org`):

```bash
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/lp_sync_bootstrap.py \
    --all <LP_ROOT>/<sub>/
```

## Phase-B: merge upstream

```bash
git -C <TANGLED_ROOT>/<sub> fetch origin
git -C <TANGLED_ROOT>/<sub> merge --ff-only origin/${LITERATE_AGENT_DEFAULT_BRANCH:-main}
```

Three outcomes:

- **No-op** ("Already up to date") — local already at or past
  upstream. Skip to Phase-D (still process any local LP drift).
- **Fast-forward** — local was behind, now updated. Capture the
  delta `HEAD@{1}..HEAD` for Phase-C/E classification.
- **Non-fast-forward** — independent commits on both sides. STOP,
  surface the divergence, ask rebase vs merge.

## Phase-C: code-drift triage (NEW automated path)

The NEW v4 path uses `scripts/lp_sync_engine.py` to handle most
cases automatically. Falls back to STOP-and-ask only for ambiguous
or high-risk changes.

```bash
# Run the sync engine over every .org for this submodule
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/lp_sync_engine.py \
    --lp-root <LP_ROOT>/<sub>/ \
    --source-repo <TANGLED_ROOT>/<sub>/ \
    --dry-run
```

The engine's 3-pass output is classified as:

| Outcome | Action |
|---------|--------|
| Pass A modify (source body changed, block exists) | Auto-apply on next non-dry run; prose unchanged |
| Pass B add (source has new def, no block) | Insert new heading + src block at sensible parent section; tag `:LITERATE_ORG_GENERATED: pass-b-add:`; HUMAN REVIEWS the chosen location |
| Pass C stale (source removed def, block exists) | Add `:STALE: <date> last-seen-at <old-sha>:`; never auto-delete; HUMAN REVIEWS |
| Tangle round-trip fails after apply | STOP, surface diff, treat as algorithm bug |

Apply (after dry-run review):

```bash
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/lp_sync_engine.py \
    --lp-root <LP_ROOT>/<sub>/ \
    --source-repo <TANGLED_ROOT>/<sub>/
```

### Legacy STOP cases (fall-back when engine can't auto-resolve)

Per file that the engine could not handle automatically, classify:

| Pattern | Action |
|---------|--------|
| Single-blank-line shifts (PEP-8 / prettier whitespace) | LET TANGLE WIN — these are cosmetic |
| Inline trailing comment moved (e.g. `# type: ignore`) | Hand-patch the .org — known literate-org-import limitation for trailing comments |
| File deleted upstream | Surface — the .org block is now orphan. Pass C tags `:STALE:`. Ask whether to remove or keep with `:tangle no` as historical |
| File renamed upstream | Surface — the .org's `:tangle` path is now invalid. Ask whether to update the path or split/merge sections |
| Block conflict (.org pinned via `:LITERATE_ORG_PIN: yes:`) | Engine skipped; surface for human review of whether to un-pin |

The decision-point at "engine could not auto-resolve" is the most
common stopping point. Don't push past it autonomously.

## Phase-C′: reimport mode (opt-in, lossy)

Enabled only when the user passes `--resync-strategy=reimport`. This
mode replaces Phase-C *entirely* — the `lp_sync_engine.py` 3-pass
flow is skipped. Phase-D / E / F / G still run unchanged.

### When to use

Large mechanical upstream sweeps — formatter runs, auto-refactors,
dependency bumps that touch many files, whole-module tool rewrites.
There the per-def diff the engine produces is expensive for the
agent to triage (dry-run → classify → apply → STOP-case handling,
multiple LLM round-trips per file) AND the prose is already stale
across the swept area, so preserving it has little value.

NOT for surgical single-def changes — there the engine's Pass-A
in-place body replacement is cheaper AND preserves prose.

### Lossy trade-offs (the cost of the fast path)

The user passing `--resync-strategy=reimport` accepts these. Surface
them in the PR description when committing.

| Lost | Consequence |
|------|-------------|
| per-section design rationale prose | reader must reverse-engineer intent from code |
| `:CUSTOM_ID:` anchors on code sections | `[[file:x.org::#anchor]]` cross-refs from other `.org` may break silently |
| noweb-restructure skeletons | `literate-org-import-noweb-split` (default `t`) re-derives structure; may not match prior manual shape |
| `:LITERATE_ORG_EXCLUDED_DEFS` opt-outs | excluded defs come back; must be re-removed by hand |

### Procedure

1. **Compute drift set** (cheap; no content diff):

   ```bash
   git -C <TANGLED_ROOT>/<sub> rev-parse HEAD              # current upstream tip
   # For each .org under <LP_ROOT>/<sub>/:
   #   if its LITERATE_ORG_SOURCE_SHA != HEAD ⇒ drifted
   # Equivalently — list :tangle target files changed SHA..HEAD:
   git -C <TANGLED_ROOT>/<sub> diff --name-only <SHA>..HEAD
   ```

2. **PIN safety check** (hard refusal — do NOT bypass). For each
   drifted `.org`, grep for `:LITERATE_ORG_PIN: yes`. Any hit →
   **STOP**. Tell the user which block is pinned and ask them to
   either manually unpin or fall back to `--resync-strategy=engine`.
   The engine's PIN safety valve exists exactly for this case;
   reimport mode does not get to override it.

3. **Per drifted `.org`:**

   a. **Set the language** (CRITICAL — prevents Emacs minibuffer
      hang). If the `.org` header lacks
      `#+PROPERTY: LITERATE_ORG_LANGUAGE <lang>`, Edit it in
      (derive from the `:tangle` path suffix: `.py`→`python`,
      `.ts`→`typescript`, `.rs`→`rust`, `.el`→`emacs-lisp`). Use
      the plural `LITERATE_ORG_LANGUAGES` (space-separated) if the
      file mixes languages. Without this, `literate-org-import-file`
      falls back to `(read-from-minibuffer "Which language: ")` and
      freezes single-threaded Emacs — the same hazard
      `skills/lp-import/SKILL.md` warns about.

   b. **Preserve the prose preamble.** Keep everything from BOF
      through the last prose-only line before the first
      `#+begin_src`-bearing section (covers `#+PROPERTY:` lines,
      `* Overview`, `* Public API`, and any leading prose-only
      sections). Delete the rest — the per-def code sections that
      `literate-org-import` is about to regenerate.

   c. **Call import** (precedent: `hooks/tangle-org-buffer.sh`,
      `skills/lp-import/SKILL.md`):

      ```bash
      emacsclient -e '(with-current-buffer (find-file-noselect "<LP_ROOT>/<sub>/<x>.org>")
                        (goto-char (point-max))
                        (literate-org-import :module-name "<pkg.mod>"
                                             :module-path "<abs/path/to/source.py>")
                        (save-buffer))'
      ```

      `literate-org-import` *appends*; step (b) cleared the old
      per-def sections so there is no duplication. It dispatches to
      `literate-org-import-file` for a single source path or
      `literate-org-import-directory` for a directory walk.

   d. **Fix the tangle path** (open risk carried over from
      `skills/lp-import/SKILL.md`). The drawer's
      `:header-args: :tangle` may be written as absolute. Confirm
      each new section's tangle path is *relative to the `.org`
      file* (e.g. `../../repos/<sub>/<pkg>/<mod>.py`). Rewrite if
      not — an absolute path breaks byte-equivalence and the
      `.cache/tangle-map.tsv` reverse map.

   e. **Re-stamp metadata:**

      ```bash
      python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/lp_metadata_refresh.py <LP_ROOT>/<sub>/<x>.org
      # Then bump the file-level LITERATE_ORG_SOURCE_SHA / SHA_DATE
      # to current upstream HEAD (bootstrap does this if refresh
      # alone doesn't):
      python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/lp_sync_bootstrap.py <LP_ROOT>/<sub>/<x>.org
      ```

4. **Pass-C stale does not apply.** Reimport is wholesale per-file;
   a def removed upstream simply won't appear in the regenerated
   sections (implicit delete). Do NOT run the engine's `:STALE:`
   tagging pass — it has nothing to operate on after reimport.
   Surface any "def disappeared" surprises at Phase-F if the
   tangle round-trip fails to match upstream.

Phase-F (verify) is unchanged and remains the safety net: a
non-empty `git diff --stat` after tangle means import wrote
something that doesn't round-trip — STOP, treat as a procedure bug.

## Phase-D: new-file triage

```bash
# Files in the submodule but not claimed by any .org's :tangle header
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/build_tangle_map.py  # refresh cache
# Then compare against current source tree:
comm -23 <(find <TANGLED_ROOT>/<sub> -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.rs' | sort) \
         <(awk -v sub="<TANGLED_ROOT>/<sub>" '$1 ~ "^"sub {print $1}' .cache/tangle-map.tsv | sort)
```

Heuristic auto-routing:

- New file in a directory already covered by an `.org` → add a
  section with `:tangle` header pointing at the new file. **Always
  use `literate-org-import`** — never a hand-authored single-block
  import, regardless of how small the file is. There is no
  "small enough to paste" threshold: even a 10-line file goes
  through the tool, which emits the canonical per-definition shape
  with the `:header-args: :tangle` drawer. A hand-written single
  block reproduces the exact two defects `warn-oversized-atomic-src.sh`
  exists to catch (oversized atomic block + inline `:tangle`). See
  the `lp-import` skill for the invocation.
- New file in a *brand-new directory* → STOP and ask:
  - Create a new `<LP_ROOT>/<sub>/<new-name>.org` (use
    `templates/new-module.org` as template).
  - Fold into an existing `.org` despite the new directory.
  - Skip — leave the file un-LP-managed for now (test fixtures,
    generated code, vendored deps).
- Test files / fixtures / generated code: STOP and ask — common
  skips.

Always report new-file decisions as a table before importing.

## Phase-E: doc-changes triage

For each modified or added doc under `<TANGLED_ROOT>/<sub>/docs/`,
apply the 4-bucket classifier:

| Bucket | Test | Action |
|--------|------|--------|
| **narrow inline** | Describes one current module/class | Augment / replace the inline prose in the owning `.org` section |
| **cross-cutting** | Describes wiring across multiple modules | Augment `<LP_ROOT>/<sub>/_project.org` |
| **reference** | Defines vocabulary or schemas the code uses | Augment `_project.org` § Glossary (or `_glossary.org` if reused widely) |
| **SKIP** | Historical, process, proposal, retro, sprint plan, link-only | Drop |

Deleted docs: report — usually means the corresponding `.org`
prose is now also stale. Ask whether to trim.

For partial-import (some sections of a doc kept, others dropped),
align with code, drop the rest, optionally mark `[STALE]` in a
comment.

## Phase-F: verify

```bash
# Tangle round-trip
make ${LITERATE_AGENT_TANGLE_MAKE_TARGET:-tangle}
git -C <TANGLED_ROOT>/<sub> diff --stat     # MUST be empty

# Metadata consistency
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/audit_lp_sync_metadata.py \
    <LP_ROOT>/<sub>/ --check-all

# Structure + index
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/check_org_structure.py
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/build_tangle_map.py
python3 ${LITERATE_AGENT_PLUGIN_ROOT}/scripts/build_index.py
```

A non-empty diff means Phase-C / D / E left work undone. Either
finish or STOP. A metadata audit failure means the sync engine
violated an invariant — bug; report.

## Phase-G: commit + push

Same scout-pattern:

1. **Submodule commit** — only if local branch now has commits that
   don't exist upstream AND those commits' content is what we want
   upstream to see. After a pure `ff-merge` with no LP-side
   backfill, skip this step.
2. **Submodule push** — only when there's a submodule commit.
3. **Meta-repo commit** — `<LP_ROOT>/<sub>/*.org` changes +
   `<TANGLED_ROOT>/<sub>` pointer bump + regenerated `INDEX.org`
   + `.cache/tangle-map.tsv` if the map changed.
4. **Meta-repo push**.

User must approve commit + push explicitly (per the global
no-auto-commit rule). The commit message should declare risk per
`rules/lp-cowork-stake-declaration.md`.

## Decision points where the agent MUST pause

- **Phase-A failure**: pre-flight fail (dirty submodule, wrong
  branch, missing SHA). STOP.
- **Phase-B non-ff**: independent commits on both sides. STOP, ask
  rebase vs merge.
- **Phase-C engine surface**: Pass B inserted new blocks (review
  location) or Pass C tagged stale (review removal). STOP.
- **Phase-C file deleted or renamed**: STOP, ask.
- **Phase-C′ PIN safety check hit** (`--resync-strategy=reimport`
  only): a drifted `.org` contains `:LITERATE_ORG_PIN: yes`. STOP,
  ask user to unpin or fall back to `engine` mode.
- **Phase-C′ post-import byte-equivalence failure** (`--resync-strategy=reimport`
  only): Phase-F `git diff --stat` non-empty after reimport. STOP —
  import wrote something that doesn't round-trip; treat as a
  procedure bug.
- **Phase-D new directory**: STOP, ask whether to create a new
  `.org`.
- **Phase-D test / fixture / generated**: STOP, ask whether to
  skip.
- **Phase-E partial doc with >50% drop rate**: STOP, surface
  what's kept vs dropped.
- **Phase-F metadata audit failure**: STOP, report — algorithm bug.
- **Before each commit**: standard rule.

## Anti-patterns (never do)

- **Don't `git checkout`** in the submodule to inspect another
  branch — use a worktree or `git show <branch>:<path>`.
- **Don't push the submodule** when local branch is identical to
  upstream. The meta-repo's pointer bump alone records the intent.
- **Don't auto-resolve a content conflict** between `.org` and
  upstream source. Surface and ask.
- **Don't bootstrap a new `.org` for a single new utility file**
  if the owning `.org` exists — append.
- **Don't translate prose** — keep original language. Only fix
  factual claims (code-alignment), never re-author.
- **Don't hand-edit `:LITERATE_ORG_CONTAINS_DEFS:`** — always run
  `lp_metadata_refresh.py`. Hand edits drift from tree-sitter
  ground truth.

## Batch mode (`resync all`)

Loop the single-target workflow alphabetically over
`ls <TANGLED_ROOT>/`. Each target's STOP point halts the whole
batch — ask user, then resume from that target (don't skip ahead).
Track progress in an in-line table printed between targets; commit
per target, not at the end.

## Origin

Generalised from <meta-repo>'s original `lp-resync` skill (in turn
generalised from `lp-docs-migration`). The original handles only
edo's `repos/<sub>/` + `lp/<sub>/*.org` layout and `jt` branch
discipline. This generalised version:

- Replaced hard-coded `repos/` with `${LITERATE_AGENT_TANGLED_ROOTS}`
- Replaced hard-coded `lp/<sub>/` with `${LITERATE_AGENT_LP_ROOT}/<sub>/`
- Replaced hard-coded `jt` branch with `${LITERATE_AGENT_DEFAULT_BRANCH:-main}`
- Added Phase A metadata pre-flight (NEW in v4)
- Added Phase C automated sync engine path (NEW in v4)
- Added Phase F metadata audit (NEW in v4)
- Dropped edo-specific `lp-docs-migration` historical notes

The original SKILL.md is at <meta-repo> `.claude/skills/lp-resync/`
and should be deprecated once edo's `_env.sh` confirms the
generalised version works for its layout.

## See also

- `rules/lp-resync-metadata.md` — the metadata contract this skill
  consumes
- `rules/lp-resync-noweb-discipline.md` — noweb-restructure protocol
- `rules/lp-cowork-stake-declaration.md` — Risk: tier discipline for
  commits this skill creates
- `draft.org § 2026-05-22-lp-resync-roundtrip` — full v4 design
