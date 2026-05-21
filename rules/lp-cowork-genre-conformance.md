# Cowork: LP Genre as Bilateral Coordination Tool

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork research loop direction G — Bazerman 1988's
> finding that genre conventions are evolved coordination tools,
> mapped to LP cowork's four-part section shape.

The LP four-part section shape — heading + `:CUSTOM_ID:` + prose
preamble + src block — is not a style preference. It is an
*evolved coordination tool* that minimises reader-author
miscoordination cost for both human and AI agent. Deviation imposes
that cost on every future reader of the file. Genre conformance is
load-bearing infrastructure, not aesthetic polish.

## The empirical anchor

Bazerman 1988 (=Shaping Written Knowledge=) traced 300 years of
scientific genre evolution from Newton onward, showing genre
conventions stabilise *because* they reduce coordination cost.
Berkenkotter & Huckin 1995 extended to multiple disciplines. The
robust finding: stable genre is a coordination protocol —
readers know where to look, authors know what to write, and
*deviations carry per-reader parse cost that compounds across
the artefact's audience*.

The LP four-part shape is the LP-cowork genre. Section heading
names a concept; properties drawer carries the anchor; one-to-three
prose sentences answer "why"; src block answers "what." Both
reader populations (human, agent) build expectations against this
shape. Sibling sections train the expectations; cross-file
consistency reinforces them.

## Two consequences

### Stability is the value, not the shape

Any specific shape that's stable would coordinate. The four-part
shape isn't sacred; its *consistency across the codebase* is.
Evolving the shape is OK; gradual unintentional drift is not.
When the convention changes, all visible examples should update
together so the agent's example-driven genre learning catches up.

### Example exposure is the agent's only learning channel

Human authors accumulate genre awareness through years of reading
LP docs. Agents have *no inter-session accumulation*. The agent
learns the project's specific genre exclusively from the sibling
sections visible in the current context window. Three implications:

1. *Sibling examples are load-bearing infrastructure.* When a
   module's first section uses the four-part shape, every other
   section in the same module inherits this implicit teaching.
2. *Templates are agent-onboarding material.* `templates/new-
   module.org` is part of the genre persistence stack — it
   pre-seeds the shape for new files.
3. *Genre drift compounds.* If one PR introduces a deviation that
   isn't caught, the next agent reading that file may interpret
   the deviation as the new norm and propagate it.

## Failure mode

The grab-bag heading is the canonical genre violation. `**
Functions` / `** Helpers` / `** Misc` collapse the concept-named
expectation into mechanical category. Subsequent sections in the
same file now have ambiguous expectations — is the next heading
going to name a role or a category? The agent's genre model
becomes inconsistent, and downstream sections get progressively
weirder.

## Three operational practices

1. *Audit genre conformance, not just individual rule violations.*
   `commands/lp-research-audit.md` finds rule-level violations;
   genre conformance is the gestalt observation across all rules
   together. Both audits matter.
2. *Update visible examples when the genre evolves.* If you adopt
   a new convention (e.g. always include `:Last-validated:`),
   update all existing files within reasonable scope rather than
   leaving stale examples teaching the old genre to next-session
   agents.
3. *Make the genre visible in onboarding artefacts.* `template/
   new-module.org` + `hints/dual-audience-checklist.org` + the LP
   doctrine rules together are the genre's *public spec*. Treat
   them as such.

## Anti-pattern

Treating rule violations as isolated incidents to fix one by one.
Three small rule violations in the same section are not three
small problems; they are *one large genre erosion problem* — the
section's shape no longer matches the reader's expectations, and
the cumulative parse cost is much higher than the sum of
individual violations.

## See also

- `rules/literate-programming-document-first.md` — defines the
  four-part section shape (the genre's shape).
- `rules/lp-module-section-hierarchy.md` — module-level genre
  scaffolding.
- `rules/lp-stable-anchors-for-multi-referenced-sections.md` — one
  of the four parts (the anchor).
- `templates/new-module.org` — genre starter; pre-seeds the shape.
- `hints/dual-audience-checklist.org` — six-point genre audit
  (each item is a rule whose collective satisfaction = genre
  conformance).
- `docs/cowork-research.org` — direction G synthesis.
