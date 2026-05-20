# Transfer Discipline — No Weak Metaphors

> *Last-validated*: 2026-05-20
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: research finding (cross-cutting observation #8 — *weak
> metaphors invite overgeneralisation*).

LP doctrine has been built by borrowing from HCI, cognitive science,
and information-retrieval research. Most LP-with-AI rules in this repo
trace back to a canonical HI finding (Pirolli & Card 1999 information
foraging, Sweller 1988 cognitive load theory, Nielsen 1994 usability
heuristics, etc.). The research that produced these rules also
identified the *failure mode* of unconditional borrowing — *weak
metaphors* that look like shared structure but aren't.

## The rule

Before adding a new LP rule that claims a finding "transfers" from
human-interface research to AI-agent reading, verify the claim with
one of two acceptance tests:

1. **Closed-form mathematical core**. The finding has a substrate-
   independent mathematical core that holds for any reader with the
   matching constraint structure. Foraging-economics' Charnov 1976
   marginal-value theorem is the canonical example: `R = G / T`
   optimisation works for ants, web readers, and AI agents alike —
   the math doesn't care about substrate.
2. **Behavioural isomorphism backed by traces**. Direct observation
   that agents demonstrate the same behaviour shape as humans under
   matched conditions, with evidence in actual agent traces. The
   dual-process system-1 / system-2 pattern qualifies: agents
   reading-by-grep produce system-1-like errors (mismatched filenames,
   stale snippets); agents producing chain-of-thought traces produce
   system-2-like outputs. The traces are the evidence.

If neither (a) nor (b) holds, the proposed transfer is a *weak
metaphor*. Document it as a metaphor (the structural resemblance is
real and useful for thinking) but do NOT codify it as a rule that
either reader population must follow.

## Catalogued weak metaphors (do NOT codify)

These resembled real shared primitives but were classified as weak
metaphors by Round-4 verification:

| Surface analogy | Why it's weak |
|-----------------|---------------|
| Gestalt-grouping ≈ transformer attention-head similarity | No closed-form math; no behavioural traces; the substrates are causally unrelated. |
| Retrieval-practice ≈ chain-of-thought reinforcement | Surface resemblance only; no measurement showing the agent's "practice" produces the same retention curve. |
| Working-memory-chunking ≈ context-window compression | Same word ("chunking") for different mechanisms; Miller's chunks are item × interactivity bound, context window is positional-bias bound. |
| Eye-mind hypothesis ≈ attention-weight allocation | Just & Carpenter 1980 requires foveal sampling. Agents have no visual mechanism. |
| Saccade economics ≈ token-by-token cost | Saccade is a discrete jump with parafoveal preview; token processing is sequential with no analogue of parafoveal preview. |

## What does transfer (positive list)

Findings that pass the acceptance tests:

- *Information foraging* (Pirolli & Card 1999) — closed-form
  marginal-value theorem (Charnov 1976).
- *Recognition vs recall asymmetry* (Tulving & Thomson 1973) —
  closed-form measurement: cue-presence reduces retrieval cost.
- *Berry-picking iterative search* (Bates 1989) — closed-form
  decision-structure: candidates are heterogeneous, sampling is
  cheap, stopping rule is "sufficient" not "optimal."
- *Dual-process mode switching* (Kahneman 2011, Stanovich & West
  2000) — behavioural isomorphism with traces (System-1 grep-scan vs
  System-2 chain-of-thought observable in agent runs).
- *Cognitive load element-interactivity* (Sweller 1988) — partial:
  the structural form transfers (interacting items × budget produces
  graceful degradation under overload), the numerical value does not.

## What does NOT transfer (negative list)

Findings whose *every empirical layer* is human-biology specific —
their structural form has no agent-side projection:

- *Eye-tracking + saccades* (Rayner 1998) — every layer biological:
  saccade lengths in visual angle, fixations in milliseconds, regressions
  as percentage of saccades.
- *Gestalt principles* (Wertheimer 1923) — every layer biological:
  retinal sampling rates, grouping radii in degrees.

These remain *human-only optimisations*. The dual-audience implication
is in `lp-load-bearing-affordances-structural.md`: typography is OK
for human polish, but the load-bearing affordance must also exist in
the structural layer.

## What partially transfers (numerical-constants warning)

Some findings have a structural form that transfers but a numerical
constant that does not. The naive port "max 7 items per menu" onto an
agent context window misreads the finding entirely — the agent
context window IS bounded (~10⁵-10⁶ tokens) but the qualitative
implications are *opposite* to Miller's:

- Human reader overwhelmed by 30-item lists; agent absorbs them
  trivially.
- Agent loses fidelity over *thousands* of items by a different
  mechanism (positional bias, lost-in-the-middle).

The correct port: structural form (capacity bounded → graceful
degradation under overload) with a *new number* derived from agent
measurements. The naive copy of Miller's 7±2 to LP design for agents
is a weak metaphor and falls under this rule.

## Author discipline

Before submitting a new LP rule:

1. State the HI finding it borrows from.
2. State which acceptance test it passes — (a) closed-form math,
   (b) behavioural-isomorphism traces, or *neither* (weak metaphor).
3. If neither — DO NOT codify as a rule. Document it as a *thinking
   metaphor* in prose if useful; the structural prescription must
   come from somewhere else.

## See also

- `docs/transfer-gradient.org` — the transfer-gradient figure and
  the catalogue of 6 shared-primitive families, derived from the
  full 50-iteration research loop.
- `rules/lp-load-bearing-affordances-structural.md` — applies the
  positive-transfer findings (F recognition, J signifiers).
- `rules/lp-agent-persistence-hooks.md` — applies the negative
  finding (cross-session state break).
