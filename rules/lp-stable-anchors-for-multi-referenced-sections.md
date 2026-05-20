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
