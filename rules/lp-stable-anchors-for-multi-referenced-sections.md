# Sections referenced ≥ 2 times get a stable :CUSTOM_ID:

> *Last-validated*: 2026-05-19
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

When a section in `lp/<sub>/<file>.org` is linked-to from ≥ 2 other prose
sites (same file OR cross-file), give it a stable slug:

```org
,* Background — the PCR vocabulary in 90 seconds
:PROPERTIES:
:CUSTOM_ID: pcr-vocabulary
:END:
```

Other prose then references the anchor instead of the heading text:

```org
[[#pcr-vocabulary][§ PCR vocabulary]]                      ← same file
[[file:validator.org::#pcr-vocabulary][...PCR vocabulary]] ← cross-file
```

## Slug naming

| pattern | when |
|---------|------|
| `<topic>` — e.g. `pcr-vocabulary`, `noisy-or`, `dai-iteration` | concept-level anchor in a `*` or `**` section |
| `<file>-<function>` — e.g. `validator-build-prompt`, `reasoner-build-wisdom-index` | per-`***` function anchor for cross-file linking to specific code |
| `<file>-<phase>` — e.g. `reasoner-phase1-dai`, `validator-phase2-llm` | phase / stage anchor |

Slugs must be unique within a file. Cross-file uniqueness is not
required (each file has its own anchor namespace).

## When NOT to add

- Section referenced 0–1 times: anchor is overhead. Add it the moment
  the 2nd reference appears.
- Sections inside a `:tangle no` parent that exists only to satisfy
  noweb mechanics (e.g. the skeleton block in
  `lp-noweb-for-big-blocks.md` example) — anchor goes on the
  user-visible `*** =ClassName=` heading, not on the `**** =method=`
  children.

## Recommended (not required)

- Top-level `* Algorithm overview` / `* Background` sections: anchor
  even at 0 references today, because they will get cross-referenced.
- Section that the rubric in
  `.claude/skills/lp-style-refactor/references/lp-rubric.md` describes
  as a "hub" (end of `* Algorithm overview` before `* Modules`): pair
  the anchor with a `** See also` footer.

## Rationale

Heading text is the natural cross-reference key, but it changes during
normal refactoring. Anchors decouple the link from the text — renaming
"Background — the PCR vocabulary in 90 seconds" to "Background"
breaks every `[[file:x.org::*Background — the PCR vocabulary in 90 seconds]]`
link but leaves every `[[file:x.org::#pcr-vocabulary]]` link working.

## Enforcement

Mechanically caught by
`.claude/skills/lp-style-refactor/scripts/audit_lp.py` (rule
`anchor-candidate`, counts heading-text references and flags ≥ 2
without `:CUSTOM_ID:`). Reviewed on PR. Add via the `lp-style-refactor`
skill's standard iteration; see the skill's
`references/org-link-cheatsheet.md` for forms.

### Mechanical scan command

For ad-hoc check across a tree of .org files, find headings whose
text is cross-referenced ≥ 2 times but lack a `:CUSTOM_ID:`:

```bash
# Step 1: list every heading text in the tree.
find <dir> -name "*.org" \
  | xargs awk '/^\*+ / { sub(/^\*+ +/, ""); print FILENAME":"$0 }'

# Step 2: for each heading text, count cross-references in prose
# (lines containing `[[*<text>]]` or `[[file:...::*<text>]]`).
# Sections referenced ≥ 2 times AND missing `:CUSTOM_ID:` are
# violations.
```

The audit script generalises this and emits a per-file ratio. See
[Q2 2026 audit findings](../docs/agent-native-phenomena.org) — the
raw heading-count metric (93-98% missing) is *misleading*; only
sections referenced ≥ 2 times need anchors. Real violation rate
is lower (sample suggests 5-15% of concept-level headings).

### Target threshold

Healthy project state: **≥ 95% of multi-referenced
(≥ 2-reference) sections have `:CUSTOM_ID:` anchors**. Anything
below ≥ 90% suggests backfill work — but only on the
multi-referenced subset, never on every heading.

The threshold is calibrated to allow per-PR fluctuation while
catching systemic drift. Track over time via the quarterly
audit cadence (`rules/lp-agent-long-horizon-audit-cadence.md`).

## Why ≥ 2 references (recognition-over-recall grounding)

Tulving & Thomson 1973's *encoding specificity* finding established
that recognition (cue-present retrieval) is dramatically cheaper than
recall (cue-absent retrieval). Nielsen 1994 made this Heuristic #6
("recognition rather than recall") in his canonical 10-heuristic list.

A `:CUSTOM_ID:` is a *recognition surface* — both audiences arrive
at the cross-reference with the cue (`[[#stable-anchor]]`) already
in hand. The alternative — recalling the heading text from memory or
grepping for fragments — is *recall* and produces the symmetric
failure mode: hallucination in agents, "I knew that but couldn't
find it" in humans.

The ≥ 2-references trigger is not arbitrary: it captures the empirical
break-even point where the cost of typing one `:CUSTOM_ID:` line
beats the per-reference cost of resolving the link via heading text
(which silently breaks on rename). Anchors used only once may rely
on heading text; anchors crossed twice or more pay for themselves
the first time the heading is edited.

This makes `:CUSTOM_ID:` one of the *cleanest dual-audience
optimisations* in LP doctrine — same edit serves both audiences with
the same mechanism. See `rules/lp-load-bearing-affordances-structural.md`
for the broader principle.
