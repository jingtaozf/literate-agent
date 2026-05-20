# Noweb-split template for big classes / functions

Apply when a single `#+begin_src` block exceeds **~80 lines** (typical
trigger: a class with 5+ methods). Get the skeleton wrong and the
tangled `.py` will diverge from the unsplit version — verify byte
equivalence with `verify_tangle.sh` after.

## When to apply

- Class body > 80 lines AND has 3+ methods.
- A long top-level function (> 60 lines) whose body splits into 3+
  natural narrative steps. (For shorter long functions, prefer NL
  outline `# # one-sentence` comments inline — see `lp-rubric.md` § 1.5.)

## When NOT to apply

- Class < 30 lines — single block more readable.
- Class whose methods are all 5-line one-liners — splitting buys nothing.
- Module-level helper cluster around one concept — keep them in one
  block with a grouped `**` parent heading.

## Required file-scope setup

Ensure the file's header has:

```org
,#+PROPERTY: header-args :results silent :session :noweb yes :tangle no
```

`:noweb yes` is critical. Without it, the skeleton block's
`<<chunk-name>>` placeholder is not expanded at tangle time.

## The pattern

### Step 1 — Parent section (the class envelope)

```org
,*** =NodeEdgeValidator=
:PROPERTIES:
:CUSTOM_ID: validator-nodeedgevalidator
:header-args: :tangle no :noweb-ref NodeEdgeValidator-body
:END:

(prose intro for the class as a whole — 2-4 lines)

,#+begin_src python :tangle ../../repos/pcr-skill-networking/src/pcr_skill_networking/validator/validator.py :noweb yes :noweb-ref ""
class NodeEdgeValidator:
    """Three-phase pipeline: index → LLM batch → apply verdicts."""

    <<NodeEdgeValidator-body>>
,#+end_src
```

Critical details:

- Parent's `:header-args:` sets BOTH `:tangle no` AND `:noweb-ref
  NodeEdgeValidator-body`. Org inherits header-args sub-keys only via
  `:header-args:`; a standalone `:noweb-ref:` PROPERTY-drawer line
  is NOT seen by `org-babel-tangle`.
- Skeleton block is the ONLY one with a real `:tangle <path>`.
- Skeleton block carries `:noweb-ref ""` (empty string) to opt OUT of
  inheriting the chunk name (otherwise its own contents would recurse
  into the chunk).
- Skeleton block also needs `:noweb yes` *explicitly* — the parent's
  `:header-args:` replaces the file-level one, so file-scope `:noweb yes`
  does NOT propagate to the skeleton.
- `<<NodeEdgeValidator-body>>` sits at indent 4 (one level inside
  `class NodeEdgeValidator:`).

### Step 2 — Each method as a `****` subsection

```org
,**** =__init__= — wire up dependencies

(prose for the constructor)

,#+begin_src python
def __init__(self, llm: LiteLLMAdapter, config: ValidatorConfig) -> None:
    self._llm = llm
    self._config = config
,#+end_src

,**** =validate= — public entry point (3-phase pipeline)

(prose for validate)

,#+begin_src python
@traced("pcr.validate", openinference_kind="CHAIN")
def validate(self, nodes, node_edges, wisdoms) -> StageResult[...]:
    ...
,#+end_src
```

Each method block:

- Inherits `:tangle no :noweb-ref NodeEdgeValidator-body` from parent
  via `:header-args:`, so it APPENDS to the chunk and does NOT tangle
  directly.
- Content is at column 0 in the .org (no leading indent).
- Org-Babel re-indents to match the skeleton's `<<...>>` placeholder
  position when expanding.

### Step 3 — Methods are concatenated in document order

`org-babel-tangle` walks the file top-to-bottom and stitches all
sub-blocks with `:noweb-ref NodeEdgeValidator-body` into the
`<<NodeEdgeValidator-body>>` placeholder, in order of appearance.

This means: **reordering methods in the `.org` reorders them in the
`.py`**. Match the original `.py` method order exactly, or you break
byte-equivalence.

## Verification

After noweb-split, run:

```bash
bash .claude/skills/lp-style-refactor/scripts/verify_tangle.sh lp/<sub>/<file>.org
```

The submodule diff MUST be empty for an unchanged-intent split.

## Common mistakes

| Symptom                                         | Cause                                       |
|-------------------------------------------------|---------------------------------------------|
| Tangled `.py` has no method bodies, only class header | Skeleton's `:noweb yes` missing OR `<<...>>` indent wrong |
| Tangled `.py` is doubled                        | Skeleton inherited a `:noweb-ref` and recurses |
| Methods appear in wrong order                   | Subsection order in `.org` doesn't match original `.py` |
| `make tangle` errors "Reference 'X-body' not found" | Parent's `:header-args:` line uses `:noweb-ref:` standalone instead of inline in header-args |
| Methods get 2 extra blank lines between them    | Normal — `ruff format` post-tangle adds PEP-8 spacing |

## Worked example

See iter-? of the cron-mode refactor on `lp/pcr-skill-networking/reasoner.org`'s
`Class PCRReasoner` (planned). Until that lands, the closest reference
is the `Class PCRReasoner` *unsplit* state (321 lines, see
`lp-rubric.md` § 1.4 for why it's a candidate).
