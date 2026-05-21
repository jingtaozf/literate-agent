# Cowork: Stake Declaration Before Edit

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork chapter — observed across claude-agent + edo-literate
> + cmux long-run practice; codifies the user's standing
> *risk-tier-self-disclose* discipline as an LP-specific rule.

In an author-author cowork loop where a human and an AI agent both
edit the same LP file, the *stake* of any change must be declared
*before* the edit lands. Stake = "cost of being wrong here." Without
explicit declaration, the human and the agent diverge silently — the
agent treats the section as boilerplate while the human treats it as
load-bearing, or vice versa.

## The rule

Open every cowork reply that proposes a non-trivial change with one
line:

```
Risk: <low|med|high> — <one-clause reason>
```

| Tier | Domain examples | Required process gate |
|------|-----------------|------------------------|
| *low* | docs, comments, tests-only changes, formatter runs, dependency bumps with no behaviour change | proceed directly |
| *med* | business logic edits, refactors inside one module, non-public API changes, new features behind a flag | write a 3-line plan (problem / approach / verification) before editing |
| *high* | auth, payments, migrations, public-API contracts, CI/CD pipeline, deployment scripts, anything in the production hot path, anything that changes how the system fails | enter plan mode; get explicit user approval *before* any Edit/Write tool call |

LP-specific high-tier examples:

- Editing the canonical doctrine rules under `literate-agent/rules/`.
- Changing the four-part section shape across a whole module.
- Restructuring the heading hierarchy of a tangle-bearing `.org` file.
- Modifying the tangle map / build pipeline / hooks.

## When in doubt, default UP

- Unsure between low and med → call it med.
- Unsure between med and high → call it high.

The cost of over-classifying is one extra 3-line plan. The cost of
under-classifying a high-stake change is a production incident *or*
silent doctrine drift in the LP doc itself.

## Why this matters in the cowork loop

The dual-audience-reader research established that LP docs serve
both human and agent readers. The cowork extension adds: LP docs are
also *written* by both populations. Without stake declaration:

- *Stake mismatch*: the agent treats `lp/draft.org` as scratch and
  rewrites prose freely; the human treats it as a negotiated
  proposal and the rewrite eats hours of context.
- *Anti-sycophancy collapses*: the agent's deference defaults to
  "agree with whatever the human wrote," and the human cannot tell
  when the agent has actually thought about the change vs nodded
  through it. Stake declaration forces the agent to mark which way
  it expects to engage.

## Format

Single line, exactly:

```
Risk: high — touches the auth middleware that gates every request.
```

```
Risk: med — refactor inside the cmux backend module, no protocol change.
```

```
Risk: low — typo fix in a docstring.
```

The clause after the dash is *one short clause* naming the
load-bearing reason. Multi-sentence rationale belongs in the
follow-up plan, not the declaration line.

## Enforcement

- *Pre-edit*: agent's first reply to any change request opens with the
  declaration line.
- *PR review*: reviewer rejects a PR whose commit message does not
  carry an implicit-or-explicit stake (the description body must
  reflect the matching gate's content).

## Anti-patterns

- *Sandbagging* — calling everything "low" to skip the plan gate.
- *Inflation* — calling everything "high" to bypass deletion-test
  prose discipline.
- *Stake-as-style* — using the line for emphasis ("Risk: critical")
  instead of the actual decision-cost framing.

## See also

- The user-global `risk-tier-self-disclose.md` rule — this LP rule is
  its LP-specific application.
- `rules/lp-autonomy-levels.md` — maps tier to autonomy L1-L4.
- `rules/lp-cowork-propose-before-edit.md` — what to do *after*
  declaring med or high.
