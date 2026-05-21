# Agent: Long-Horizon Audit Cadence — Schedule Resets Before Degradation

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: agent-native phenomena research loop direction J —
> LP cowork loops degrade over time; periodic audits with the
> existing `/lp-*-audit` commands prevent breakdown but only if
> *scheduled*, not waited-for.

LP cowork loops *degrade*. The degradation is not uniform — some
failure modes accumulate (cumulative sycophancy, convergent
regression, citation hallucination), others reset (per-session
context loss). Without periodic intervention, the loop's quality
falls from baseline. Two breakdown events have already been
observed (=edo-literate= April 2026 rule-violation accumulation;
=claude-agent= late-April Tri-Protocol drift).

The mitigation is *scheduled audit + reset cadence* — not waiting
for failure visible enough to demand attention.

## The rule

Run scheduled audits on a fixed cadence appropriate to the
project's agent-participation rate:

| Agent activity | Audit cadence | Audit scope |
|----------------+---------------+-------------|
| Heavy (multiple agent sessions per day) | Weekly | `/lp-cowork-review` + `/lp-research-audit` on PRs from past week |
| Moderate (few agent sessions per week) | Monthly | Same commands over 4-week range |
| Light (few agent sessions per month) | Quarterly | Same plus prose drift comparison vs 6-month-old snapshot |

The cadence is the *minimum*; running more often is fine. Running
*less* often is the failure mode.

## What the audit catches

Three categories of degradation, each with a corresponding leading
indicator:

1. *Cumulative sycophancy* (research direction A). `/lp-cowork-
   review` K1 check catches "looks good, polish only" review
   patterns. Spike in K1 → sessions are anchoring on prior
   capitulations.
2. *Rule-violation drift* (research directions D + E).
   `/lp-research-audit` catches phase-name headings, missing
   anchors, typographic-only affordances, citation
   hallucinations. Spike → drift outpacing rule reinforcement.
3. *Convergent regression* (research direction E).
   `/lp-cowork-review` K2 check catches project-term replacement
   by generic synonyms. Spike → pretraining attractor
   dominating in-context priors.

## The reset action

When audit surfaces drift beyond the natural rate (varies; track
your project's baseline), reset:

1. *Update rules*. Convert recurring drift patterns into rules
   per the lessons → rule pipeline. The faster patterns promote,
   the slower the underlying dimension drifts (research direction
   J.5).
2. *Refresh sibling examples*. When a rule evolves, update
   visible examples so agents' next-session genre awareness
   catches up (per `lp-cowork-genre-conformance.md` — sibling
   examples are load-bearing).
3. *Trim long files*. Files past ~3000 lines hit
   lost-in-the-middle (research direction C). Split or
   restructure.

## What this rule does NOT prescribe

- A specific calendar tool. Use whatever the project already
  uses for scheduling (calendar reminder, cron, manual ritual).
- A specific audit threshold. Each project's baseline drift rate
  differs; calibrate locally.
- An automated remediation pipeline. The audit *surfaces* drift;
  reset action is human-initiated.

## The cost-benefit framing

Without scheduled audits:

- Drift accumulates silently.
- Two known breakdown events (edo April / claude-agent late-April)
  required substantial recovery (research-grounded reset,
  re-anchoring effort).
- Recovery cost > preventive audit cost.

With scheduled audits:

- Audit run takes minutes (mechanically scriptable via the
  existing commands).
- Drift surfaces early, before it cascades.
- Lessons-to-rule pipeline kicks in at lower latency.

The math favours preventive audits even at high cadence. The
practical limit is *human attention to read the audit output*,
not the audit execution itself.

## Composability with the cowork rule stack

- `lp-cowork-persistence-stack.md`'s `tasks/lessons.md` is the
  rule-promotion pipeline; this rule operates the dial.
- `lp-cowork-anti-sycophancy.md` is the within-session
  mitigation; this rule is the across-session safety net.
- `lp-cowork-genre-conformance.md`'s "evolve genre
  deliberately" — audit catches when the genre has drifted
  enough to warrant deliberate evolution.
- `lp-agent-convergent-regression-defence.md` — audit detects
  the regression this rule defends against.

## Worked example — Q2 2026 first execution

The first execution of this cadence happened 2026-05-21, immediately
after the rule shipped. Findings + process evaluation documented in
`claude-agent/tasks/audit-2026-Q2.md` (commit
[f120f3e](https://github.com/jingtaozf/claude-agent/commit/f120f3e)).

Three calibration findings from that execution worth incorporating
on next-cycle:

1. *C2 raw coverage (=:CUSTOM_ID:= ratio) is misleading*. The rule
   `lp-stable-anchors-for-multi-referenced-sections.md` only requires
   anchors on ≥2-referenced sections. Raw heading-count gives 93-98%
   "missing" which is mostly single-reference sections that need no
   anchor. The load-bearing metric is *coverage on ≥2-ref sections
   only* — needs a cross-reference-aware scan, not raw heading
   counting.
2. *C3 raw count includes literate-org-import auto-generated
   headings*. At depth ≥ 3, Python-statement-per-heading style
   (`*** Function foo`, `*** Assignment X`) inflates the count
   wildly. Filter to depth ≤ 2 (concept-level) for meaningful
   numbers.
3. *K3 raw count is sensitive to file-deletion strips*. The first
   audit found 31 "incident strip" lines in edo-literate — all from
   benign LP-rule-migration where files were *deleted*, not edited
   in place. The `commands/lp-cowork-review.md` K3 check has been
   refined to filter on `--diff-filter=M`.

## See also

- `commands/lp-research-audit.md` — the reader-side audit.
- `commands/lp-cowork-review.md` — the cowork-side audit (K3
  refined 2026-05-21 to skip file-deletion strips).
- `docs/agent-native-phenomena.org` direction J — research
  grounding for why long-horizon breakdown is a real
  architectural risk, not just a hypothetical.
- `claude-agent/tasks/audit-2026-Q2.md` — worked example, first
  execution; top-10 priority list + 4 candidate rule updates.
