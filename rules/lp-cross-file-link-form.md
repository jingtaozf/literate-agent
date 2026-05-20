# Cross-file references in Literate `.org` Files use org links, not bare text

> *Last-validated*: 2026-05-19
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate (`lp/<sub>/*.org` is the convention).

When prose in one `lp/<sub>/<file>.org` references another `.org` file (or
a section in it), use the org-link form. Never bare like
`=lp/<sub>/other.org=` or `see other.org §...`.

## Forms (preferred → fallback)

```org
[[file:other.org::#stable-custom-id][readable text]]
[[file:other.org::*Heading text][readable text]]
[[file:other.org][readable text]]
```

The first form is most robust — it survives heading renames on the
target side. Always pair it with a `:CUSTOM_ID:` on the target section
(see `lp-stable-anchors-for-multi-referenced-sections.md`).

## What "bare text" means here

```org
See =lp/pcr-skill-networking/reasoner.org= § "Algorithm overview".      ← bad
See =reasoner.org=.                                                     ← bad
See [[file:reasoner.org::#reasoner-algorithm][reasoner.org § Stage 4]]. ← good
```

The link form is clickable in Emacs / any org-link follower, and
non-clickable readers (HTML export, GitHub raw) still see the readable
text.

## Exception — inside docstrings tangled to .py

Python docstrings travel as plain text into IDE viewers that don't
render org links. Inside `#+begin_src python ... """ ... """`, keep
prose with the path:

```python
"""...

See ``lp/pcr-skill-networking/reasoner.org`` § Algorithm overview
for details.
"""
```

## Rationale

Bare cross-file mentions silently rot the moment the target file or
heading is renamed. Org links cause `org-lint` to surface dead
references immediately. The cost is one round trip through brackets;
the saving is every "where did this section go?" moment in the future.

## Enforcement

Mechanically caught by
`.claude/skills/lp-style-refactor/scripts/audit_lp.py` (rule
`bare-cross-file-ref`). Reviewed on PR — bare references in prose get
flagged and replaced. The conversion is the iter-5 pattern documented
in the skill's `references/worked-example.md`.
