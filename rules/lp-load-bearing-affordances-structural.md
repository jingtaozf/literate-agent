# Load-Bearing Affordances Must Be Structural, Not Typographic

> *Last-validated*: 2026-05-20
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: research finding (transfer-gradient figure, directions J/D/H);
> the principle generalises to any dual-audience LP project.

When an affordance is *load-bearing* — i.e. the reader (human OR AI agent)
must identify it to use the system correctly — express it through the
*structural layer* (`:CUSTOM_ID:`, `#+NAME:`, `:PROPERTIES:`, section
heading text), not through *typography* (bold, italic, whitespace,
indentation).

## Why

The LP document is a *dual-audience artefact*: human readers and AI
agent readers share most affordances but optimise differently. Research
(transfer-gradient figure) places two HI direction findings squarely
in the *human-only quadrant*:

- *Eye-tracking + saccades* (Rayner 1998) — typographic cues drive
  the human's next saccade. Agents tokenise without saccading.
- *Gestalt principles* (Wertheimer 1923) — proximity / similarity /
  closure produce perceptual grouping. Agents have no retina.

Bold, italic, whitespace, font weight, paragraph length: these all
serve the human only. They wash out completely in the agent's
token-by-token processing. If a critical affordance is encoded ONLY
typographically (e.g. "this is the public API" expressed via bold),
the agent never sees it.

The structural layer — `:CUSTOM_ID:`, `#+NAME:`, `:PROPERTIES:` —
survives tokenisation. Both audiences read it. *That* is the
dual-audience layer.

## The 4-rule heuristic

1. **Be dense in structural signifiers**. Every section gets a
   `:CUSTOM_ID:`; every cross-referenced block gets a `#+NAME:`;
   every heading names a *concept* (the role this section plays in
   the system), not a phase (`Functions`, `Helpers`, `Misc`).
2. **Prefer structural over typographic for load-bearing affordances**.
   *Italics for emphasis* is fine for humans; if the agent *must* know
   "this is the public API," express that as a `:PROPERTIES:` drawer
   or a tag, not as bold text.
3. **Layer signifier-vocabularies**. Keep typography for human
   aesthetics; layer structural cues underneath so the agent gets
   the same affordance map. A heading written `* Public API` in bold
   gives humans the typographic signifier; the heading text itself
   plus a `:CUSTOM_ID:` gives the agent the structural one. Both
   audiences win.
4. **Heading-as-concept restated as signifier-design**. A concept-named
   heading (`** Permission Request Handler`) IS a structural signifier
   for both audiences. A phase-named heading (`** Functions`) hides
   the role; the agent has nothing to triage on, the human has to
   read the body to know what's in it.

## Test for a candidate affordance

Ask: *if the typography were stripped from this file (bold removed,
all whitespace collapsed, fonts uniform), would the load-bearing
affordance still be visible?*

If no → move it into the structural layer.
If yes → typography is polish; safe to keep as-is.

## Examples

| Affordance | Typographic only | Structural too |
|------------|-----------------|----------------|
| "This is the entry point" | =bold= the function name | `:CUSTOM_ID: entry-point` + concept-named heading |
| "This section is the canonical doc" | underline / large font | `:PROPERTIES: :CANONICAL: yes :END:` + named anchor |
| "Public API surface" | indent / box layout | `* Public API` heading with `:CUSTOM_ID: api` |
| "Internal helper, don't depend on" | grey out / smaller font | `--` double-dash naming convention + `:CUSTOM_ID: helpers-internal` |
| "Variant of canonical X" | quote block / italic | `** Variant: X` heading with explicit cross-link |

## Anti-patterns

- **Typography is THE signifier**:
  - "I made the API names *bold* so they stand out" — humans benefit;
    agents see no markup difference.
- **Heading text is generic**:
  - `** Functions` — load-bearing role of THIS section (vs other
    sections) is invisible to the agent's triage step.
- **Cross-references rely on heading text**:
  - `[[*Long Heading With Many Words]]` breaks when the heading is
    edited. `[[#stable-anchor]]` survives.

## See also

- `rules/lp-stable-anchors-for-multi-referenced-sections.md` — the
  mechanical rule "≥2 references → `:CUSTOM_ID:`" is one specific
  application of structural-signifier density.
- `rules/lp-cross-file-link-form.md` — org links over bare text is
  another application (structural-link vs typographic-quote).
- `rules/lp-prose-no-self-narration.md` — typographic redundancy
  (e.g. "(see above)" pointing at an immediately-preceding artefact)
  is the same anti-pattern from the prose side.
