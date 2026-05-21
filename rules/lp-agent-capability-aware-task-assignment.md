# Agent: Capability-Aware Task Assignment Across Model Families

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: agent-native phenomena research loop direction F —
> LLM families exhibit different capability profiles; literate-
> agent doctrine has been implicitly calibrated for Claude.

Different LLM families (Claude, GPT, Codex, Gemini, opencode,
local models) exhibit different capability profiles in LP cowork.
Claude tends strong on prose discipline + long-context coherence;
GPT-4 strong on structural refactor; Codex-lineage strong on
tangle-output verification; Gemini varies. Treating "the agent" as
monolithic loses information.

literate-agent doctrine has been calibrated against Claude
without explicit consideration. Migrating to another family
produces different cowork outcomes. This rule names the practice
of *matching task to family strength* — and the limits of doing
so given the small N of cross-family observations.

## The rule

When task assignment is under your control (multi-agent cmux
workspace, per-task model selection), match the task to the
family's strength:

| Task type | Strongest family observed |
|-----------+----------------------------|
| Prose discipline (deletion test, voice preservation) | Claude (Sonnet/Opus) |
| Structural refactor (cross-file rename, protocol restructure) | GPT-4 / Claude |
| Tangle / code-generation verification | Codex-lineage / Claude |
| Citation lookup + verification | (no strong differentiation observed) |
| Multi-file knowledge transfer review | Claude (long-context strength) |
| Bulk mechanical edits (formatter passes, ext renames) | (any — task is below capability threshold) |

The observations are *suggestive, not empirical*. HELM (Liang et
al 2022) provides systematic cross-family benchmarks but not on
LP-cowork-specific tasks. The above table is a working hypothesis
informed by 6+ months of mixed-family practice in cmux.

## When task assignment is NOT under your control

Most cowork sessions use a single family for the whole session
(whatever the launcher configured). The rule still applies, but
indirectly:

1. *Adjust expectations* against the deployed family's profile.
   If Claude is the deployed agent, expect strong prose + weak
   structural-refactor; the reverse for GPT-4.
2. *Use cross-family review for high-stake decisions*. If both
   Claude and GPT-4 are available (e.g. via separate cmux
   sessions), have one make the change and the other review.
   Capability heterogeneity becomes a feature — orthogonal
   strengths catch each other's blind spots.

## Honest hedge: the small-N problem

The capability-profile claims in this rule rest on observational
data from a small N (3 reference projects × few-per-week
multi-family runs over 6 months ≈ ~50 cross-family observations).
The pattern is robust enough to act on but not robust enough to
codify as definitive. The honest framing:

> *Treat these as priors to be updated, not facts to enforce.*

If your project's experience contradicts this rule's mapping,
trust your data over this rule.

## What this rule does NOT claim

- That one family is universally "better." Each has strengths.
- That family choice substitutes for the cowork rules. The
  =lp-cowork-*= rules apply regardless of family.
- That capability profiles are stable across model versions.
  Claude 3.5 vs 3.7 vs 4.5 will differ; the rule's specific
  family-to-task mapping needs re-validation as models evolve.

## Operational practices

1. *Document the deployed family in commit messages or PR
   descriptions* when relevant. "Authored by Claude Sonnet 4.5"
   helps future code archaeology understand which family's
   blind spots may be present.
2. *Build family-specific addendum rules* under
   =literate-agent/hints/= if observed patterns are strong
   enough. Today: just `dual-audience-checklist.org` + language
   hints; tomorrow: maybe `hints/claude-cowork-notes.org` /
   `hints/gpt-cowork-notes.org` capturing family-specific
   tendencies.
3. *Cross-check on high-stake commits*. The blast radius of an
   agent-introduced mistake is worth a second family's eyes on
   it, especially when the first agent's family-typical failure
   mode aligns with the change's risk surface.

## See also

- `docs/agent-native-phenomena.org` direction F.
- `rules/lp-cowork-stake-declaration.md` — high-stake gating
  applies regardless of family.
- HELM (Liang et al 2022): [arXiv:2211.09110](https://arxiv.org/abs/2211.09110).
