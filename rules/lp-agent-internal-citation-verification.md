# Agent: Verify Project-Internal Citations Before Shipping

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: agent-native phenomena research loop direction H — LP
> cowork's hallucination subtype that the general taxonomy (Ji et
> al 2023) does not cover.

LLMs hallucinate. The general taxonomy (Ji et al 2023, =ACM
Computing Surveys=) catalogues intrinsic / extrinsic / factual
subtypes — all checkable against external sources. LP cowork
exhibits a fourth subtype: *LP-internal hallucination* — citations
to project-internal artefacts that don't exist (`RATIONALE.md`
line 42 when no such entry; "per the previous discussion" with no
such discussion; references to project rules with content
different from what's claimed).

LP-internal hallucinations are *more damaging* than external
factual hallucinations because they corrupt the project's own
decision history, and *harder to catch* because verification
requires looking inside the project itself — usually done by the
same agent that hallucinated.

## The rule

Before shipping any agent-authored content that cites a
project-internal artefact (file, section, decision log entry,
prior commit, rule), *verify the citation grounds out*. Two
checks:

1. *Path existence*. The cited file / section / line / commit
   exists.
2. *Content match*. The cited content actually says what's
   claimed.

The verification is *not optional for high-stake content* (per
`rules/lp-cowork-stake-declaration.md`). For low-stake content,
the verification SHOULD happen but failures are recoverable.

## How to verify mechanically

Three approaches in order of reliability:

```bash
# 1. File + section exists (cheapest)
grep -n "^\*\+ <heading>" <file>                 # heading exists
grep -nE ":CUSTOM_ID: <anchor>" <file>           # anchor exists

# 2. Content match (moderate)
sed -n "<line>p" <file>                          # exact line content
grep -A 3 "^\*\+ <heading>" <file>               # heading + body

# 3. Semantic match (most expensive — the agent re-reads and
#    quotes back; if it cannot quote, the citation was
#    hallucinated)
```

The `/lp-cowork-review` command's K4 check does (1) + (2)
mechanically. For (3), the human reviewer asks "quote the cited
section" — if the agent cannot, the citation was generated, not
recalled.

## The hallucination mechanism (why this happens)

Three contributing factors from the research (direction H.3):

1. *Salience bias*. `RATIONALE.md` is salient in `CLAUDE.md`, so
   the agent reaches for it when generating "the rationale for X
   is in Y" patterns — regardless of whether `RATIONALE.md`
   actually contains the rationale for X.
2. *Plausibility filter*. The agent's output passes its own
   plausibility check (the citation *could* exist). No self-
   correction triggers.
3. *Verification cost*. Verifying line 42 requires a `Read` tool
   call. Under generation pressure (long session, multiple
   citations needed), the agent skips verification.

Knowing the mechanism predicts the mitigation: *force the
verification step explicitly*. The plausibility filter is the
weakest link — it cannot distinguish real from generated
citations.

## What counts as "project-internal"

| Citation target | LP-internal? | Verification |
|-----------------+--------------+--------------|
| `RATIONALE.md` line N | yes | Read + line check |
| `lp/<sub>/x.org` section | yes | Read + heading check |
| A specific commit hash | yes | `git show <sha>` |
| A previous chat turn | yes | inspectable in conversation history |
| `Sweller 1988` external paper | no — external | WebSearch (different rule) |
| `the agent we discussed` (no specifier) | suspect | replace with concrete citation or remove |

The "suspect" category is where hallucination is most common:
*vague references that sound like citations but name no specific
artefact*. Treat these as red flags.

## Anti-patterns

- *Citing without quoting*. "Per `RATIONALE.md`'s rejected-
  alternative discussion" with no quoted content — verify or
  reword.
- *Confident vagueness*. "As we discussed earlier in this thread"
  — if the discussion is real, point at the message or quote it.
- *Salience reach*. Citing the most salient file (CLAUDE.md,
  RATIONALE.md, ARCHITECTURE.org) when the actual relevant content
  lives in a deep module section. Verify the file actually
  contains what's being cited.

## Composability with other rules

- `lp-cowork-anti-sycophancy.md` rule 2 (verify citations
  before reviewing) — applies to external citations; this rule
  extends to internal.
- `lp-cowork-review-expectation.md` knowledge-transfer review —
  ironically, agent review's *strength* is catching internal
  inconsistency, which makes hallucination from the same agent
  particularly insidious. Cross-check with a fresh session.
- `/lp-cowork-review` command's K4 check — mechanises this
  rule's verification step.

## See also

- `hints/cowork-failure-modes.org` failure mode 4 (citation
  hallucination) — symptom-side view.
- `docs/agent-native-phenomena.org` direction H — mechanism-side
  view.
- `rules/lp-transfer-discipline-no-weak-metaphors.md` — sibling
  discipline for external citations.
