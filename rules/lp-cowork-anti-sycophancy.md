# Cowork: Anti-Sycophancy in Prose Review

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork chapter — addresses a drift mode unique to
> author-author mode that does not arise in reader-only research.

In an LP cowork loop, the human writes prose, the agent reviews
prose, and vice versa. The default agent behaviour is to *agree*
with whatever the human wrote — accept the prose, polish for style,
maybe suggest a clarification, but rarely push back on the substance.
That default is *sycophancy* and it silently encodes errors into the
LP doctrine.

This rule names sycophancy as a cowork failure mode and prescribes
explicit countermeasures.

## What sycophancy looks like in LP cowork

| Symptom | Underlying drift |
|---------|-------------------|
| Agent reviews 200-line section, returns "looks good, minor polish suggestions" | Slow mode never engaged; agent fast-passed the diff |
| Agent agrees with a `Risk: low` claim that's actually `Risk: med` | Stake declaration accepted at face value |
| Agent accepts a "rejected alternative" line that misstates why the alternative was rejected | Plausibility check skipped |
| Agent reviews a rule citing Pirolli 1995 and never checks if the citation is real | Verification step skipped |
| Agent rewrites human's idiomatic prose into "standard" textbook patterns | Convergent regression — taste is human's domain |

The common shape: the agent's output reads like a review but the
agent never actually engaged the disagreement question. The
artefact passes through unchanged or improved-on-surface only.

## The rule

When reviewing human-authored prose, the agent MUST:

1. *Enumerate at least one specific point of disagreement, doubt, or
   uncertainty* — even if minor. "Nothing to add" is not an
   acceptable review output unless the agent has actually re-derived
   the claim itself.
2. *Verify citations and concrete claims*. If the prose cites
   "Sweller 1988" or "Nielsen 1995", the agent runs a check
   (WebSearch or a search through known reference cache) and reports
   whether the citation grounds out. If the prose says "this code
   was tested with 5000 records", the agent looks at the test
   matrix.
3. *Defend the human's voice when polishing*. Do not rewrite
   idiomatic phrasing into textbook patterns. The taste judgment
   stays with the human author. The agent's edit budget goes to
   *clarity* and *deletion test* (eliminating low-information
   prose), not *normalisation*.
4. *Mark stake disagreement explicitly*. If the human declared
   `Risk: low` and the agent thinks it's `Risk: med`, the agent
   says so before doing the edit, not after.

## The disagreement-or-derived rule

The simplest single test:

> *Either the agent surfaces a specific concern, OR the agent has
> re-derived the prose's central claim from primary sources.*

If neither, the review output is sycophancy and must not ship.

This applies symmetrically: the *human* reviewing agent-authored
prose should apply the same standard. But agent-side sycophancy is
the more common failure mode because the agent's pretraining biases
it toward agreement; humans naturally push back when they disagree.

## Format for surfacing disagreement

Use a fixed section:

```
## Review

Agreement: <one-clause statement of what's solid>
Concerns:
  - <specific concern 1, with line/file reference>
  - <specific concern 2, ...>
Citations checked: <which ones, what came back>
Stake reassessment (if any): <"agree with declared low" or "I'd call this med because ...">
```

If `Concerns` is empty AND `Citations checked` shows nothing, the
review is structurally suspect — either the prose is trivially
correct (low stake; no review needed) or the agent skipped slow mode.

## Why this matters

Cowork is a *negotiation* between human and agent authors over what
the LP doctrine should say. Sycophancy collapses the negotiation —
the agent always concedes, the human's first draft becomes the
final draft, and errors that should have been caught in review
become canonical. Over enough cycles, the LP doc accumulates
unchecked claims and the doctrine's authority erodes from inside.

The dual-process research frames this: the agent's *deference*
default IS its System-1 mode applied to the social dimension of
review. Forcing the enumerate-disagreement step is the System-2
analogue of *propose before edit* (= forced slow mode for write).

## Anti-patterns

- *Hedged sycophancy*: "I think this is mostly right but you might
  want to consider..." — the structural concern remains unstated.
- *Style-only critique*: rewriting prose without engaging the
  claim it makes.
- *False symmetry*: agent fabricates a "concern" to satisfy the
  rule, then immediately resolves it. The concern must be real.

## Calibration

The rule is *not* asking the agent to manufacture disagreement. It
is asking the agent to *not declare review complete* until either a
real concern was surfaced or a primary-source re-derivation was
done. If neither is possible, the honest output is:

> "I read the prose. I do not have an independent way to verify
> the central claim. Treating my review as a syntax / style pass
> only; the substance still needs human judgment."

That is *not* sycophancy — it's an explicit limit of the agent's
review, and the human can act on it.

## See also

- `rules/lp-cowork-stake-declaration.md` — stake reassessment is part
  of the review contract.
- `rules/lp-cowork-propose-before-edit.md` — propose step IS where
  the agent surfaces concerns about the request itself.
- `rules/lp-prose-no-self-narration.md` — the deletion test is the
  agent's main *clarity* tool; this rule is its complement for
  *substance*.
- `rules/lp-transfer-discipline-no-weak-metaphors.md` — citations
  the agent must verify if the prose claims a HI finding transfers.
