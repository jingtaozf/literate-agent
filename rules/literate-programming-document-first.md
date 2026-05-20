# Literate Programming — Document First

> *Last-validated*: 2026-05-20
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: merged from claude-agent (Elisp-leaning) and edo-literate
> (Python/multi-submodule-leaning) versions; supports both layouts.

**The single most important style rule in any literate-programming
codebase.** `.org` files are documents that happen to contain code, not
source files that happen to have comments. Write the document first;
the code blocks are evidence that backs up the prose. The same
principle applies to non-tangled Python / TypeScript modules — favour
docstrings that explain *why*, not *what*, and prefer module-level
prose over flat function lists.

## Two layouts this rule covers

| Layout | Source of truth | Tangle output |
|--------|-----------------|---------------|
| Single-repo (e.g. claude-agent) | `<module>.org` at the repo root | `python/<pkg>/*.py` or no tangle (literate-elisp loads .org directly) |
| Multi-submodule (e.g. edo-literate) | `lp/<sub>/<file>.org` | `repos/<sub>/<...>.py`, `.ts`, `.rs`, etc. |

Both share the same prose-before-code discipline. Where layout-specific
guidance applies, it's marked below.

## What "document first" means

For every literate `.org` file in the project, the file must justify
its own existence in prose **before the first code block**.

1. **Overview section** — what this module owns, where it fits in the
   lifecycle (loading order, dependencies, role). Cross-link to calling
   modules and to `ARCHITECTURE.org` invariants.
2. **Public API section** when relevant — table of exported symbols /
   classes / functions with one-sentence roles. This is what consumers
   read first.
3. **Section heading + prose preamble before every code block.** Heading
   names a *concept* (`* ACP Handshake`, `* Permission Request Handler`),
   not a phase (`* Functions`, `* Helpers`). Each section opens with 1-3
   sentences explaining *what the code does, why it's shaped this way,
   what trade-off it embodies.*

Code blocks stay short and self-contained. If a block does something
non-obvious, the prose around it explains the non-obvious part. Don't
bury the explanation in `;;` comments — those are for implementation
details, not for the *reason* the code exists.

## Three principles that shape the document

1. **Intent before implementation.** Explain *why* before showing *how*.
   Prose drives the narrative; code blocks illustrate. No "Functions"
   section with no preamble.

2. **One block = one meaningful step.** Each code block does one thing,
   like a paragraph in prose. If a single `#+begin_src elisp` contains
   five unrelated `defun`s, split it — each gets its own section with
   its own 1-3 sentences of "why".

3. **Structure follows narrative logic, not execution order.** Present
   concepts in the order best for a human reader. `literate-elisp` doesn't
   care about order within a file — don't contort the document to match
   definition order.

## What looks right

```org
** Permission Request Handler

Handles `session/request_permission` server-to-client requests from the
agent. Default prompts the user via `completing-read` — C-g sends
`outcome: cancelled`. `claude-agent-acp-auto-approve` flips to legacy
first-option behaviour for trusted sandboxes.

#+BEGIN_SRC elisp
(defun claude-agent-acp--handle-permission (backend request)
  ...)
#+END_SRC
```

Three sentences of prose answer: *what* (handles a specific request),
*why* (default safer than auto-approve), *how to customise* (the
defcustom). A reader who can't run Elisp still understands the intent.

## What looks wrong

```org
** Functions

#+BEGIN_SRC elisp
(defvar claude-agent-acp-auto-approve nil)
(defun claude-agent-acp--handle-permission (backend request) ...)
#+END_SRC
```

No prose, generic heading, multiple unrelated definitions stacked in
one block. Even if the code is correct, the file is **failing as a
literate document**.

## Module Overview — three-part template

Every `.org` module file leads with a `* Overview` section. This is the
durable answer to "what is this module for, and what invariant does it
protect?" — the question a future maintainer (human or agent) asks before
reading 700 lines of code.

Three things to put there, in order:

1. **Motivation paragraph.** What does this module exist to prevent /
   enable? Examples: "Long-lived sessions would accumulate forever without
   this sweeper." "Thin object-oriented wrapper around the cmux CLI."

2. **Invariant paragraph.** What's true about this module that callers
   can rely on? Examples: "Cancel is O(1) and never races with fire."
   "Time-driven, unlike the event-driven heartbeat — handles the
   user-walked-away case hooks can't detect."

3. **Design principles (optional).** 3-5 short bullets when the reasoning
   isn't obvious from the code alone. Present the trade-off considered
   and why this shape was chosen over alternatives.

### Anti-patterns

- **Empty Overview.** `* Overview` followed immediately by `*
  Implementation` with no prose between is the AI default; resist.
  An empty Overview means the next reader recovers intent from code
  alone, which is exactly what the file is for.
- **Prose that restates the type.** "This module defines a `foo` class"
  — the `defclass` says that. Say *why* the class exists.
- **Tutorial that belongs in `docs/`.** The Overview answers someone
  editing this module right now. How to *use* the module from elsewhere
  belongs in `docs/` or `CLAUDE.md`.

## Org files are the design record

Every design decision, tradeoff, open question, and "why not the other
approach" belongs in the module's `.org` file as prose. The org file is
the *only* durable record of *why* the code looks the way it does.

Chat conversations with AI agents, Slack threads, PR discussions are
ephemeral. If the reasoning lives only there, it's lost the next time
someone asks "why is this a cl-defstruct and not a plist?" or "why did
we reject session/load without fallback?"

Each module's `.org` file should carry:

- **Overview** — what this owns and where it fits.
- **Design intent** — why this shape was chosen. One paragraph usually
  suffices; if two approaches were considered, record both and the
  reason for the pick.
- **Rejected alternatives** — one short section per major "why not"
  that would otherwise be rediscovered later. Even one sentence is
  worth keeping.
- **Open questions / TODO** — acceptable in prose, not as bare `TODO`
  comments. Future readers read the prose, not the comments.

When a design conversation happens in an agent chat or PR review, **the
output of that conversation must land in the relevant `.org` file(s)
before the branch merges.** If you can't point at the prose that
captures the decision, it didn't happen.

## Self-check before committing

For each modified `.org` or `.py` file, ask:

1. Does the section heading describe a **concept**, not a phase or
   "Functions"/"Helpers"?
2. Does the prose before each code block answer **why** the code is
   shaped this way?
3. If you stripped every code block and read only the prose, would a
   human still understand the module's role?
4. Is each `defun` / `defclass` / `defmethod` / Python `def` / `class`
   accompanied by a docstring that's a **sentence**, not a label?

If any answer is "no", the file isn't done — keep writing prose, not
more code.

## NEVER-touch list (some enforced by hooks)

- **NEVER** edit any tangle-output file (`.py` / `.ts` / `.rs` etc.)
  directly when the project uses tangle. The PreToolUse hook
  (`block-tangled-edit.sh`) returns exit 2 with a friendly message
  pointing at the owning `.org` section.
- **NEVER** edit `__pycache__/`, `dist/`, `*.egg-info/`, `.cache/`,
  or any other generated tree. They are recreated.
- **NEVER** rename or move an `.org` file without updating any
  `:tangle ../../<...>` headers inside it — paths resolve relative
  to the `.org` file's directory, so a move breaks tangling silently.
- **NEVER** add `:noweb yes` to an Emacs Lisp `#+begin_src` block —
  `literate-elisp` does not expand `<<chunk>>` references at load
  time. (Fine for Python / TS / Rust; those paths use
  `org-babel-tangle` and support noweb.)
- **NEVER** introduce a section heading at depth > 5 in any `.org`
  source — most projects' `make check-structure` will fail.
- **NEVER** open a section that tangles to code with `#+begin_src`
  directly — at least one prose line must come first.
- **NEVER** introduce a bare `*` at column 0 inside `#+begin_src`
  — Org parses it as a headline and silently terminates the src
  block. Use `,*` to escape. The `block-bare-star-in-src.sh` hook
  enforces this.

## File-local-vars line (poly-org users)

When the `.org` source tangles Python via the `literate-org-mode`
package, the file must open with a file-local-vars line so the
tangler picks up the project's formatter (otherwise tangle output
drifts the moment any block diverges from canonical formatting):

```
# -*- Mode: POLY-ORG; indent-tabs-mode: nil; literate-org-py-formatter: ruff;  -*- ---
```

For TypeScript-bearing org files, use
`literate-org-ts-formatter: prettier` (or whatever the matching
submodule's `make format` uses). For Elisp-bearing org files loaded
via `literate-elisp`, no such header is needed — the prose IS the
source.

## Why this matters

- For `literate-elisp` projects: `.org` files load **directly** via
  `literate-elisp-load` — the org file **is** the source of truth.
  There is no separate "tangle" step that strips the prose. When you
  edit a function, you're editing inside its own justification.
- For `org-babel-tangle` projects: the tangled output (`.py` / `.ts`)
  is what runs in production, but the `.org` is what *justifies* the
  code. Without prose discipline, the .py drifts from the .org and
  the design record decays.
- Python / TS modules are read by both humans and AI agents
  continuously. A module-level docstring explaining *why the module
  exists* saves every future reader the archaeology.
- One file = one set of decisions = one readable story.

This style has a cost: writing prose takes time. Pay the cost.
Future you (and reviewers, and other agents) will read every module
multiple times. One extra paragraph at authoring saves hours of
"what does this do?" archaeology later.

## Mechanical org conventions (the boring details that still matter)

Beyond the document-first principles above, four mechanical conventions
keep org sources consistent across the project. Violating them isn't
"wrong" but mixed usage produces files that read inconsistently.

### Heading levels — what each depth means

| Depth | Use for |
|-------|---------|
| `*` | Top-level concept / module section (one per major topic) |
| `**` | Major feature, lifecycle phase, or logical grouping |
| `***` | Specific implementation, helper class, function group |
| `****` | Reach for sparingly — usually a sign the parent should split |

### Block naming

Code blocks rarely need names, but when one is referenced via `:noweb`,
`:tangle`, or in prose, name it with `#+NAME:` and use kebab-case with
a domain prefix: `db-connect`, `api-validate`, `mcp-dispatch-handler`.
Names should read as a natural-language phrase — not `block1` or `helper`.

### Editing existing blocks

- Preserve `#+NAME:` values (they may be cross-referenced).
- When changing a block's behaviour, update the surrounding prose in
  the same edit — stale prose is worse than no prose.
- Maintain top-to-bottom executability: code that runs at load time
  must be defined before the first call site.

### Property inheritance

- Section-level: drop a `:PROPERTIES:` drawer under the heading. Org
  inherits these into descendants automatically.
- File-level: use `#+PROPERTY:` lines in the file header for globals
  (load order, tangle target, default header args).

## Dual-audience reader model

LP files are read by two populations with overlapping needs:

- *Human readers* — saccade-driven (Rayner 1998), perceptual grouping
  (Gestalt), mental model accretion across sessions (Norman 1988).
- *AI agent readers* — token-driven, no perceptual layer, cold-start
  each session (no inter-session memory consolidation).

Optimisations that serve BOTH (the *structural layer*):

- `:CUSTOM_ID:` anchors for cross-reference (recognition surfaces).
- Concept-named headings (foraging proximal cues + signifier vocabulary).
- Prose preambles answering WHY (the designer's mental model made
  explicit).
- Cross-references over plain-text mentions (berry-picking navigation).

Optimisations that serve ONLY humans (the *typographic layer*):

- Whitespace, paragraph length, font weight (saccade economics).
- Visual proximity / Gestalt grouping (perceptual grouping).
- *Bold* / *italic* for emphasis (typographic signifiers).

Rule of thumb: *when the affordance is load-bearing (must be
identified by both audiences), use the structural form*. Typography
is the polish layer on top — fine to add for human aesthetics, but
never the sole carrier of a critical affordance. See
`rules/lp-load-bearing-affordances-structural.md` for the full
4-rule heuristic.
