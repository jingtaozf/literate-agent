# Purge .org Sections for Upstream-Deleted Files BEFORE Re-Tangling

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

When a `/lp-resync <sub>` (or any other merge / pull) of
`repos/<sub>/` removes one or more source files (`.py` / `.ts` /
`.tsx` / `.rs` / `.tf`), the corresponding `lp/<sub>/<x>.org`
sections that still point at those paths are **stale tangle
sources**. If a tangle runs before those sections are removed,
the deleted files come back to life on disk as untracked tangle
outputs — and the next `literate-org-import` pass picks them up
again, re-creating the very sections we should have removed.

This is a tight, repeatable failure loop:

```
upstream deletes foo.py
   ↓ (merge — foo.py removed from working tree)
   ↓
.org still has a "foo.py" section with :tangle foo.py
   ↓ (make tangle — re-creates foo.py on disk, now untracked)
   ↓
literate-org-import scans tree — sees foo.py — re-adds section
   ↓
.org has "foo.py" section again. Net effect: deletion never landed.
```

Hit during the 2026-05-15 `mega-code-oss` resync of PR #80:
upstream deleted `mega_code/client/{check_pending,collector,schema}.py`
+ `scripts/check_pending_skills.py`. The merge committed the
deletions, but the next `make tangle-repo` re-created the files
because the old per-construct .org sections were still there. The
re-import then added them back as untracked sections, masking the
upstream intent until a manual purge.

## The order that breaks the loop

For every `/lp-resync` (and every manual merge), do this **before**
the first tangle of the new HEAD:

1. Capture the upstream deletions:
   ```bash
   git -C repos/<sub> diff --name-only --diff-filter=D HEAD@{1} HEAD
   ```
2. For each deleted path, find and remove its `.org` section. The
   section is the `***` heading whose `:header-args:` line contains
   `:tangle ../../repos/<sub>/<path>`. Remove the heading + drawer
   + all sub-content down to the next sibling heading at equal or
   shallower depth.
3. Only then run `make tangle-repo REPO=<sub>` and proceed with the
   rest of the resync.

The reverse mistake — tangle first, purge later — leaves orphan
`.py` files on disk and orphan `.org` sections in tree, and the
next innocent `literate-org-import` reinstates everything.

## When upstream renames (not deletes)

A rename shows up as `R` in `git diff --name-status` and is the
same problem rotated 90 degrees: the old `:tangle` path is now
invalid, the new path has no section. Surface both — the `.org`
needs the OLD section removed AND a new one created (or the
existing section's `:tangle` path updated). Treat as a STOP point
in `/lp-resync` Phase-C, same as the "file deleted upstream" rule
in `lp-resync/SKILL.md`.

## The matching skill update

`/lp-resync` Phase-C already flags "File deleted upstream → STOP
and ask whether to remove the section or keep with `:tangle no`
as historical." This rule extends that with the operational
consequence: **the section MUST be removed before the next tangle**,
regardless of whether it ultimately keeps `:tangle no` or is
deleted outright. A `:tangle no` section is safe (no tangle output),
a section with `:tangle <path>` to a deleted file is not.

## Anti-patterns

- **Run tangle first, see what's in the working tree, then "clean
  up"**. The cleanup itself is contaminated by tangle's output.
- **Trust `git status` after tangle to tell you which files are
  upstream-deleted.** They'll show as `??` (untracked) because
  tangle re-created them. The merge already committed the
  deletions; the `??` state is downstream noise.
- **Re-run `literate-org-import` to "refresh"** without first
  purging the deleted-file sections. The import will happily
  re-pick up the re-tangled `.py` files and re-create the same
  sections.

## Enforcement

- `/lp-resync` skill explicitly STOPs on `--diff-filter=D` rows.
- After every `/lp-resync`, the final verification step grep for
  orphan tangle outputs:
  ```bash
  git -C repos/<sub> status -s | grep '^??' | grep -E '\.(py|ts|tsx|rs|tf)$'
  ```
  Any hit means the `.org` still has a stale section pointing at
  that path. Find it via the `:tangle ../../repos/<sub>/<path>`
  string and purge.
- This rule lives in `edo-literate/.claude/rules/` so meta-repo
  agents see it on every session.
