# Literate Programming — Document First (literate-org)

**The single most important style rule in this repo.** `literate-org.org`
is a document that happens to contain code; `literate_python/*.py` are
generated artefacts. The Python files exist for two readers:
1. Team members who don't use Org-mode and need plain `.py` to consume.
2. Distribution / `pip install` consumers downstream.

For Jingtao (the maintainer), `.org` is the **single source of truth**.
For the team, `.py` remains a legitimate read-and-edit surface.

This split has consequences for AI agents:

- **AI must edit `.org`, not `.py`.** Any Edit/Write/MultiEdit targeting
  `literate_python/*.py` is rejected by a `.claude/hooks/` guard.
- **AI does not need to add `# DO NOT EDIT` headers to .py files** —
  doing so would lie to teammates who legitimately edit those files.
- **When AI changes a tangled module, it edits the org section that
  tangles to it**, then re-tangles via the Emacs flow (or asks the user
  to). Re-tangle output overwrites teammate edits — confirm with the user
  before overwriting if unsure.

Adapted from `~/projects/claude-agent/.claude/rules/literate-programming-document-first.md`,
calibrated for the Python LP runtime in this repo.

## NEVER-touch list (the hook enforces some of these)

The PreToolUse hook in `.claude/hooks/block-tangled-edit.sh` rejects the
first item below. The rest are project-wide rules even where no hook
catches them — agents and humans alike must follow.

- **NEVER** edit `literate_python/*.py` directly. They are tangle
  artefacts; the hook will return exit 2 with a friendly message.
  Edit the corresponding org section in `literate-org.org` instead.
- **NEVER** edit `literate_python/__pycache__/`, `dist/`, `*.egg-info/`,
  `.cache/`, or any other generated tree. They are recreated.
- **NEVER** rename or remove a `:LITERATE_ORG_MODULE:` property without
  also updating its `:tangle` path; the importer keys off the property.
- **NEVER** add `:noweb yes` to an Emacs Lisp src block — `literate-elisp`
  loads `.org` directly and does not expand `<<chunk>>` references at
  load time. (This is fine for Python; that path uses `org-babel-tangle`
  and supports noweb.)
- **NEVER** introduce a section heading at depth > 5 in `literate-org.org`
  — `make check-structure` will fail. Re-examine the surrounding layout
  before adding the deep section; usually a missing sibling layer is the
  real cause.
- **NEVER** open a section that tangles to a `.py` with `#+begin_src`
  directly — it must have at least one prose line first. `make
  check-structure` enforces this.

## What "document first" means

For the master file (`literate-org.org`) and any future companion `.org`
files in this repo:

1. **Module section** owns one Python module
   (`:LITERATE_ORG_MODULE: literate_python.foo`). The section justifies
   its own existence in prose **before the first `#+begin_src python` block**.
2. **Section heading + prose preamble before every code block.** Heading
   names a *concept* (`*** Literate module loader`, `*** HTTP execute
   endpoint`), not a phase (`*** Functions`, `*** Helpers`, `*** Misc`).
   Each section opens with 1–3 sentences explaining *what the code does,
   why it's shaped this way, what trade-off it embodies.*
3. **One block = one meaningful step.** Each `#+begin_src python` block
   is one function, one class, one variable group, or one block of related
   imports. If a block contains multiple unrelated definitions, split it
   — each gets its own subsection with its own "why" prose.

## Four principles that shape the document

1. **Intent before implementation.** Explain *why* before showing *how*.
   Prose drives the narrative; code blocks illustrate. Never open a
   section with `#+begin_src` directly.

2. **Psychological order, not execution order.** Knuth's term: present
   concepts in the order that is *easiest for a human to learn from*,
   not the order the compiler / interpreter / loader needs. The tangler
   reorders by section and `:noweb-ref`, so the document is free to
   teach: introduce the high-level routine first and the helpers it
   calls afterwards, even though Python defines names top-down. If
   reading a section forces the reader to scroll past machinery they
   don't yet care about, the order is wrong.

3. **Structure follows narrative logic.** Hierarchy mirrors how a
   reader builds their mental model: top-level = "what this module
   does", second level = "what concepts make it work", third level =
   "concrete pieces". Before adding any new heading, look up — is the
   surrounding hierarchy still readable, or are you drilling deeper
   because each step felt locally reasonable while the global layout
   decayed? `make check-structure` flags depth > 5 as a guardrail
   (see "Structural shape" below); use the warning as a prompt to
   re-examine layout, not as a number to chase.

4. **Org files are the design record.** Every design decision, tradeoff,
   open question, and "why not the other approach" belongs in
   `literate-org.org` as prose. Chat conversations and PR threads are
   ephemeral. If you can't point at the prose, the decision didn't happen.

## Structural shape (enforced by `make check-structure`)

The lint exists to catch the AI failure mode of drilling endlessly
into a deep hierarchy because each individual addition feels reasonable
in local context, while the global layout silently becomes
incomprehensible. *Depth is not the rule.* The rule is: every section
should sit where the reader's mental model puts it, and the reader's
mental model breaks long before line 6 of indented asterisks.

- **Section nesting depth ≤ 5 — guardrail, not target.** When the lint
  fires, *do not raise the cap*. Step back and look at the surrounding
  hierarchy: is a sibling layer missing? Is the parent a grab-bag that
  forced this depth? Did the AI agent narrowly drill into one concept
  without zooming out? Often a single rename or a flat sibling section
  removes the depth complaint without losing structure. The cap is at
  five (not three or four) so the lint stays out of the way of
  legitimate hierarchy; *exceeding* it is the signal something is
  wrong, not the strict bound itself.
- **Forbidden grab-bag headings.** Section titles matching
  `^(Functions|Helpers|Utilities|Misc|Things|Stuff)\s*$` are rejected.
  Name the *concept*, not the phase. A grab-bag heading is the most
  common driver of accidental over-nesting: agents put all "the rest"
  under it, and then nest specifics inside it because there's nowhere
  else to put them.
- **Prose before code.** A section with a `:tangle ./literate_python/*.py`
  property must have at least one non-empty prose line between the
  heading and the first `#+begin_src` block. The prose is what tells a
  human reader (or another agent) why the section exists at all.

## NL outline for long functions

Borrowed from *Natural Language Outlines for Code* (Shi et al., FSE'25,
arXiv:2408.04820): when a Python function body exceeds **40 lines**, add
inline `# # <one-clause summary>` comments that partition the body into
narrative steps. Each summary covers ≥3 source lines; one-line dec­ora­tive
summaries are forbidden.

```python
def parse(s: str) -> Ast:
    # # Tokenise input into a stream of tokens.
    tokens = tokenize(s)
    # # Build a parser over the token stream.
    p = Parser(tokens)
    # # Drive the parser to AST; ParseError propagates.
    return p.parse_program()
```

This is *in addition to* the surrounding prose in the org file — not a
replacement. Module-level "why this exists" stays in org prose;
function-internal "what each block does" goes into the NL outline.

## Self-check before committing

For each modified `.org` section, ask:

1. Does the heading describe a **concept**, not a phase?
2. Is there at least one prose line between the heading and the first
   `#+begin_src`?
3. If you stripped every code block and read only the prose, would a
   reader understand what the module does and why it's shaped this way?
4. Is each `def` / `class` accompanied by a docstring that's a
   **sentence**, not a label?
5. Function ≥ 40 lines? NL outline present?
6. Section depth ≤ 5? If not, did you check whether the surrounding
   layout has a missing sibling layer or a grab-bag parent before
   adding the deep section?

If any answer is "no", the file isn't done — keep writing prose, not
more code.

## Auto-tangle lifecycle

Tangling (`.org` → `literate_python/*.py`) is automated; you do not need
to invoke `make tangle` manually in normal flow.

Two routes converge on the same Emacs function `literate-org-tangle-buffer`:

1. **Claude edits a `.org` file via `Edit` / `Write` / `MultiEdit`** —
   the PostToolUse hook `.claude/hooks/tangle-org-buffer.sh` fires. It
   asks the host Emacs (via `emacsclient`) to call
   `(literate-org-tangle-by-path PATH)`, which loads the file (or finds
   the existing buffer), reverts if disk has been changed externally
   while the buffer is clean, and tangles. If the host Emacs is
   unreachable, the hook falls back to `make tangle FILE=…` (`emacs
   --batch`).

2. **Anyone saves a `.org` buffer in Emacs** (you with `C-x C-s`, or an
   `emacsclient -e '(save-buffer)'` call from another agent path) —
   `literate-org-mode` has `literate-org-tangle-buffer` registered on
   `after-save-hook`, which tangles every code block in the buffer.

The two routes are idempotent and may overlap (`Edit` on disk *and* the
file being open in Emacs); the result is the same on-disk `.py` either
way.

### What this rule asks of you (the agent)

- **Do not call `make tangle` manually** unless the hook reports failure.
- **Do not edit `literate_python/*.py` directly** — the PreToolUse hook
  rejects it, and the next tangle would overwrite anyway.
- **If you edit a `.org` file via `mcp__emacs__evalElisp`**, end the
  elisp with `(save-buffer)` so the after-save-hook fires. Otherwise
  the `.py` falls behind the buffer and only resyncs on the next disk
  save.
- **If the hook reports a dual-writer conflict** (`buffer is modified
  and disk has changed externally`), stop and surface the conflict.
  Do not paper over it — that means the user has unsaved changes in
  Emacs that would be lost by an automatic resync.

### Escape hatch

`LITERATE_ORG_NO_AUTO_TANGLE=1` in the environment skips the PostToolUse
hook entirely. Use during bulk patches where per-edit tangle would be
wasteful, or when debugging the hook itself.

## Why this matters specifically here

- `literate-org.org` is **3000+ lines** and growing. Without strict
  document-first discipline it degenerates into "marked-up source".
- AI agents (this one included) read the master file repeatedly and
  reason about what to change. Prose-first sections are AI-readable
  intent — agents that have to infer intent from code make worse edits.
- The project itself implements LP infrastructure (custom module loader,
  HTTP server). Eating our own dog food is the only credible
  demonstration that the system is worth using.

This style has a cost: writing prose takes time. Pay the cost. The
codebase is small enough that future-you and future agents will read
every module dozens of times. One paragraph at authoring saves hours
of "what does this do?" archaeology later.
