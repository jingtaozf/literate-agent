# LP Noweb — Embedding Code into Algorithm Narrative

> *Last-validated*: 2026-05-19
> *Triggering source*: PCR docs-readability pass — 7 .org files got
> jump-link style across `lp/pcr-skill-networking/` (commits
> `5cbb65c` reasoner, `0245a3f` 7-file batch).
> *Review cadence*: quarterly — drop if 6 months without an applied case
> *Origin*: edo-literate; the principle generalises beyond that repo.

When an LP `.org` file's algorithm narrative section and its
implementation src blocks live in *different sections* of the file
(narrative at top under `* Algorithm overview`, code at the bottom
under `* Modules`), readers must jump back and forth to follow the
algorithm. Three styles bridge that gap; each has different
trade-offs.

## Decision table

| Style | When to use                                                                              | Reader sees                                                  | Tangle byte-identical | Effort per file |
| ----- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------------- | --------------- |
| *v1*  | Default for any file with both narrative + Modules sections (low risk, high coverage)   | Algorithm prose ends with `Implementation:` jump-link to the matching `*** Function/Class` heading | ✅ 100%               | ~5 min          |
| *v2*  | Reader must see code beside prose; comfortable with Emacs `noweb-expand-buffer` view    | Algorithm section contains `#+begin_src ... <<chunk>>` literal; full code only after expand | ✅ if careful         | ~30-60 min      |
| *v3*  | Algorithm and code are one tight unit; willing to accept tangle-order change            | Code physically lives under the algorithm sub-section; no separate Modules block | ❌ (order changes)    | ~60-120 min     |

## v1 — Cross-link (recommended default)

Narrative section ends with a sentence pointing at the implementation:

```org
*** Deduction (forward beam search)

(prose explaining deduction)

Output: new =P → R= edges with =source="deduction"=.

*Implementation*: the Python side prepares input + calls into the
Rust crate ([[file:pcr_engine_rs.org][pcr_engine_rs.org]] § Deduction);
the Python orchestrator that collects the result is
[[*Class PCRReasoner][=PCRReasoner=]]'s =_run_deduction= method.
```

Or as a table when multiple steps map to multiple implementations:

```org
| Step  | What it does          | Implementation                                |
|-------+-----------------------+-----------------------------------------------|
| 1     | Decompose query       | [[*QueryDecomposer][=QueryDecomposer=]]      |
| 2     | Seed select via cosine | [[*SeedSelector][=SeedSelector=]]            |
| 3     | PCST graph expansion  | [[*GraphTraversal][=GraphTraversal=]]        |
| ...   | ...                   | ...                                            |
```

✅ Use heading-text links (`[[*Heading Title][label]]`) not
CUSTOM_ID links unless the target heading has a `:CUSTOM_ID:` drawer.
The literate-org-import tool generates headings without CUSTOM_IDs,
so `#kebab-case` anchor links will silently fail.

❌ Don't add `:CUSTOM_ID:` drawers just for cross-linking — they
accumulate as the heading name evolves and a stale link is worse
than a heading-text link (which fails fast on rename).

## v2 — Noweb skeleton + chunk references

The narrative section embeds the code via noweb chunk reference;
the source-of-truth `#+begin_src` lives in `* Modules` with a
`:noweb-ref` tag that the narrative chunk pulls in.

```org
*** =PCRReasoner=
:PROPERTIES:
:header-args: :tangle no :noweb-ref PCRReasoner-body
:END:

(prose intro for the class)

#+begin_src python :tangle ../../repos/<sub>/<...>.py :noweb yes :noweb-ref ""
class PCRReasoner:
    """Docstring for PCRReasoner."""

    <<PCRReasoner-body>>
#+end_src

**** =_scan_pattern_a= — pattern A: w1.R = w2.P
(prose explaining pattern A)
#+begin_src python
def _scan_pattern_a(self, ...): ...
#+end_src

**** =_scan_pattern_b= — pattern B: w1.P → w2.C
(prose explaining pattern B)
#+begin_src python
def _scan_pattern_b(self, ...): ...
#+end_src
```

The parent `*** =PCRReasoner=` skeleton block declares the tangle
target + opens the class body; nested `**** =_scan_pattern_X=`
src blocks inherit `:noweb-ref PCRReasoner-body` from the parent
`:header-args:` and accumulate into the chunk. At tangle time the
chunks concatenate in document order into the placeholder.

Existing rule with the full setup:
[[file:lp-noweb-for-big-blocks.md][lp-noweb-for-big-blocks.md]].

⚠️  Reader caveat: outside Emacs (GitHub web, IDE preview), the
narrative shows `<<PCRReasoner-body>>` literally — readers don't
see the expanded code unless they tangle locally or run
`org-babel-expand-noweb-references-and-assignments-in-buffer`.

## v3 — Physical move (code lives under algorithm heading)

Restructure the file so the algorithm sub-sections own their src
blocks directly. The `* Modules` section disappears or shrinks to
top-level package boilerplate (imports, logger, dataclasses); the
real implementation moves under the algorithm `** Phase N` headings.

```org
** Phase 2 — Cross-triplet pattern aggregation

(intro prose)

*** Pattern A — w1.R = w2.P (causation)
(prose explaining pattern A)
#+begin_src python :tangle ../../repos/<sub>/<...>.py
def _scan_pattern_a(self, ...): ...
#+end_src

*** Pattern B — w1.P → w2.C (feed)
...
```

⚠️ Org-babel-tangle concatenates src blocks in *document order* per
`:tangle <path>`. If you move src blocks across sections, the
tangled `.py` line order *will* change. Verify byte-identical with
`git -C repos/<sub> diff --stat` after every move; if the diff is
non-empty, either restore (the move is incompatible) or accept the
new order as a separate concern (rare — typically `ruff` reformats
the moved block which is also acceptable).

## When to choose which

- *v1* — choose for *every* algorithm-narrative file as a baseline.
  Cheap, safe, immediate reader value.
- *v2* — choose when the class is bigger than ~200 lines AND
  readers should see the algorithm's code structure inline. Apply
  to scientific-heavy files where the narrative *is* the
  documentation contract (e.g. `reasoner.org` PCRReasoner,
  `wisdomgraph.org` WisdomGraphBase).
- *v3* — choose when the algorithm and the code are so tightly
  coupled that "algorithm description" and "function source" are
  not meaningfully separable. Rare; only for genuinely Knuth-style
  literate sections.

In practice, *v1 + occasional v2* covers 95% of cases. *v3* is
reserved for the few files where the algorithm-and-code unit is
small (< 200 LOC) and would otherwise feel artificially split.

## Applied cases (Phase 1, May 2026)

| File              | Style | Why                                                              |
| ----------------- | ----- | ---------------------------------------------------------------- |
| `reasoner.org`    | v1    | Long file, well-developed narrative — jump-link covers it cleanly |
| `wisdomgraph.org` | v1    | Same, plus the file is 7k+ LOC; v3 too risky                   |
| `router.org`      | v1    | 5.7k LOC; v3 would re-shuffle dozens of src blocks               |
| `retriever.org`   | v1    | Smaller, but pipeline-shaped — v1 table works perfectly         |
| `parser.org`      | v1    | Same                                                              |
| `validator.org`   | v1    | Same                                                              |
| `curator.org`     | v1    | Smallest; v1 sufficient                                          |
| `feedback.org`    | v1    | Most complex pipeline; v1 8-row table delivers everything       |

v2 / v3 candidates for future iterations:

- `reasoner.org` *Class PCRReasoner* (~430 LOC) — would benefit from
  v2 split into per-method sub-sections under the existing Phase 1 /
  Phase 2 narrative
- `wisdomgraph.org` *WisdomGraphBase* + *PostgresWisdomGraph* —
  both large; partial v2 split could pull canonicalisation logic
  under "Canonicalisation =" section
