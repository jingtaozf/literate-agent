# Cowork: Review Expectations Are Knowledge Transfer, Not Defect Finding

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork research loop direction D — derived from Bacchelli
> & Bird 2013's empirical finding on the expectation-outcome gap in
> code review, mapped to LP cowork's specific capability profile.

When a reviewer (human or AI agent) reviews a diff or section in an
LP cowork loop, the *dominant realised outcome* is knowledge
transfer + style enforcement + design improvement — NOT defect
finding. This is not a model-capability gap to be closed; it is a
structural property of review observed empirically across software
engineering and replicated in LP cowork practice. Calibrate
expectations accordingly.

## The empirical anchor

Bacchelli & Bird 2013 (=ICSE 35th=) surveyed 165 developers and
interviewed 17 at Microsoft. Czerwonka et al 2015 analysed 24,000+
review threads at the same scale. Both converge:

| Stated purpose of review | Realised dominant outcome |
|--------------------------+----------------------------|
| Find defects             | Knowledge transfer (catching inconsistency with prior decisions, surfacing rejected alternatives) + style enforcement + design improvement |

The gap is robust across teams, languages, and review tooling. It
is a *property of the review activity*, not a deficiency to fix.

## Agent reviewer capability profile

LP cowork practice shows the agent reviewer's capability profile is
asymmetric in a way that *aligns with* the realised outcome rather
than the stated purpose:

| Task | Human reviewer | Agent reviewer |
|------+----------------+----------------|
| Defect finding ("this logic has a bug") | strong — runtime intuition + experience | weak — no runtime, no execution anchor |
| Knowledge transfer ("this contradicts RATIONALE.md line 42") | strong but costly — re-reads history | very strong — uniform recall cost per token |
| Style enforcement ("section missing :CUSTOM_ID:") | medium — manual lookup | very strong — mechanically checkable via `/lp-research-audit` |
| Design improvement ("this abstraction is leaking") | strong — taste-driven | medium — risks convergent regression toward textbook patterns |

The agent reviewer is *categorically stronger than the human* on
knowledge transfer and style; *categorically weaker* on defect
finding. Measuring agent review against defect-finding parity
systematically under-values its actual contribution.

## Operational implications

1. *Frame the review request to match capability*. Asking the agent
   to "find bugs" produces weak output. Asking it to "check this
   PR against RATIONALE.md and the lp-* rules" produces strong
   output. The framing is the lever.
2. *Do not measure agent review by defect count*. Bacchelli's gap
   says defect-finding is a tertiary outcome even for skilled
   human reviewers. Holding the agent to a metric humans don't
   meet either is structurally unfair.
3. *Combine review modes*. Use the agent reviewer for knowledge
   transfer + style; reserve human review for defect finding +
   design judgment. The two reviewers cover non-overlapping
   territory; their union is stronger than either alone.

## Anti-pattern

Reading agent review output, finding no bug callouts, concluding
"agent review missed everything." The agent's review value was
elsewhere — in the line that said "this contradicts the
rejected-alternative decision in `RATIONALE.md`" or "this
section's heading is a phase-name not a concept." Look there.

## Symmetry with the anti-sycophancy rule

`rules/lp-cowork-anti-sycophancy.md` forces the agent to surface
≥1 specific concern. This rule says *what those concerns should
look like*: knowledge transfer issues, style violations,
design-consistency observations — not defect-finding speculation.
The two rules compose.

## See also

- `rules/lp-cowork-anti-sycophancy.md` — forces the agent to
  produce specific concerns in review.
- `docs/cowork-research.org` — full research synthesis including
  direction D's Bacchelli-gap derivation.
- `commands/lp-cowork-review.md` — mechanises the audit; K1 check
  detects the "looks good, polish only" pattern that hides
  capability mismatch.
