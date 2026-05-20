# Module Section Hierarchy in Literate `.org` Files

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate (`lp/<sub>/*.org` convention); examples use
> Python-LP shape, the principle generalises to any literate language.

## File-level skeleton (always start here)

Every `lp/<sub>/<x>.org` opens with this fixed prologue:

```org
# -*- Mode: POLY-ORG; indent-tabs-mode: nil; literate-org-py-formatter: ruff;  -*- ---
#+TITLE: <Module concept> (=<sub>.<pkg>=)
#+OPTIONS: tex:verbatim toc:nil \n:nil @:t ::t |:t ^:nil -:t f:t *:t <:t
#+STARTUP: noindent
#+PROPERTY: literate-lang python
#+PROPERTY: literate-load yes
#+PROPERTY: literate-insert-header no
#+PROPERTY: header-args :results silent :session :noweb yes :tangle no

* Table of Contents                                            :noexport:TOC:

* Why this module exists
…
```

The `* Table of Contents :noexport:TOC:` heading is the **toc-org**
sentinel — when the maintainer saves the buffer in Emacs, toc-org's
`before-save-hook` regenerates the TOC list under that heading
automatically. AI agents do NOT need to populate the TOC themselves.
Just leave the heading as-is.

---

For any **new** module section added to an `lp/<sub>/<x>.org` (and
when fully refactoring an existing one), follow this hierarchy: each
Python concept gets its own org subsection, organised hierarchically —
never as a flat list of "Functions / Helpers / Misc".

Adapted from skill-scout-server's `lp-module-section-hierarchy.md`,
re-rooted for the meta-repo's `:tangle ../../repos/<sub>/<...>.py`
paths.

## Why

A 600-line module gets one prose paragraph and a 600-line src block in
the single-block style — readers can't pivot to "what does class X do"
without scrolling through the whole block.

The hierarchy style brings prose to every concept, *and* gives
agents a stable target ("edit the `** ClassName` subsection")
instead of "edit lines 250–390 of the giant block".

## Required structure for each module section

```org
* <Module concept name>           ← depth-1 heading
:PROPERTIES:
:CUSTOM_ID: <sub>-<module-kebab>
:LITERATE_ORG_MODULE: <sub_pkg>.<module>
:header-args: :tangle ../../repos/<sub>/<...>/<module>.py :mkdirp yes
:END:

(prose intro: 2–4 lines explaining what this module owns, why it's
shaped this way, what reader-facing facts they should know.)

** import                         ← always first
(short prose if the import set is non-obvious; often empty)

#+begin_src python
<all module-level imports, exactly as in the .py>
#+end_src

** logger                          ← second, when present
(prose if non-trivial; usually trivial)

#+begin_src python
logger = logging.getLogger(__name__)
tracer = ...           ← OTel tracer, if any
#+end_src

** <Module-level constants / globals>
(only when the module has top-level non-import / non-logger constants)

#+begin_src python
SOMETHING_DEFAULT = 42
_SOMETHING_RE = re.compile(r"...")
#+end_src

** =ClassName= / Concept-named function group / Single function
(one depth-2 subsection per class or function-cluster)
```

The order within a module section is:

1. `import`
2. `logger` (and any module-level OTel tracer / metric setup)
3. global constants / configuration
4. classes (each as its own `**` subsection)
5. top-level functions (each as its own `**` subsection — or grouped
   under a concept-named parent when ≥ 3 are conceptually paired)

## Per-class subsection — three sizes

### Small (≤ 30 lines): single src block

```org
** =SmallClass=
(prose)
#+begin_src python
class SmallClass:
    ...
#+end_src
```

### Medium (30–80 lines): single src block, prose explains each method

```org
** =MediumClass=
(prose: introduces the class AND walks through each method's role —
2–6 sentences.)
#+begin_src python
class MediumClass:
    def __init__(...): ...
    def method_a(...): ...
    def method_b(...): ...
#+end_src
```

### Large (≥ 80 lines): noweb-split per `lp-noweb-for-big-blocks.md`

See that rule for the full template.

## Per-function subsections — flat or grouped

### Standalone function

```org
** =do_something=
(prose: what + why + tradeoff)
#+begin_src python
def do_something(...): ...
#+end_src
```

### Grouped concept (preferred when ≥ 3 related helpers)

```org
** Download S3 files
(prose intro for the group: what these helpers collectively do)

*** Cache timeout
(prose)
#+begin_src python
REMOTE_CACHE_TIMEOUT = ...
_cached_remote_mtime = {}
#+end_src

*** =get_cached_remote_mtime=
(prose)
#+begin_src python
def get_cached_remote_mtime(...): ...
#+end_src
```

The group heading names the *concept*. Sub-headings name the
*specific* function or constant. Hierarchy mirrors the reader's
mental model: zoom in from concept to detail.

## Hierarchy over flat layout

Three signals you should reach for hierarchy:

1. The same module has 8+ top-level subsections at depth-2 — look
   for 3–4 conceptual clusters and group them under depth-2 headings.
2. The prose for one subsection naturally forward-references another
   ("see also `helper_x`") — they belong under one common parent.
3. Function names share a prefix or suffix (`_build_*`, `_normalize_*`,
   `*_to_dict`) — same family ⇒ likely one group.

Avoid hierarchy for hierarchy's sake — three depth-2 subsections is
fine if each is conceptually distinct. The depth-≤-5 cap from
`literate-programming-document-first.md` still applies.

## Quick reference

| Module piece | Subsection at depth | Heading style |
|---|---|---|
| imports | `**` | `** import` |
| logger / tracer | `**` | `** logger` |
| constants | `**` | `** <concept> constants` |
| small class (≤ 30 lines) | `**` | `** =ClassName=` |
| medium class | `**` | `** =ClassName=` |
| big class (≥ 80 lines) | `**` + nested `***` per method | `** =ClassName=` / `*** method_name` |
| single top-level function | `**` | `** =function_name=` |
| function cluster (≥ 3) | `**` parent + `***` per fn | `** <concept>` / `*** =function_name=` |
| nested grouping | `***` parent + `****` per leaf | depth ≤ 5 cap |

The first subsection MUST be `** import`. The second MUST be
`** logger` (or another module-globals subsection) when the module
has any. Classes and functions follow in source-file order.
