# Literate Agent — Shared LP Doctrine

This file aggregates the literate-programming rules maintained in
`~/projects/literate-agent/rules/`. A consuming repository imports
this aggregator from its own `CLAUDE.md` with a single line:

```
@~/projects/literate-agent/CLAUDE.md
```

Claude Code inlines this file (and the rules it `@`-imports) at
load time, so each repo gets the full LP doctrine without
maintaining a local copy.

## Core LP discipline

@~/projects/literate-agent/rules/literate-programming-document-first.md

@~/projects/literate-agent/rules/lp-prose-no-self-narration.md

@~/projects/literate-agent/rules/org-mode-docs-first.md

@~/projects/literate-agent/rules/lp-module-section-hierarchy.md

## Org mechanics (avoid common traps)

@~/projects/literate-agent/rules/lp-comma-escape-leading-star.md

@~/projects/literate-agent/rules/lp-cross-file-link-form.md

@~/projects/literate-agent/rules/lp-stable-anchors-for-multi-referenced-sections.md

## Noweb — splitting big classes / narrative embedding

@~/projects/literate-agent/rules/lp-noweb-for-big-blocks.md

@~/projects/literate-agent/rules/lp-noweb-narrative-embedding.md

## Tangle lifecycle

@~/projects/literate-agent/rules/lp-purge-deleted-files-first.md

@~/projects/literate-agent/rules/python-literate-programming.md

## Tests embedded in narrative

@~/projects/literate-agent/rules/tests-embedded-in-narrative.md

## Dual-audience design (research-grounded)

These three rules derive from the 50-iteration transfer-gradient
research; see `docs/transfer-gradient.org` for the figure + the
6 shared-primitive families + the catalogued anti-patterns.

@~/projects/literate-agent/rules/lp-load-bearing-affordances-structural.md

@~/projects/literate-agent/rules/lp-agent-persistence-hooks.md

@~/projects/literate-agent/rules/lp-transfer-discipline-no-weak-metaphors.md

## Cowork (human + AI agent author pair)

These five rules codify the protocols that emerged across 6+ months
of claude-agent + edo-literate + cmux cowork practice. They extend
the dual-audience reader research to the dual-author authoring
question. The proposed deepening loop is documented at
`docs/cowork-research.org`.

@~/projects/literate-agent/rules/lp-cowork-stake-declaration.md

@~/projects/literate-agent/rules/lp-cowork-propose-before-edit.md

@~/projects/literate-agent/rules/lp-cowork-anti-sycophancy.md

@~/projects/literate-agent/rules/lp-cowork-handoff-template.md

@~/projects/literate-agent/rules/lp-cowork-persistence-stack.md

@~/projects/literate-agent/rules/lp-cowork-review-expectation.md

@~/projects/literate-agent/rules/lp-cowork-genre-conformance.md

@~/projects/literate-agent/rules/lp-cowork-boundary-object-evolution.md

## Design-record discipline

@~/projects/literate-agent/rules/design-stays-in-org.md

## Risk → autonomy (LP surfaces)

@~/projects/literate-agent/rules/lp-autonomy-levels.md

## Supporting craft (LP-friendly code style)

@~/projects/literate-agent/rules/code-clarity-over-features.md

@~/projects/literate-agent/rules/naming-conventions.md

@~/projects/literate-agent/rules/no-speculative-generality.md

@~/projects/literate-agent/rules/oop-smalltalk-protocols.md

@~/projects/literate-agent/rules/factory-only-construction.md

## Python-specific craft

@~/projects/literate-agent/rules/prefer-pydantic-over-dataclass.md

@~/projects/literate-agent/rules/prefer-model-validate.md

@~/projects/literate-agent/rules/package-root-policy.md

@~/projects/literate-agent/rules/no-bare-except.md

## Language-specific LP hints (lazy-loaded)

The `hints/` folder contains language-specific LP caveats. They
are **NOT** `@`-imported into this aggregator (would bloat
context). Instead, they auto-activate via per-language skills
when you edit a matching file type:

| Language | Auto-activates on | Hint file |
|----------|-------------------|-----------|
| Elisp | `.el` files (skill: `lp-hint-elisp`) | `hints/elisp.org` |
| Python | `.py` files (skill: `lp-hint-python`) | `hints/python.org` |

When editing a literate `.org` file that contains `#+BEGIN_SRC <lang>`
blocks, also consult `hints/<lang>.org` for that language's traps.

There is also a *cross-audience* hint:

| Topic | Auto-activates on | Hint file |
|-------|-------------------|-----------|
| Dual-audience section review | user asks to "review section" / "check this section" (skill: `lp-dual-audience-check`) | `hints/dual-audience-checklist.org` |

See `hints/README.org` for the convention and how to add a new
language.

## LP build / lint commands (typical project layout)

Drop the `templates/Makefile.lp.mk` fragment into your project to
get a working set of targets:

```bash
include $(HOME)/projects/literate-agent/templates/Makefile.lp.mk
```

That gives you:

```bash
make tangle FILE=lp/<sub>/<x>.org      # tangle one .org
make tangle-all                        # tangle the whole tree
make check-structure                   # depth ≤ 5, prose-before-src
make build-index                       # regenerate lp/INDEX.org
make build-tangle-map                  # refresh .cache/tangle-map.tsv
make build-readme                      # regenerate READMEs from .org metadata
make check-tangle-drift                # re-tangle + per-sub git diff
make measure-docs-first                # prose-density snapshot
```

The hooks key off `LITERATE_AGENT_TANGLE_MAKE_TARGET` and the
`/lp-check` slash command keys off `LITERATE_AGENT_*` env vars
(see README for the full list).

## Auto-tangle lifecycle

`.org` edits trigger tangle automatically through two paths that
both end at `org-babel-tangle-file`:

1. **PostToolUse hook** on Edit / Write / MultiEdit — the
   `tangle-org-buffer.sh` hook calls `emacsclient` first, falls
   back to `make tangle FILE=…`. Gated behind `LP_AUTO_TANGLE=1`
   until each consuming project verifies per-formatter byte-
   equivalence.
2. **Manual** — `make tangle FILE=lp/<sub>/<x>.org`.

Set `LITERATE_ORG_NO_AUTO_TANGLE=1` to bypass the hook for bulk
patches.

## Maintenance cadence

- *Quarterly*: review the `> *Last-validated*:` date on each rule.
  Drop any rule whose date is > 6 months old AND has no triggering
  incident. Bump the date when a rule is re-confirmed.
- *Quarterly*: run `make build-tangle-map` and diff against
  `.cache/tangle-map.tsv` — drift here means an `.org` `:tangle`
  header changed without the cache being refreshed.

## Tangle-map cache

The PreToolUse hook (`block-tangled-edit.sh`) consults
`.cache/tangle-map.tsv` for a reverse lookup from tangled output
path → owning `.org` source. See [`docs/tangle-map-schema.org`](./docs/tangle-map-schema.org)
for the file format and how to regenerate it.

## Notes for consuming repos

Examples in the rules reference the `claude-agent` and `edo-literate`
codebases (the rules' birthplaces). Adapt module prefixes, file
names, and tangle targets to your own project — the *principles*
are project-neutral.

If a rule's examples are too distracting for your codebase, import
only the rules you want individually instead of importing this
aggregator. For example:

```
@~/projects/literate-agent/rules/literate-programming-document-first.md
@~/projects/literate-agent/rules/lp-prose-no-self-narration.md
```
