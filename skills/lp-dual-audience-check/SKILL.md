---
description: Run the 6-point dual-audience checklist on a literate .org section. Each item maps to a research-backed LP rule (heading-as-concept, :CUSTOM_ID: for ≥2 refs, WHY in prose, one mechanism per section, structural-not-typographic affordances, cold-start agent recoverability). Use after editing or writing an .org section, or as a manual review pass.
when_to_use: user says "check this section", "review the LP section", "run the dual-audience checklist", "did I miss anything in this section"; or proactively after editing a literate .org section's prose preamble or first src block.
disable-model-invocation: false
allowed-tools: Read Grep Bash
paths: "**/*.org"
---

# lp-dual-audience-check — 6-point review for one LP section

Points at the canonical checklist:

    ~/projects/literate-agent/hints/dual-audience-checklist.org

## What this skill does

Runs the 6-point dual-audience review on a single literate `.org`
section the user just edited (or one they point at). Each item is
yes/no; the skill outputs a compact report grouped by which rule
each fail maps to.

## The 6 items

1. **Heading-as-concept** — not "Functions" / "Helpers" / "Misc".
2. **:CUSTOM_ID:** present if section is ≥ 2× referenced.
3. **WHY in prose preamble** — trade-off / rejected alternative.
4. **One new mechanism** per section, not several.
5. **Structural affordances** (not typographic) for load-bearing cues.
6. **Cold-start recoverable** — at least one stable anchor.

## Procedure

1. Read the target section (the one the user named, or the most
   recently-edited one if unspecified).
2. Run each check mechanically:
   - **1**: heading text matches `^(Functions|Helpers|Utilities|Misc|Things|Stuff)$`?
   - **2**: grep the project for `[[*<heading>]]` or `[[#<expected-anchor>]]`
     references; count; if ≥2 and no `:CUSTOM_ID:` drawer, flag.
   - **3**: read the lines between heading and first `#+begin_src`;
     check for non-empty prose (≥ 1 sentence) that names a *why*
     (trade-off, constraint, rejected alternative).
   - **4**: heuristic — does the section explain >2 mutually-
     dependent abstractions without sub-section breakdown?
   - **5**: heuristic — does the prose use bold/italic/whitespace
     to convey "this is THE entry point" / "this is the public API"
     without a matching `:PROPERTIES:` / `:CUSTOM_ID:`?
   - **6**: does the section have a stable handle (CUSTOM_ID, named
     block, concept heading) the agent can re-find on cold start?
3. Output a markdown report grouping fails by which rule they map to.

## Output shape

```
## Dual-audience check: <file>::<heading>

Pass: 4/6

✗ Item 2: missing :CUSTOM_ID:
  Section is referenced from 3 locations:
    - other.org:42 ([[*Heading Name][label]])
    - here.org:108 ([[*Heading Name]])
    - README.org:15 ([[#expected-anchor]])
  → Add :CUSTOM_ID: per rules/lp-stable-anchors-for-multi-referenced-sections.md

✗ Item 5: load-bearing affordance is typographic-only
  Line 47: "*public API* — call this from external code"
  → Add :PROPERTIES: :PUBLIC: yes :END: drawer, or :CUSTOM_ID: public-api
  → See rules/lp-load-bearing-affordances-structural.md
```

## See also

- `~/projects/literate-agent/hints/dual-audience-checklist.org` — the
  canonical checklist with detailed rationale per item.
- `~/projects/literate-agent/docs/transfer-gradient.org` — the research
  figure each item derives from.
- `~/projects/literate-agent/skills/audit-prose/` — sibling skill that
  focuses on prose deletion-test only; this skill is structurally
  broader.
