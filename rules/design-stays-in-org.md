# Design Stays in the .org File — Not in docs/design-docs/

> *Last-validated*: 2026-05-20
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: claude-agent; the principle generalises beyond that repo.

This repo's `docs/design-docs/` directory was emptied by the
2026-04 LP migration that absorbed every separate design doc into
the relevant `.org` module's Overview / Rationale / Why-X
preamble. Confirmed by CLAUDE.md ("the LP migration emptied
`docs/design-docs/`") and AGENTS.md ("the docs/design-docs/
migration absorbed the historical separate design docs into
LP-style preambles").

This rule **codifies** that one-way migration. Without a rule,
the next contributor who hits a fresh design question will reflex-
ively `mkdir docs/design-docs/` and create a split source of
truth — the exact failure mode the migration fixed.

## The one rule

**New design proposals, decisions, and rejected-alternative notes
live in `.org` files, never in `docs/`.**

Three valid storage points, in order of preference:

| Artefact | Lives in | Format |
|----------|----------|--------|
| New design proposal (under discussion, no consensus) | `claude-agent-draft.org` (create if needed; sibling of the existing module .org files) | Top-level `* <year>-<slug>` section, like edo-literate's `lp/draft.org` |
| Approved design (consensus, ready to implement) | The module's existing `.org` file, inline in the affected section's prose preamble | Prose introducing the trade-off + the rejected alternative |
| Approved cross-module design | The most-affected module's `.org` Overview section, with links to every other section it touches | Prose with `[[file:other.org::#anchor][label]]` cross-references |
| Decision log (chronological "we did X because Y") | `RATIONALE.md` (already exists at repo root) | Append-only timeline |
| Rejected design (closed without merge) | `CODEBASE-REVIEW.org` under a "Rejected" subsection | Move from draft.org with rationale |
| Research / observability snapshot (one-time field measurement) | `RATIONALE.md` under a "Research" subsection | Self-contained note with date + question + measurement |
| Tech-debt backlog | `CODEBASE-REVIEW.org` (already exists) | Prioritised review findings |

## Why

The point of literate programming is *one document that contains
everything about a piece of code* — the prose that justifies it,
the trade-offs, the design decisions, the source itself. Splitting
design between a `docs/design-docs/foo.md` and the `.org`
implementation file defeats the unification:

- **Two docs drift.** Six months from now the `.md` says "we use
  X" while the `.org` actually does Y because someone edited the
  `.org` but not the `.md`. The reader has no way to know which
  is current.
- **One discovery surface.** A reader of `claude-agent-backend.org`
  needs to know about every relevant design decision *while
  reading that file*. A separate `docs/design-docs/backend.md`
  requires a second discovery step the reader rarely takes.
- **The diff carries the design.** When you `git log -p
  claude-agent-backend.org`, you see code + prose change together.
  When design lives separately, the diff is two-file and you have
  to mentally join them.

## What ELSE this rule does NOT allow

- **Do not** create `docs/design-docs/`, `docs/product-specs/`,
  or `docs/references/`. The empty subdirectories were a
  pre-LP-migration relic; the LP migration consolidated them.
- **Do not** create story-scoped `docs/research/<story>/`
  directories during SDD workflow. Research woven into the
  module's Background subsection is the LP-native shape.
- **Do not** add `# Design` headings to README.org — README's
  job is "what is this repo, where do I go next," not design.
- **Do not** create separate `<module>-design.md` siblings to
  `.org` modules.

## Trivial bypass

Genuine `docs/` content is still allowed, **only for**:

- **External user documentation** (the README.org IS in the
  repo root, this is fine — there's no `docs/user-guide/`).
- **Architecture diagrams** as image files (SVG / PNG) — these
  ARE not text and can't live inside an `.org` file. They go in
  `docs/images/` and are linked from the relevant `.org`'s prose.
- **Generated outputs** (tangle products, build artifacts) — not
  authored content.

The test: if a contributor would *write English sentences* to
explain *why the code is shaped the way it is*, those sentences
go into the `.org` file. Not into a `.md`. Not into a `docs/`
subdirectory. The `.org` file IS where design lives.

## Variant — multi-submodule `lp/draft.org` workflow

A meta-repo with many submodules (edo-literate's shape) benefits
from a stricter "no `docs/` folder, period" policy paired with a
dedicated proposal queue file. The storage table tightens to:

| Artefact | Lives in |
|----------|----------|
| New design proposal (no consensus yet) | `lp/draft.org` — single file, top-level `* <year>-<slug>` section per proposal |
| Approved design (consensus, implementing) | The matching `lp/<sub>/<x>.org` alongside the code being changed, as the section's prose preamble |
| Approved cross-submodule design | `lp/<sub>/_project.org` (subsystem level) or a dedicated `lp/<topic>.org` (cross-cutting) |
| Rejected design (closed without merge) | `lp/decisions-log.org` under a "Rejected" subsection |
| Decision log ("we did X because Y") | `lp/decisions-log.org` — append-only timeline |
| Research / observability snapshot | `lp/decisions-log.org` under "Research" subsection |

The proposal-discussion-decision lifecycle becomes:
`lp/draft.org` → `lp/<sub>/<x>.org` (on accept) or
`lp/decisions-log.org` (on reject). The entire intellectual trail
sits in one tree the reader (and the AI agent) can walk.

This variant is stricter than the canonical "design in the relevant
.org" rule above — it pre-commits to having no `docs/` folder *at
all* and treats `lp/draft.org` as the single discussion queue. Use
this variant when the project structure justifies the centralised
proposal file (multi-submodule repos with parallel design streams);
use the canonical "design in the module .org" rule otherwise.

### Onboarding a submodule with existing `docs/`

The deprecation is gradual at the source-repo level. Until each
submodule's `docs/` is empty:

- Treat `repos/<sub>/docs/*.md` as *read-only legacy*. Reference for
  context, do not edit.
- New design that *evolves* a legacy doc starts as a fresh section
  in `lp/draft.org` that summarises the legacy doc's relevant
  context (1–3 lines + a link), then proposes the change. Don't
  fork the legacy doc.
- When a legacy doc's content has fully migrated into `lp/<sub>/`,
  the legacy file can be removed (separate commit, separate review).
