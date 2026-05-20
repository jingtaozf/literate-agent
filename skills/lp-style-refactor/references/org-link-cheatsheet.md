# Org link / bookmark cheatsheet

Five patterns, all of them safe to use anywhere in the `lp/` tree. Pick
*readable* link text — never expose the raw anchor / line number to the
prose reader.

## 1. Same-file internal anchor (most common)

Target section gets a stable slug:

```org
,*** Function build_validation_prompt
:PROPERTIES:
:CUSTOM_ID: validator-build-prompt
:END:
```

Link from anywhere in the same file:

```org
See [[#validator-build-prompt][=build_validation_prompt=]] for the templating logic.
```

## 2. Cross-file section link

Without anchor (fragile — breaks on heading rename):

```org
[[file:validator.org::*Background — the PCR vocabulary in 90 seconds][validator.org § PCR vocabulary]]
```

With anchor (preferred — stable):

```org
[[file:validator.org::#pcr-vocabulary][validator.org § PCR vocabulary]]
```

## 3. Source-file line link (jumps in Emacs)

Use for prose like "the guard at `local.py:1481`" to give Emacs users a
one-keypress jump:

```org
[[file:../../repos/pcr-skill-networking/src/pcr_skill_networking/wisdomgraph/local.py::1481][local.py:1481]]
```

The `::N` is the line number. Path is **relative to the .org file**, not
the meta-repo root.

## 4. Named src block (becomes noweb anchor + prose target)

```org
,#+NAME: pattern-a-scan
,#+BEGIN_SRC python
def _scan_pattern_a(...): ...
,#+END_SRC
```

Refer to as `[[pattern-a-scan]]` from prose.

This is mostly useful when you DO want to splice the block into another
via noweb (`<<pattern-a-scan>>` reference inside a parent block). For
pure prose cross-reference, `:CUSTOM_ID:` on the *section* is usually
better.

## 5. "See also" footer block

Place at the end of a hub section (e.g. end of `* Algorithm overview`
before `* Modules`):

```org
,** See also

- [[#pcr-vocabulary][§ PCR vocabulary]] — the local jargon every term here builds on.
- [[file:reasoner.org::#reasoner-algorithm][reasoner.org § Stage 4 (Reason)]] — what consumes this stage's output.
- [[file:../../repos/pcr-skill-networking/src/pcr_skill_networking/wisdomgraph/base.py::153][base.py:153 :: build_wisdom]] — the helper this section explains.
```

3–5 bullets is the sweet spot. More clutters; fewer doesn't justify the
section.

## Always vs Never

- *Always* prefer `[[target][text]]` over `[[target]]` — the readable
  text is what the reader sees in the rendered org.
- *Always* anchor heavily-cross-referenced sections with `:CUSTOM_ID:`
  before they get bare-text linked from 3+ places.
- *Never* hand-write the raw target slug into prose. The two-argument
  link form (`[[target][text]]`) hides it from the reader.
- *Never* link to a section that doesn't exist — `org-lint` catches
  this on save; if you're scripting, run `make build-index` after to
  regenerate the TOC and surface any broken links.
