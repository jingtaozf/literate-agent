# Agent: Defend Against Convergent Regression Toward Textbook Patterns

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: agent-native phenomena research loop direction E —
> the convergent regression failure mode identified in cowork
> practice; mechanism characterised as pretraining attractor.

*Convergent regression*: the agent rewrites project-specific
idiomatic prose into textbook-standard patterns. The failure mode
was identified in =hints/cowork-failure-modes.org=; this rule
codifies the mitigation now that the *mechanism* is known.

The mechanism (research direction E.3): *pretraining attractor*.
The agent's generation samples from the pretraining distribution,
which is dominated by generic textbook patterns. Rare patterns
(project-specific terminology, idiomatic conventions) have low
prior probability and get diluted into the median. The drift is
unintentional — the agent is not editing toward any audience; the
regression is a side effect of generation under prior pressure.

## The rule

When editing existing project prose:

1. *Preserve specific terminology by default*. Project terms like
   "comma-escape leading-star" / "boundary object" / "stake
   declaration" / "deletion test" carry the project's specific
   action; replacing with generic synonyms ("escape special
   characters" / "shared interface" / "risk assessment" /
   "concise review") destroys the action.
2. *Preserve incident references and dates*. "Triggering
   incident: 2026-05-21" carries provenance; "based on past
   issues" carries none. The agent must not strip the date / line
   number / commit hash anchor.
3. *Preserve idiomatic markers*. First-person, contractions,
   project slang, asymmetric phrasing — all signals of the
   project's voice. Generic editing strips them; preservation
   defends the voice.

## When generic edits ARE appropriate

The rule is not "never edit toward textbook patterns." It is
"don't do it accidentally." Generic edits are appropriate when:

- The project term IS a textbook synonym and was used
  inconsistently. (Drift correction.)
- A non-project reader will read the section and the project
  term is opaque without explanation. (Audience widening.)
- Both forms exist in the same section. (Disambiguation.)

In all three cases, the edit should be *explicit and announced*
in the proposal step (per `lp-cowork-propose-before-edit.md`),
not slipped into a polish pass.

## How to detect convergent regression mechanically

`/lp-cowork-review` command's K2 check looks for project-specific
phrasing being replaced by generic phrasing in a diff. Specific
heuristics:

```bash
# Project terms whose absence after edit suggests regression
PROJECT_TERMS="comma-escape|deletion test|boundary object|four-part shape|stake declaration"

# Diff hunks that REMOVE these and replace with generic synonyms
git diff <range> | grep -E "^-.*(${PROJECT_TERMS})" | wc -l   # removed
git diff <range> | grep -E "^\+.*(${PROJECT_TERMS})" | wc -l  # added
# If removed >> added, regression is happening
```

## The defending pattern

Three concrete moves the agent (and human reviewer) can use:

1. *Quote, don't paraphrase*. When citing a project term in
   prose, quote it: `"comma-escape leading-star"` in backticks
   or italics signals "this is a project-specific term," and
   the formatting itself defends against regression in
   subsequent edits.
2. *Anchor to incident*. "The 2026-05-21 incident showed X"
   gives the term a load-bearing referent. Generic regression
   that strips the date strips the anchor; reviewer notices.
3. *Cross-reference to the defining rule*. Link the term to the
   rule that introduced it (`rules/lp-comma-escape-leading-
   star.md`). The reference IS the term's authority; preserving
   the link preserves the term.

## Asymmetry with intentional editing

This rule names *unintentional* regression. *Intentional* edits
(refactoring terminology, deprecating an old term) are different
operations and require:

- Declaration in `RATIONALE.md` / `lp/decisions-log.org`.
- Updating all visible examples in one commit (per
  `lp-cowork-genre-conformance.md` — sibling-example
  consistency).
- Updating the defining rule file.

Without those three steps, what looks like intentional
terminology evolution is just regression with a label.

## Composability

- `lp-cowork-anti-sycophancy.md` rule 3 ("defend the human's
  voice when polishing") — this rule extends from voice to
  vocabulary.
- `lp-cowork-genre-conformance.md` — defending project genre
  against drift is the structural-level version of this rule's
  vocabulary-level claim.
- `lp-transfer-discipline-no-weak-metaphors.md` — preserves
  specific transfer claims against vague analogy; sibling
  defence against textbook-attractor drift.

## See also

- `hints/cowork-failure-modes.org` failure mode 3 (convergent
  regression).
- `docs/agent-native-phenomena.org` direction E — mechanism
  characterisation (pretraining attractor wins over linguistic
  anchoring and RLHF register preference).
- `commands/lp-cowork-review.md` K2 check.
