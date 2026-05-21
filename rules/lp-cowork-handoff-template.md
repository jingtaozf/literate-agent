# Cowork: Handoff Templates Across Sessions

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork chapter — addresses the cross-session state
> persistence transfer-break (observation #1 of the transfer-gradient
> research) on the *authoring* side rather than the *reading* side.

The agent has no inter-session memory. Every cowork session starts
cold. Whatever context survives must live in the LP file or in
companion files the agent can re-find on cold start. This rule
prescribes three fixed handoff templates for the three transition
points where state must move across the human-agent boundary.

## The three handoff points

| Transition | Direction | Template |
|------------|-----------|----------|
| *Plan handoff* | human → agent | `<task>: <goal>; <constraints>; <rejected alternatives>` |
| *Result handoff* | agent → human | `did: <what>; verified: <how>; deferred: <what>; surprises: <if any>` |
| *Failure handoff* | agent → next-agent-session | append to `RATIONALE.md` / `lp/decisions-log.org` |

All three templates exist because *the receiving end may be a fresh
session that knows nothing about the prior turn*. Even the
"next-agent-session" line applies symmetrically when the human
returns days later and has forgotten the context.

## Plan handoff (human → agent)

When the human asks for a non-trivial change, the *complete* request
fits this shape:

```
<task>:        <one-clause goal>
<constraints>: <budget, risk class, files in scope>
<rejected alternatives>: <what NOT to do, with reason>
```

Example:

```
Task:         Add a CLT-grounded "one new mechanism per section" rule
              to literate-agent.
Constraints:  Risk: med. Touches rules/lp-module-section-hierarchy.md
              only. Must reference Sweller 1988 with primary-source
              citation.
Rejected:     Do NOT add a new top-level rule file — fold into the
              existing hierarchy rule as a "Why this works" section.
              A separate file would re-litigate where hierarchy lives.
```

The agent can act on this without re-asking. Without the rejected
alternative, the agent may build the wrong scaffolding before the
human catches it.

## Result handoff (agent → human)

When the agent finishes a unit of work, the *complete* report fits
this shape:

```
did:       <what shipped, with file/line citations>
verified:  <which checks ran, what passed/failed>
deferred:  <what was in scope but didn't ship, why>
surprises: <anything the user didn't expect, if any>
```

Example:

```
Did:       Added "Why one new mechanism per section" section at the
           bottom of rules/lp-module-section-hierarchy.md (lines 230-258).
Verified:  CLAUDE.md @-import still resolves; cited Sweller 1988
           Cognitive Science 12(2) verified via WebSearch.
Deferred:  Did NOT update the audit script to detect violations of
           this new rule — out of scope. Filed as follow-up.
Surprises: The existing hierarchy rule already had a related
           paragraph at lines 110-130; collapsed into one to avoid
           redundancy.
```

This is the agent's *trace* into the next session. If the agent gets
restarted before the human responds, the next session reads this
report and knows where to pick up.

## Failure handoff (agent → next-agent-session)

When the agent abandons an approach, the *failure trace* gets a
permanent home in the LP file system:

| Location | Use |
|----------|-----|
| `RATIONALE.md` / `lp/decisions-log.org` | "we tried X, it failed because Y, we did Z instead" — append-only timeline |
| `tasks/lessons.md` | one-shot mistake worth capturing as a future rule |
| The relevant module's `* Overview` prose | tacit invariant the next reader needs to know |

The agent appends a 4-line entry to `tasks/lessons.md` (per the
user-global pattern):

```
Date:    YYYY-MM-DD
Mistake: <what went wrong, one line>
Context: <what triggered it>
Rule:    <preventive principle, one line>
```

The 4-line cap is intentional — narrative belongs in the LP module
prose, not in lessons. Lessons are *rule seeds*, not stories.

## Why fixed templates

Without templates, every cowork session re-invents the handoff
shape. The agent's context-window budget gets spent on re-deriving
"what does the user want / what did I just do?" instead of on the
substance. Templates compress the handoff to predictable structure
that both populations parse in constant time.

The reader-side research showed `:CUSTOM_ID:` and concept-named
headings are recognition surfaces for cross-reference. These three
templates are the *authoring-side analogue* — recognition surfaces
for cross-session state transfer.

## Composability with stake declaration

For `Risk: low` changes, the templates simplify:

- Plan: a single sentence is enough.
- Result: "done; tested via `make test`."
- Failure: usually no failure to capture.

For `Risk: high` changes, the templates expand:

- Plan: the full propose-before-edit proposal IS the plan handoff.
- Result: matches the proposal's "ask" section item-by-item.
- Failure: anything that ships incomplete gets a `lp/decisions-log.org`
  entry, not just a `tasks/lessons.md` one.

## Anti-patterns

- *Implicit handoff*: "Let me know if you have any questions" —
  shifts the discovery burden to the human. Use the result template
  to surface unknowns proactively.
- *Run-on plan*: 200-line plan that the agent must re-read on each
  turn. Compress to the 3-field template; details live in the LP
  file the plan modifies.
- *Failure swallowed*: agent abandons an approach mid-session and
  the next session has no trace. Always append to lessons / decisions
  before context closes.

## See also

- `rules/lp-agent-persistence-hooks.md` — sister rule on the
  *reading* side of the same persistence concern.
- `rules/lp-cowork-stake-declaration.md` — stake gates which template
  form applies.
- `rules/lp-cowork-persistence-stack.md` — the four-file durable
  state surface that handoffs feed into.
