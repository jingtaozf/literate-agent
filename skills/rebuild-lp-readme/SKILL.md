---
name: rebuild-lp-readme
description: Regenerate the LP-layer entry-point documents — root README.org, every lp/<group>/README.org, and lp/INDEX.org — from the current state of lp/**/*.org. Use when the user asks to "rebuild readmes", "regenerate lp index", "refresh lp entry points", "rebuild lp/INDEX.org", "rebuild root README", or after adding/removing/renaming any lp/<group>/<file>.org so the indexes stay in sync. The skill is *idempotent and deterministic*: per-group narrative (elevator pitch / file role mapping / read order) lives in scripts/build_readme.py; per-file index rows are auto-rebuilt from each .org's #+TITLE; INDEX.org is regenerated from the same metadata via scripts/build_index.py.
---

# Rebuild LP READMEs + INDEX

> *Origin*: edo-literate. The skill is project-shaped to that repo's
> multi-submodule layout (`lp/<group>/<file>.org`) and its specific
> `scripts/build_readme.py` / `scripts/build_index.py`. Adapt the
> script paths and the per-group narrative when porting to another
> LP project.

This skill regenerates every entry-point document in the LP layer.
Three artefacts get rebuilt:

1. **Root `README.org`** — the human-facing front door of the
   literate repo. Three-bucket grouping of all submodules
   with per-submodule elevator pitch + read-order suggestions.
2. **`lp/<group>/README.org`** — one per submodule.
   Each one: Why this file exists / What this submodule is / How
   files relate / Read order for newcomers / Full file index.
3. **`lp/INDEX.org`** — auto-generated flat catalogue across every
   group, with one-line elevator pitches at top + per-group nested
   list of `.org` files with their tangle targets.

All three pass the same A-grade rubric as every other `.org` in
this tree (`scripts/audit_lp.py`): file-local-vars + `#+TITLE` +
`* Why ...` + `* Table of Contents :noexport:TOC:` + per-module
prose.

## Triggers

User says any of:

- "rebuild readmes" / "rebuild lp readmes" / "rebuild readme.org"
- "regenerate lp index" / "rebuild lp/INDEX.org"
- "rebuild root README"
- "refresh lp entry points"
- "the per-group READMEs are out of date"
- After adding / removing / renaming any `lp/<group>/<file>.org`
  (the new file's `#+TITLE` won't appear in the indexes until they
  regenerate)
- After onboarding a new submodule (the group's narrative needs to
  be added to `GROUP_NARRATIVE` in `scripts/build_readme.py`, then
  re-run)

## Hard rules

1. **Don't hand-edit the generated files.** Root `README.org`, every
   `lp/<group>/README.org`, and `lp/INDEX.org` are
   *generated*. Edit the templates / metadata in
   `scripts/build_readme.py` and `scripts/build_index.py` instead,
   then re-run. The generated files carry no "DO NOT EDIT" header
   (per the project rule) — the convention is enforced socially
   and by this skill.

2. **`_project.org` files are NOT generated.** Some groups have
   substantive `_project.org` files with imported architecture
   docs (e.g. ASM has 482 lines). Those stay hand-curated and the
   README points at them as the "deep read" target. This skill
   doesn't touch `_project.org`.

3. **Per-file entry rows come from each `.org`'s `#+TITLE`.** Don't
   hand-edit the index rows in a README; fix the `#+TITLE` on the
   source `.org` instead, then re-run.

4. **`make format` / post-format is NOT invoked.** The generated
   `.org` files don't need tangling. Just run the regenerators.

5. **Always run the audit after.** After regenerating, run
   `scripts/audit_lp.py` to confirm 154/154 file-level A-grade. If
   anything drops below A, surface the failure and stop.

## Inputs

None — the skill regenerates everything in scope. Optional flag:

- `--check` (on `scripts/build_readme.py`): don't write; exit 1 if
  any generated file would change. Useful as a pre-commit gate.

## Procedure

### Step 1 — Regenerate the per-group + root READMEs

```bash
uv run python scripts/build_readme.py
```

Writes `README.org` at the repo root and every `lp/<group>/README.org`
that has a matching entry in `GROUP_NARRATIVE` (currently 14 groups).

If a new submodule has been added but its narrative isn't yet in
`GROUP_NARRATIVE`, the script will print `SKIP (missing): <grp>` and
that group's README will NOT be regenerated. To fix:

- Open `scripts/build_readme.py`.
- Add a new entry to `GROUP_NARRATIVE` keyed by the submodule's
  directory name under `lp/`. Required keys: `elevator` (one
  paragraph), `groups` (list of `(label, role)` tuples for "How
  files relate"; empty list for single-file submodules),
  `read_order` (list of strings, numbered automatically).
- Also add the submodule to one of `ROOT_BUCKETS` so it appears in
  the root README's three-bucket table.
- Re-run the script.

### Step 2 — Regenerate `lp/INDEX.org`

```bash
uv run python scripts/build_index.py
```

This is a separate script that walks `lp/**/*.org`, groups by
top-level directory, and renders:

- A meta-overview block (what edo-literate is, how to navigate).
- A "Groups with one-line elevator pitches" section pulled from
  `GROUP_ELEVATOR` in `scripts/build_index.py`.
- A detailed per-group section listing each `.org` with its
  `#+TITLE` and first `:tangle` target.

If a new submodule was added, the per-group elevator pitch in
`GROUP_ELEVATOR` also needs an entry. Same pattern as
`GROUP_NARRATIVE` in `build_readme.py` — keyed by the directory
name.

### Step 3 — Verify

```bash
uv run python scripts/audit_lp.py
```

Expected output:

```
A-grade (file-level): 154/154

A+ tier — per-construct prose gaps: 3112 across 61 files
```

The A+ tier number is per-construct prose (e.g. `** Class X` with
no prose between heading and src block) — currently deferred
backlog and *not* what this skill addresses. As long as the
file-level count stays at 154/154 the regeneration is fine.

### Step 4 (optional) — Make sure links resolve

```bash
uv run python - <<'PY'
import re
from pathlib import Path
broken = []
for f in [Path('README.org')] + list(Path('lp').rglob('README.org')):
    for line in f.read_text().splitlines():
        for m in re.finditer(r'\[\[file:([^\]]+)\]', line):
            target = m.group(1)
            base = Path('.') if f == Path('README.org') else f.parent
            if not (base / target).exists():
                broken.append((str(f), target))
if broken:
    for src, t in broken:
        print(f"BROKEN: {src} → {t}")
else:
    print("all links resolve ✓")
PY
```

If anything broke, the most common cause is a renamed `.org` whose
old name still appears in the per-group `groups` list inside
`GROUP_NARRATIVE`. Fix the `groups` entry and re-run Step 1.

### Step 5 (when in CI / pre-commit) — Drift gate

```bash
uv run python scripts/build_readme.py --check
```

Exits 1 if any generated README would change. Use as a Bitbucket
pipeline gate to catch authors who forget to regenerate after
editing source `.org` titles.

## Anti-patterns

- **Editing the generated `README.org` files directly.** Your
  changes vanish on next regen. Edit `GROUP_NARRATIVE` or the
  source `.org`'s `#+TITLE` instead.
- **Forgetting Step 2.** After adding a new `lp/<group>/<file>.org`
  with a brand-new `#+TITLE`, the per-group README will pick it up
  but `lp/INDEX.org` won't until you re-run `build_index.py`.
- **Adding a new submodule without updating both scripts.** Both
  `scripts/build_readme.py` (`GROUP_NARRATIVE` + `ROOT_BUCKETS`)
  and `scripts/build_index.py` (`GROUP_ELEVATOR`) need the new
  entry — otherwise the new group is silently invisible in the
  generated indexes.
- **Skipping the audit.** The A-grade check catches missing
  `* Why` sections, wrong heading depth, etc. Always run.

## Worked example

After adding a new submodule `repos/new-sub/`:

```bash
# 1. Create the LP folder + at least a _project.org
mkdir lp/new-sub
$EDITOR lp/new-sub/_project.org

# 2. Add GROUP_NARRATIVE entry in scripts/build_readme.py
$EDITOR scripts/build_readme.py
# (also append the new submodule to one of ROOT_BUCKETS)

# 3. Add GROUP_ELEVATOR entry in scripts/build_index.py
$EDITOR scripts/build_index.py

# 4. Regenerate everything
uv run python scripts/build_readme.py
uv run python scripts/build_index.py

# 5. Audit
uv run python scripts/audit_lp.py
```

Expected: `A-grade (file-level): 156/156` (was 154; +1 README, +1
_project.org for the new group).
