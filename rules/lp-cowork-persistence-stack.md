# Cowork: The Minimum Persistence Stack

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork chapter — generalises the four-file pattern that
> emerged across claude-agent + edo-literate + cmux long-run practice.

In an LP cowork loop, four persistence surfaces emerged as the
*minimum complete set* of durable state needed to keep human and
agent authors aligned across sessions. Each surface answers one
specific question; missing any one leaks state across the
session boundary.

## The four-file stack

| File | Question it answers | Lifetime |
|------|---------------------|----------|
| `tasks/todo.md` (or equivalent) | *What are we currently working on?* | Per-feature; archived on completion |
| `tasks/lessons.md` | *What mistakes have we already learned to avoid?* | Append-only forever |
| `ARCHITECTURE.org` (or equivalent) | *What is the system shape right now?* | Living; updated whenever shape changes |
| `RATIONALE.md` / `lp/decisions-log.org` | *Why did we make the decisions we made?* | Append-only forever |

A project missing any of the four surfaces has a *predictable failure
mode* in the cowork loop — see the table below.

## Failure modes when a surface is missing

| Missing surface | Failure mode |
|-----------------|--------------|
| `tasks/todo.md` | Agent loses track mid-task; on restart cannot tell what was in flight; redoes work or skips work |
| `tasks/lessons.md` | Same class of mistake recurs across sessions; rule promotions never happen; doctrine doesn't accrue |
| `ARCHITECTURE.org` | Each agent session re-derives the system shape from code; introduces inconsistencies because re-derivation is lossy |
| `RATIONALE.md` / `lp/decisions-log.org` | "Why did we do X?" cannot be answered; agents re-propose rejected alternatives; humans repeat justifications |

The four answer four *orthogonal* questions. None substitutes for
another. A `RATIONALE.md` that includes lessons mixes append-only
decisions with rule seeds and neither stays readable.

## Responsibilities

| File | Human writes | Agent writes |
|------+--------------+--------------|
| `tasks/todo.md` | Initial plan, checks off completed items | Updates inline as work proceeds |
| `tasks/lessons.md` | Adds entries after a human-caught mistake | Appends 4-line entry when a user correction surfaces a pattern |
| `ARCHITECTURE.org` | Major decisions, invariants, extension points | Routine updates to module boundaries, dependency tables |
| `RATIONALE.md` / decisions-log | Major design rationale, "why not X" history | Routine implementation rationale, post-hoc decision capture |

Either party can write to any surface. The split is by *typical
load* — humans write less but make load-bearing entries, agents
write more but for smaller deltas.

## Minimum complete set claim

The claim is that *these four surfaces, used together, cover the
persistence needs of any LP cowork loop*. Stronger requirement:
adding a fifth surface should not produce material improvement
beyond the four-file set.

Test the claim against the four canonical cross-session questions:

1. *What am I supposed to do right now?* → `tasks/todo.md`.
2. *What should I avoid because we already tried it?* →
   `tasks/lessons.md` (mistake patterns) + `RATIONALE.md` (rejected
   alternatives).
3. *What does the system look like?* → `ARCHITECTURE.org`.
4. *Why does it look this way?* → `RATIONALE.md`.

Any cowork question that doesn't decompose into these four either
belongs in the actual LP module's prose (`module.org` preamble) or
is ephemeral session context that need not persist.

## Composability with the handoff templates

The three handoff templates from `lp-cowork-handoff-template.md`
*feed* the persistence stack:

| Handoff | Feeds into |
|---------+------------|
| Plan handoff | Updates `tasks/todo.md` with the current task |
| Result handoff | Appends to `ARCHITECTURE.org` if shape changed; appends to `RATIONALE.md` if a decision was made |
| Failure handoff | Always feeds `tasks/lessons.md`; sometimes also `RATIONALE.md` |

The templates are *write protocols*; the persistence stack is
*storage layout*. Together they form the cowork loop's durable
state machine.

## Concrete examples (where each file lives in actual projects)

| Project | `todo.md` | `lessons.md` | `ARCHITECTURE` | `decisions` |
|---------+-----------+--------------+----------------+-------------|
| claude-agent | `tasks/todo.md` | `tasks/lessons.md` | `ARCHITECTURE.org` | `RATIONALE.md` |
| edo-literate | `lp/draft.org` (proposals queue) | (rolls into draft.org or decisions-log) | per-`lp/<sub>/_project.org` | `lp/decisions-log.org` |

The exact filenames differ; the four *roles* are the same.

## Anti-patterns

- *Mixing roles*: putting lessons inside `RATIONALE.md` because
  "they're both append-only". Lessons are *rule seeds* (template:
  date / mistake / context / rule); decisions are *justifications*
  (template: what was decided / why / what alternatives were
  rejected). Mixing collapses the search shape.
- *No archive of completed todos*: `tasks/todo.md` grows forever,
  agents waste context budget re-reading old items. Move completed
  items to a section/file with a clear cutoff date.
- *Architecture-as-tutorial*: `ARCHITECTURE.org` becomes a friendly
  onboarding doc instead of a structural map. Both have value but
  they answer different questions. Onboarding goes to README.

## See also

- `rules/lp-cowork-handoff-template.md` — the *protocol* that
  populates the four surfaces.
- `rules/lp-cowork-stake-declaration.md` — high-stake changes
  *always* produce a `RATIONALE.md` entry; low-stake usually don't.
- `rules/lp-agent-persistence-hooks.md` — the reader-side analogue
  (what info must persist for cold-start agent readers).
- `rules/design-stays-in-org.md` — design lives in `.org`, never
  in `docs/`; the persistence stack files are exceptions because
  they answer cross-session *process* questions, not design ones.
