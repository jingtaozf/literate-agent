# Agent: Multi-Agent Coordination Through Stigmergic Substrate

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: agent-native phenomena research loop direction G —
> multi-agent emergence in cmux multi-workspace practice. Neither
> classical CSCW (humans) nor coordinated multi-agent AI (Park et
> al 2023) directly cover the case where independent agent
> sessions edit the same repo via git with zero awareness of
> sibling sessions.

cmux runs multiple Claude Code sessions in parallel. Each session
its own context, often editing the same repo. The agents do not
know about each other. Their interaction is *purely stigmergic*
(direction H of the cowork loop) via the shared git artefact.
This rule names the practices that prevent the predictable
failure modes (lock contention, contradictory commits, double-fix
duplication) and exploits the rare upside (emergent labour
division).

## The failure-mode catalogue

Observed across cmux + claude-agent + edo over 6+ months:

| Failure mode | What happens | Cost |
|--------------+--------------+------|
| `git index.lock` contention | Both agents commit simultaneously; one waits or aborts | Low — git handles it |
| Contradictory commits | Agent A edits file X one way, Agent B edits opposite way; second commit wins; first loses work | High — silent work loss |
| Double-fix | Both agents independently fix the same bug; two commits both pass CI but duplicate effort | Moderate — effort doubled |
| Cross-stale-context drift | Agent A reads file, makes mental model, edits hours later; meanwhile Agent B has restructured the file; A's edit lands on stale assumptions | High — partial drift cascades |

The mechanism is *stigmergic*: each agent reads the repo, modifies
it, commits. No direct channel. No awareness of in-flight sibling
work.

## The rule

When multiple cmux workspaces or Claude Code sessions are running
on the same repo simultaneously:

1. *Treat `tasks/todo.md` as the multi-agent coordination
   substrate*. Every active session reads it on start and
   appends an "in flight" entry naming what it's working on.
   Removes the entry on completion or abandonment.
2. *Pre-divide work explicitly whenever possible*. Avoid parallel
   work on overlapping files. The cost of contradictory commits
   exceeds the cost of sequential work; schedule serially when
   overlap is likely.
3. *Read state immediately before editing, not before
   planning*. Time between read and write should be small.
   Agent A reads file at session start, plans for 30 minutes,
   then writes — by then Agent B may have restructured the
   file. Re-read before write.
4. *Treat git index.lock as a coordination signal, not a
   transient error*. When lock contention triggers, the other
   session has in-flight work. Wait and re-fetch before
   retrying; don't retry blindly.

## The exploitation pattern (rare but valuable)

When multi-agent setup IS used deliberately, it can produce
*emergent specialisation* — agents naturally divide labour when
their context contexts happen to differ:

- Agent A sees the Python files (workspace focused on backend).
- Agent B sees the .org files (workspace focused on LP doctrine).
- The codebase gets covered without explicit division because
  each agent works in its visible scope.

The pattern is opportunistic, not designed. Documenting it here
because the alternative (one agent doing everything) wastes
parallelism.

## What the research literature does NOT cover

CRDT literature (Shapiro et al 2011) assumes a *designed
coordination layer* above the data store. Multi-agent AI
literature (Park et al 2023 generative agents) assumes
*agents-aware-of-other-agents*. The LP cowork case is the
*uncoordinated-and-unaware limit*: pure stigmergy via git, no
designed layer, no inter-agent awareness.

This is uncharted territory. The rule's practices are the
*current best understanding* derived from observed failures —
not the *eventually-correct* design. The natural next step is
designing an explicit multi-agent coordination layer (out of
scope here; flagged in `docs/agent-native-phenomena.org`
direction G).

## Tools that help

- `tasks/todo.md` — coordination substrate. Update on
  session start + end.
- `git status` before commit — detect divergence early.
- `git fetch` before push — surface remote changes from
  sibling agents.
- `/lp-cowork-review` command — catches some multi-agent
  artefacts (commits with no `Risk:` declaration, etc.).

## Anti-patterns

- *Long-running agent session on a shared repo without periodic
  re-read*. Stale assumptions silently accumulate.
- *Retry-on-lock without re-fetch*. Wins the lock race but
  commits without the other agent's changes.
- *Treating multi-agent as "more parallelism = faster"*. The
  coordination cost (contradictory commits, double-fixes) often
  exceeds the parallelism benefit.

## See also

- `rules/lp-cowork-handoff-template.md` — single-agent
  cross-session handoff; this rule is the multi-agent
  generalisation.
- `rules/lp-cowork-persistence-stack.md` — `tasks/todo.md` is
  one of the four persistence surfaces; multi-agent makes it
  *the* coordination surface.
- `docs/agent-native-phenomena.org` direction G — research
  characterisation.
- CRDT survey: [Shapiro et al 2011](https://inria.hal.science/inria-00609399v1/document).
- Generative agents: [Park et al 2023](https://arxiv.org/abs/2304.03442).
