# LP Resync Metadata Schema

> *Last-validated*: 2026-05-23
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: lp-resync source-drift roundtrip design (v4 — draft.org §
> 2026-05-22-lp-resync-roundtrip). Codifies the metadata contract
> between literate-org (producer at import time) and literate-agent
> (consumer at sync + audit time).

The lp-resync roundtrip workflow depends on durable metadata in LP
`.org` files. This rule defines the schema, who maintains each
field, when it gets set, and what consistency invariants apply.

## Two-level schema

### File-level (=#+PROPERTY:= at .org header)

| Property | Type | Maintained by | Semantics |
|----------|------|----------------|-----------|
| `LITERATE_ORG_SOURCE_SHA` | git SHA | sync engine | source-repo SHA at last successful sync round-trip |
| `LITERATE_ORG_SOURCE_SHA_DATE` | ISO8601 | sync engine | timestamp of the SHA stamp — human-readable audit trail |
| `LITERATE_ORG_TREESIT_GRAMMAR_HASH` | string | sync engine | hash of the tree-sitter grammar binary used for the def-extraction; flags breaking changes |
| `LITERATE_ORG_EXCLUDED_DEFS` | space-separated names | human | defs in source that user deliberately excluded from LP coverage |

### Block-level (=:PROPERTIES:= drawer on `:tangle`-bearing headings)

| Property | Type | Maintained by | Semantics |
|----------|------|----------------|-----------|
| `:LITERATE_ORG_BLOCK_KIND:` | `atomic` / `skeleton` / `noweb-leaf` / `prose-only` | import + restructure | what kind of block this is for sync purposes |
| `:LITERATE_ORG_CONTAINS_DEFS:` | space-separated FQN list | sync engine (auto) | the source defs this block owns (auto-derived from tree-sitter parse of block content + noweb expansion) |
| `:LITERATE_ORG_NOWEB_PARENT:` | anchor of skeleton block | import + restructure | for `noweb-leaf` kind, points at the skeleton block's `:CUSTOM_ID:` |
| `:LITERATE_ORG_GENERATED:` | `original` / `pass-a-modify` / `pass-b-add` | sync engine | provenance — was this block authored by human (original) or by a sync pass |
| `:LITERATE_ORG_PIN:` | `yes` (or absent) | human | "don't sync this block — treat as authoritative regardless of source state" |
| `:STALE:` | `<ISO8601> last-seen-at <SHA>` | sync engine (Pass C) | "source removed the def this block owns; human review pending" |

## Who writes what

| Producer | Fields it sets |
|----------|----------------|
| `literate-org-import` at first import | `LITERATE_ORG_SOURCE_SHA`, `SHA_DATE`, `TREESIT_GRAMMAR_HASH`, per-block `:BLOCK_KIND:`, `:CONTAINS_DEFS:` |
| `scripts/lp_sync_bootstrap.py` (legacy migration) | Same as import — stamps existing .org with HEAD as initial SHA after verifying tangle round-trip |
| `scripts/lp_sync_engine.py` Pass A modify | Updates block body + bumps `LITERATE_ORG_SOURCE_SHA` (file-level) at end |
| `scripts/lp_sync_engine.py` Pass B add | Inserts new heading + block with `:LITERATE_ORG_GENERATED: pass-b-add:` |
| `scripts/lp_sync_engine.py` Pass C stale | Adds `:STALE: <date> last-seen-at <old-sha>:` on owning block |
| `scripts/lp_metadata_refresh.py` | Recomputes `:CONTAINS_DEFS:` after human noweb-restructure |
| Human | `LITERATE_ORG_EXCLUDED_DEFS` (opt-out), `:LITERATE_ORG_PIN: yes:` (authoritative), `:LITERATE_ORG_BLOCK_KIND:` change (restructure) |

## Consistency invariants

These must hold after every sync + after every human restructure:

1. *SHA presence*: every .org file with at least one `:tangle <path>` target has `LITERATE_ORG_SOURCE_SHA` set.
2. *SHA round-trip*: tangling .org at the stored SHA's source state produces byte-equivalent output. If not, SHA is wrong or .org has drifted; bootstrap or sync fails.
3. *Block-kind ↔ noweb link*: every block with `:LITERATE_ORG_BLOCK_KIND: noweb-leaf:` has a `:LITERATE_ORG_NOWEB_PARENT:` pointing to a valid skeleton-kind block in the same file.
4. *CONTAINS_DEFS ↔ content*: tree-sitter parse of block content (or expanded noweb skeleton) produces the same set of def FQNs as `:CONTAINS_DEFS:` lists. Drift means metadata is stale; run `lp_metadata_refresh.py`.
5. *No duplicate CONTAINS_DEFS*: a single FQN should appear in at most one block's `:CONTAINS_DEFS:` per .org file. Duplicate means structural ambiguity (which block owns this def?) — surface to human.
6. *EXCLUDED_DEFS ↔ source*: every name in `LITERATE_ORG_EXCLUDED_DEFS` should correspond to an actual def in the source. Stale entries (deleted from source) get reported by audit.

## Audit script

`scripts/audit_lp_sync_metadata.py` checks invariants 1, 3, 4, 5, 6.
Invariant 2 (tangle round-trip) is checked by the existing
tangle-check infrastructure (`make check-tangle-drift` per
`Makefile.lp.mk`).

Quarterly cadence per `rules/lp-agent-long-horizon-audit-cadence.md`
should include the metadata audit. Add it to the `/lp-research-audit`
or `/lp-cowork-review` command in a future iteration.

## When to update metadata vs let sync handle it

| Situation | Who updates |
|-----------|-------------|
| Source code changes | sync engine, via /lp-resync workflow |
| Human restructures .org into noweb (no source change) | human edits `:BLOCK_KIND:` + `:NOWEB_PARENT:`; runs `lp_metadata_refresh.py` to recompute `:CONTAINS_DEFS:` |
| Human moves a def to `EXCLUDED_DEFS` (drops from LP coverage) | human adds to `EXCLUDED_DEFS`; deletes the corresponding block manually; runs audit to confirm clean |
| Human pins a block (authoritative LP version diverges intentionally from source) | human adds `:LITERATE_ORG_PIN: yes:`; sync engine skips this block on next /lp-resync |
| Tree-sitter grammar version bumps (binary changed) | sync engine notices `TREESIT_GRAMMAR_HASH` mismatch and re-validates all `:CONTAINS_DEFS:` against new grammar parse |

## S3-lite limitation: NOWEB_PARENT not auto-inferred

The shipping S3-lite bootstrap (`scripts/lp_sync_bootstrap.py`)
detects `:LITERATE_ORG_BLOCK_KIND:` for all `:tangle`-bearing
blocks, including noweb-leaf blocks (identified by `:noweb-ref` in
header-args). It does NOT yet set `:LITERATE_ORG_NOWEB_PARENT:`
because parent-inference requires building an index of skeleton
blocks (`<<chunk-name>>` placeholders) and matching against
leaves' `:noweb-ref` names — a richer org-block parse that lands
in S5 / S6.

Expected post-S3-lite audit state: I3b violations (noweb-leaf
without parent) appear once for each noweb-leaf block. These are
*acceptable bootstrap residue* — they get resolved by:

- Human: hand-set `:LITERATE_ORG_NOWEB_PARENT: <skeleton-anchor>:`
  on each leaf (manual triage when there are < ~20 cases).
- Automated: future `scripts/lp_metadata_refresh.py` (S4+) reads
  skeleton blocks' `<<chunk-name>>` placeholders, matches leaves'
  `:noweb-ref` names, infers parent automatically.

The audit script reports I3b as `error` severity, but the
expected adoption path is to *accept* this state post-bootstrap and
resolve incrementally — either via human triage or via the future
refresh script. Do not treat I3b alone as "bootstrap failed."

## Bootstrap for legacy .org files

`.org` files predating this schema have no SHA, no BLOCK_KIND, no
CONTAINS_DEFS. `scripts/lp_sync_bootstrap.py` handles legacy
migration:

```bash
# Stamp single file
python3 scripts/lp_sync_bootstrap.py path/to/file.org

# Stamp tree
python3 scripts/lp_sync_bootstrap.py --all <repo-root>
```

Bootstrap algorithm:

1. Verify tangle round-trip on current `.org` against current source
   working tree is byte-equivalent. If not, *stop* — the .org has
   drifted from source already and needs manual reconciliation
   before bootstrap.
2. Stamp `LITERATE_ORG_SOURCE_SHA` = `git -C <source-repo> rev-parse HEAD`.
3. Stamp `LITERATE_ORG_SOURCE_SHA_DATE` = current ISO timestamp.
4. Stamp `LITERATE_ORG_TREESIT_GRAMMAR_HASH` = grammar binary hash.
5. For each `:tangle`-bearing block, set default `:LITERATE_ORG_BLOCK_KIND: atomic:`
   unless block has `:noweb yes` → `skeleton`. Compute `:CONTAINS_DEFS:`
   via tree-sitter parse.
6. Report any block where tree-sitter found 0 defs (might be
   `prose-only` block tagged with `:tangle` by mistake — needs
   human triage).

## Anti-patterns

- *Stamping SHA without verifying round-trip*. The SHA is supposed to mean "source at this commit matches our .org's tangle." Stamping without verification corrupts the invariant.
- *Hand-editing `:LITERATE_ORG_CONTAINS_DEFS:`*. Always run `lp_metadata_refresh.py`; hand edits drift from tree-sitter ground truth.
- *Using heading text as identity*. Heading text drifts (rename function → heading changes). The schema uses `:CONTAINS_DEFS:` FQN + tree-sitter on block content — robust against heading drift.
- *Removing `:STALE:` without triage*. Stale tags should be resolved either by re-adding the def in source (un-staling) or by deleting the block + adding the name to `EXCLUDED_DEFS` (closing).

## See also

- `rules/lp-resync-noweb-discipline.md` — noweb-restructure protocol
- `rules/lp-stable-anchors-for-multi-referenced-sections.md` — sibling
  metadata schema (anchors); same audit-cadence pattern
- `rules/lp-cowork-boundary-object-evolution.md` — why this metadata
  fits literate-agent's boundary-object role
- `draft.org § 2026-05-22-lp-resync-roundtrip` — full design doc
- `skills/lp-resync/SKILL.md` — workflow that consumes this metadata
