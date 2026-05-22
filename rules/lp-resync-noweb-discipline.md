# LP Resync Noweb Discipline

> *Last-validated*: 2026-05-23
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: lp-resync source-drift roundtrip design (v4 — draft.org §
> 2026-05-22-lp-resync-roundtrip, edge case #5 "Noweb restructure
> with no source diff"). Extends `lp-noweb-for-big-blocks.md` with
> the sync-engine-facing maintenance protocol.

A large class or function in source can be expressed in the LP `.org`
two ways:

1. *Atomic block*: one `#+begin_src ... #+end_src` containing the
   whole class. Heading is `*** =BigClass=` with one tangle target.
2. *Noweb split*: parent `:skeleton` block holds the class envelope
   with a `<<chunk>>` placeholder; per-method child blocks (kind
   `noweb-leaf`) contribute to the same chunk via `:noweb-ref`. Org-
   babel-tangle stitches them at tangle time.

Both produce *byte-equivalent tangle output*. Choosing between them
is a *prose-narrative* decision (per `lp-noweb-for-big-blocks.md`):
splits buy section-per-method prose preambles at the cost of one
extra org-babel mechanism.

This rule covers the *sync-engine-facing* obligations when humans
restructure between the two forms — moves that have *no source
diff* but reshape the LP layer.

## The restructure cases

| Direction | What changes |
|-----------|--------------|
| atomic → noweb split | parent block keeps `:tangle`, gets `:LITERATE_ORG_BLOCK_KIND: skeleton:` + `:noweb yes`; new children get `:BLOCK_KIND: noweb-leaf:` + `:NOWEB_PARENT: <parent-anchor>:` + `:noweb-ref <chunk-name>:` |
| noweb split → atomic | all children's content merged back into parent; children's headings either deleted or kept as prose-only (kind `prose-only`, no `:tangle`); parent's `:BLOCK_KIND:` reverts to `atomic` |
| noweb shape preserved, but chunks renamed | `:NOWEB_PARENT:` anchors and `:noweb-ref` names update; `:CONTAINS_DEFS:` per child unchanged |

## Required metadata maintenance

After every restructure, *before the next /lp-resync run*, the
human must ensure these invariants hold:

1. *Skeleton block has `:LITERATE_ORG_BLOCK_KIND: skeleton:`* and
   `:noweb yes` in its `:header-args:`.
2. *Every leaf has `:LITERATE_ORG_BLOCK_KIND: noweb-leaf:`* and
   `:LITERATE_ORG_NOWEB_PARENT: <anchor-of-skeleton>:`.
3. *Skeleton's `:CONTAINS_DEFS:` is the union of leaves' `:CONTAINS_DEFS:`*.
4. *Tangle round-trip is byte-equivalent* against source at
   stored `LITERATE_ORG_SOURCE_SHA`. The whole point of restructure
   was to keep the tangle output stable; verify before committing.
5. *No duplicate def FQNs across siblings*. Two leaves both
   listing `Foo.method_a` in `:CONTAINS_DEFS:` is a structural
   error.

## How to maintain CONTAINS_DEFS after restructure

Run `scripts/lp_metadata_refresh.py <org-file>`:

```bash
python3 scripts/lp_metadata_refresh.py lp/sub/x.org
```

The refresh script:

1. Tree-sitter parses every `:tangle`-bearing block's content.
2. For skeleton blocks, expands `<<noweb-refs>>` by gathering
   children with matching `:NOWEB_PARENT:` and `:noweb-ref:`.
3. Computes ground-truth FQN list per block.
4. Overwrites `:LITERATE_ORG_CONTAINS_DEFS:` to match.
5. Surfaces any block where parse returned 0 defs (likely a
   `prose-only` block tagged with wrong BLOCK_KIND).

Refresh is idempotent: running twice produces the same result.

## Why this matters for /lp-resync

The sync engine's Pass A "modify body" needs to find *the owning
block* for a source def that changed. If the source rewrites
`Foo.method_a`, the engine consults `:CONTAINS_DEFS:` to identify
which block to update.

For atomic kind: the parent block IS the owner — straightforward.
For skeleton kind: the parent's `:CONTAINS_DEFS:` lists `Foo.method_a`
(via the union invariant above), but the *actual code* lives in a
leaf. The engine must walk from skeleton → leaves and find the
leaf whose own `:CONTAINS_DEFS:` lists `Foo.method_a`. That's the
write target.

Without correct `:NOWEB_PARENT:` + `:CONTAINS_DEFS:` metadata, the
engine *cannot find the right leaf*. It falls back to either:

- Updating the skeleton (wrong — overwrites the noweb structure),
- Failing with "ambiguous owner — STOP for human review."

The cost of stale noweb metadata is a STOP per affected sync run.
Audit catches this preventively.

## Common errors + fixes

| Error symptom | Likely cause | Fix |
|---------------|--------------|-----|
| Sync engine reports "block kind missing" on a leaf | New leaf created without `:LITERATE_ORG_BLOCK_KIND:` | Add `:LITERATE_ORG_BLOCK_KIND: noweb-leaf:` |
| `:NOWEB_PARENT:` points at non-existent anchor | Skeleton heading renamed or anchor changed | Add `:CUSTOM_ID:` on skeleton; point leaves at it |
| Refresh reports skeleton has more defs in CONTAINS_DEFS than union of leaves | A leaf was deleted but skeleton's CONTAINS_DEFS not updated | Re-run refresh |
| Refresh reports leaf has 0 defs | Leaf body is empty or prose-only | Mark as `prose-only` kind (no tangle); or add code body |

## When to use atomic vs noweb-split

(This is `lp-noweb-for-big-blocks.md` territory — referencing for
completeness.)

Triggers for noweb split:

- Class body > 80 lines
- A class mixing setup / public API / helpers warranting per-section prose
- Pure functions > 60 lines with natural narrative partitions

Don't split:

- Classes < 30 lines — splitting buys nothing
- Classes whose methods are 5-line one-liners
- Module-level helpers clustered around one concept that fit one
  src block

## Audit hook

`audit_lp_sync_metadata.py` checks invariants 1, 2, 3, 5 of this
rule. Invariant 4 (tangle round-trip) is checked by the existing
tangle-drift infrastructure.

Run the audit:

```bash
python3 scripts/audit_lp_sync_metadata.py <repo-root> --check-noweb
```

The `--check-noweb` flag enables the noweb-specific checks beyond
the baseline metadata audit.

## See also

- `rules/lp-noweb-for-big-blocks.md` — *when* to noweb-split
  (prose-narrative angle)
- `rules/lp-noweb-narrative-embedding.md` — three styles of
  noweb integration
- `rules/lp-resync-metadata.md` — the metadata schema this rule
  extends
- `draft.org § 2026-05-22-lp-resync-roundtrip` — full design,
  edge case #5
