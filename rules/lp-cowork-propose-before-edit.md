# Cowork: Propose Before Edit (med + high stake)

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork chapter — observed across claude-agent + edo-literate
> long-run practice; same mechanism the user invokes verbally with
> "proposal first before any code".

For any LP change declared as `Risk: med` or `Risk: high` (see
`rules/lp-cowork-stake-declaration.md`), the agent MUST articulate
the proposed change *before* making any Edit/Write/MultiEdit tool
call. The human reads the proposal, raises objections, modifies the
direction, and only then approves.

This is the LP-specific form of plan-mode discipline. It exists
because the agent cannot reliably tell when its own model has
drifted from the human's intent, and the cost of catching the drift
mid-edit is much higher than catching it before the first character
lands.

## The protocol

Pattern by stake tier:

| Tier | Propose-before-edit form |
|------|--------------------------|
| *low* | None. Edit directly. |
| *med* | 3-line plan in the same reply: *problem* / *approach* / *verification*. Then proceed unless the human objects in the next turn. |
| *high* | Enter plan mode. Multi-paragraph proposal. *Wait* for human approval before any Edit/Write tool call. |

The med form is *not* a separate round-trip — it's three lines at
the top of the reply that would have produced the edit anyway. The
human can interrupt before the edit lands (cheaper) or after
(more expensive but still recoverable).

The high form *is* a separate round-trip. The agent's reply names
the proposal and stops. The next message in the conversation comes
from the human.

## The 3-line plan format (med stake)

```
Problem:  one clause naming what's wrong / what's missing.
Approach: one clause naming what the edit will do.
Verify:   one clause naming how we'll know it worked.
```

Example (med):

```
Risk: med — adds a new LP rule under literate-agent/rules/.

Problem:  cowork loops have no codified rule about stake declaration.
Approach: add rules/lp-cowork-stake-declaration.md adapting the
          user-global risk-tier-self-disclose pattern to LP-specific
          high-tier examples.
Verify:   make check-structure passes on the new file; CLAUDE.md
          @-imports it; doc reads cleanly to a human reviewer.
```

The human reads three lines, sees no drift, the agent proceeds in
the same reply with the actual Edit calls.

## The high-stake proposal format

A high-stake proposal is structurally a *design doc embedded in a
chat reply*:

1. *Context* — what's the current state? what changed?
2. *Goal* — what's the desired end state?
3. *Approach* — what's the proposed path? alternatives considered?
4. *Risk* — what could go wrong? blast radius?
5. *Verification* — what convinces us it's correct?
6. *Ask* — what specifically am I asking the human to approve?

Then *stop*. Do not make any tool call that mutates state until the
human replies.

## Why this matters

The dual-process research (E/F/G in the transfer-gradient figure)
shows agents demonstrably switch between fast cue-driven mode and
slow deliberate mode. Cowork failure mode: the agent gets *stuck in
fast mode* when the change deserves slow mode. Propose-before-edit
is a *forced mode switch* — putting the proposal into words triggers
slow mode and surfaces the assumptions the fast pass would have
swallowed.

Symmetrically: the human cannot reliably tell when the agent is in
fast vs slow mode from the output alone. The proposal artefact is
the *visible mode signal* — its presence means slow mode is engaged.

## What counts as "before"

- Reading is fine (Read, Grep, Glob).
- Looking at git state is fine.
- Asking the user clarifying questions is fine.
- Any Edit / Write / MultiEdit is NOT fine until proposal is on
  screen (med) or approved (high).
- Bash commands that *write* are NOT fine. Bash commands that read
  (e.g. `git status`, `ls`, `cat`) are fine.

## Anti-patterns

- *Stealth edit* — declaring `Risk: med` then making 8 tool calls
  in the same reply without a 3-line plan.
- *Performative proposal* — writing a 3-line plan that says
  effectively "I will do what was asked", then doing something
  different. The plan must match the edit.
- *Proposal-as-essay* — multi-paragraph "proposal" on a med-stake
  change that should have been three lines. Wastes the human's
  budget on triage.

## See also

- `rules/lp-cowork-stake-declaration.md` — declaration line that
  gates which form of propose-before-edit applies.
- `rules/lp-autonomy-levels.md` — high-stake = L3 supervised, gate
  is identical to the propose-before-edit gate here.
- `rules/lp-cowork-anti-sycophancy.md` — the agent's propose step
  is also where it surfaces disagreement, not just agreement.
