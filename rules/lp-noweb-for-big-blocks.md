# Use Noweb References to Split Big Classes / Functions

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

When a Python class or top-level function in an `lp/<sub>/<x>.org`
source exceeds **~80 lines**, split it across multiple `#+begin_src`
blocks using Org-Babel's *noweb* references. The reader gets a
section per logical method/concept with its own prose preamble; the
tangler stitches them back into a single class body.

Adapted from skill-scout-server's `lp-noweb-for-big-blocks.md`. The
only meta-repo difference: the `:tangle` path on the skeleton block
is `../../repos/<sub>/<...>/<file>.py` instead of `../<pkg>/<file>.py`.

## Required setup at file scope

`#+PROPERTY: header-args :results silent :session :noweb yes :tangle no`

Per-section `:tangle ../../repos/<sub>/<...>.py` overrides the
file-level `:tangle no`.

## The pattern (per class or large function)

> The noweb-ref MUST be inside `:header-args:` (not a standalone
> `:noweb-ref:` property), and the skeleton block MUST explicitly carry
> `:noweb yes` (the parent's `:header-args:` *replaces* the file-level
> one, so file-scope `:noweb yes` does not propagate to the skeleton).

```org
*** =SomeBigClass=
:PROPERTIES:
:CUSTOM_ID: <sub>-some-big-class
:header-args: :tangle no :noweb-ref SomeBigClass-body
:END:

(prose intro for the class as a whole)

#+begin_src python :tangle ../../repos/<sub>/<...>/<file>.py :noweb yes :noweb-ref ""
class SomeBigClass:
    """Docstring for the class."""

    <<SomeBigClass-body>>
#+end_src

**** =__init__= — wire up dependencies

(prose for the constructor)

#+begin_src python
def __init__(self, ...):
    self._x = ...
#+end_src

**** =evaluate= — main entry point

(prose for evaluate)

#+begin_src python
async def evaluate(self, ...):
    ...
#+end_src
```

Key rules:

1. **Parent (class-level) section** declares the chunk name and the
   no-tangle-by-default in **one** property line:
   `:header-args: :tangle no :noweb-ref SomeBigClass-body`. (Org-mode
   only inherits header-args sub-keys via `:header-args:`; a
   standalone `:noweb-ref:` PROPERTY-drawer line is NOT seen by
   org-babel-tangle.)
2. **Skeleton block** is the only one with a real `:tangle <path>`.
   It uses `:noweb-ref ""` (empty string) to opt out of inheritance.
   It contains the class envelope and `<<SomeBigClass-body>>` as the
   placeholder. **It also needs `:noweb yes` explicitly.**
3. **Method blocks** inherit `:tangle no :noweb-ref SomeBigClass-body`
   from the parent's `:header-args:`, so each one *appends* its
   contents to the chunk and does not tangle directly.
4. **Method block content is at column 0** in the .org. The skeleton's
   `<<SomeBigClass-body>>` placeholder sits at indent 4 (one level
   inside `class SomeBigClass:`), and Org-Babel's noweb expansion
   re-indents the chunk contents to match.
5. **Method-to-method blank lines are added by `ruff format`** at the
   end of `make tangle`. Org-babel concatenates noweb chunks with no
   inter-chunk separator.

## When to apply

Triggers:

- Class body > 80 lines.
- A class that mixes setup / public API / helpers in a way the prose
  wants to discuss separately.
- A long pure function (> 60 lines) whose body has natural narrative
  partitions — split via noweb the same way (skeleton with
  `<<func-body>>` placeholder).

Do NOT apply to:

- Small classes (< 30 lines) — single-block is more readable.
- A class whose methods are all 5-line one-liners — splitting buys
  nothing.
- Module-level helper functions clustered around one concept — they
  can stay in one src block under one section.

## Verification

```bash
make tangle FILE=lp/<sub>/<x>.org
git -C repos/<sub> diff --stat    # MUST be empty for unchanged-intent edits
```

A non-empty diff means either:

- The skeleton's `<<chunk>>` placeholder isn't at the right indent.
- A method block's content has wrong indent at column 0 in the .org.
- A method got reordered relative to the original .py declaration
  order (noweb expands chunks in source-document order).
- `:noweb yes` is not set at file scope.

When debugging, run `org-babel-expand-noweb-references-and-assignments-in-buffer`
in Emacs to see the post-expansion text without tangling.
