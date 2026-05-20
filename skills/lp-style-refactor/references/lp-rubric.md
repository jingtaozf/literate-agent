# LP rubric — what makes a `.org` file readable

Synthesizes the project's own LP rules + outside research (Knuth,
Shi et al. FSE 2025, Anthropic skill design, org-mode community).

Each rule has a one-line statement, a measurable threshold (where
applicable), and a "bad vs good" contrast.

## Section 1 — Structural (auditable mechanically)

### 1.1 Heading depth ≤ 5

`make check-structure` enforces this. Exceeding 5 means the file's
hierarchy has rotted — split into multiple files or merge sibling layers.

### 1.2 No grab-bag section names

Banned: `Functions`, `Helpers`, `Utilities`, `Misc`, `Things`, `Stuff`,
`Implementation`, `Code`, `Other`.

**Bad**: `*** Helpers` containing 9 unrelated functions.

**Good**: name the *concept*. `*** Pattern A — Causal Chain detection`,
`*** Edge canonicalisation` etc. The reader should know what the section
adds to the mental model from the title alone.

### 1.3 Prose-before-code: every section that contains `#+begin_src` has ≥ 1
prose line between heading and first src block

Repo rule:
`.claude/rules/literate-programming-document-first.md`.

**Bad**:

```org
,*** Function _validate_all
,#+BEGIN_SRC python
def _validate_all(...): ...
,#+END_SRC
```

**Good**:

```org
,*** Function _validate_all — Phase 2 of the validator

Builds every per-wisdom prompt up front, then sends them all in one
``complete_batch`` call so ``litellm`` parallelizes the slow calls.
The previous chunked version serialized at chunk boundary.

,#+BEGIN_SRC python
def _validate_all(...): ...
,#+END_SRC
```

### 1.4 Src block > 80 lines → noweb-split candidate

Repo rule: `.claude/rules/lp-noweb-for-big-blocks.md`. See
`references/noweb-split-template.md` for the canonical pattern.

Soft warning at 80, strong warning at 150. Below 80, splitting adds
overhead (skeleton block + per-method subsections) for marginal gain.

### 1.5 Function ≥ 40 LOC → NL outline expected

Per Shi et al., FSE 2025: 4–5 plain-English statements as `# # one-sentence`
comments partitioning the function body. Each summary covers ≥ 3 source
lines.

**Bad** (40 lines of code, no outline):

```python
def parse(s: str) -> Ast:
    tokens = tokenize(s)
    p = Parser(tokens)
    return p.parse_program()
```

**Good** (NL outline at logical boundaries):

```python
def parse(s: str) -> Ast:
    # # Tokenise the input into a flat token stream.
    tokens = tokenize(s)
    # # Wrap a Parser over the stream so recursive-descent can backtrack.
    p = Parser(tokens)
    # # Drive the parser to AST; ParseError propagates with line info.
    return p.parse_program()
```

The outline is NOT a docstring (which describes API contract). It is a
strategy commentary that tracks the body's logical phases.

## Section 2 — Cross-reference hygiene (org-link mechanics)

### 2.1 Bare cross-file refs → org link

**Bad**:

```org
See =lp/pcr-skill-networking/reasoner.org= § "Pure-from-ground-truth"
for details.
```

**Good**:

```org
See [[file:reasoner.org::#pure-from-ground-truth][reasoner.org § Pure-from-ground-truth]] for details.
```

The second form is clickable in Emacs / any org-link follower, and
survives heading renames if the target carries a `:CUSTOM_ID:` anchor.

### 2.2 Multi-referenced section → add `:CUSTOM_ID:`

If a section is linked-to from ≥ 2 places, give it a stable slug. Once
linked, the link target won't break when the heading text is reworded.

```org
,* Background — the PCR vocabulary in 90 seconds
:PROPERTIES:
:CUSTOM_ID: pcr-vocabulary
:END:
```

Reference as `[[#pcr-vocabulary]]` (same file) or
`[[file:other.org::#pcr-vocabulary][text]]` (cross-file).

### 2.3 Hub section → add "See also" footer

If the section is a natural reading-rest stop (e.g. end of "Algorithm
overview" before "Modules"), add a bullet list of 3–5 next-step links:

```org
,** See also

- [[file:validator.org::#pcr-vocabulary][validator.org § PCR vocabulary]] — base concepts.
- [[file:reasoner.org::#reasoner-algorithm][reasoner.org § Stage 4]] — what consumes this stage's output.
```

Cuts the time it takes a reader to find the relevant next section.

## Section 3 — Prose quality (judgment)

### 3.1 Prose explains WHY, not WHAT

The code already shows WHAT. Prose's job is to motivate the design
choice, define jargon, and surface invariants.

**Bad**: "This function takes a list of edges and returns a dict mapping
wisdom IDs to their edges." (the type signature shows this)

**Good**: "Wisdoms share node pairs, so the same edge can appear in two
different wisdoms' prompts. Pre-grouping by canonical (unordered)
endpoint pair lets one prompt's LLM verdict reach all referencing
wisdoms via lookup, instead of N re-scans."

### 3.2 Every jargon term defined before first use

Domain abbreviations (`DAI`, `HNSW`, `noisy-OR`, `Jaccard prior`,
`pgvector`, `advisory lock`) must have a 2–5 sentence plain-English
definition the first time they appear. Subsequent uses can be bare.

Test: hand the file to a senior eng with no ML/stats background. They
should not stumble on a term they haven't seen defined.

### 3.3 Sections shouldn't recap the same fact

If the LP prose preamble already says "this class has 98 methods, here's
a 9-cluster reading guide" then the class docstring should NOT also say
"This is a big class. The methods are organized into groups..." Pick
one place.

## Section 4 — Hygiene (cleanups)

### 4.1 Stale AI-PROVENANCE blocks

```
AI-PROVENANCE
-------------
- Models used: ...
- Date range: 2026-02 → 2026-05 (active)
- Hand-reviewed pivots: ...
```

If `Date range`'s upper bound is > 6 months old AND no "Hand-reviewed
pivots" bullets list recent commits, the block is rotting. Drop it OR
update the date + add a "still relevant because: <one line>".

### 4.2 Resolved TODOs

`# TODO: ...` / `# FIXME: ...` / `# deferred 2026-X: ...` comments that
the surrounding code already addresses → drop.

### 4.3 Docstring-prose duplication

When the LP prose preamble (outside the src block) already covers the
docstring's "Business logic" / "Scoped X" / "Pure-from-ground-truth
invariant" sections, the docstring duplicates can be trimmed. Leave the
API-shape docstring alone (Args / Returns / Raises). Drop the
re-explanation paragraphs.

### 4.4 Redundant blank lines / wrong comments

`ruff format` / `prettier` post-tangle handles most of this. For .org
prose: collapse 2 consecutive empty lines into 1.

## Section 5 — When to STOP

A file is "done" for this iteration if:

- Audit script reports 0 findings, AND
- A senior eng reading top-to-bottom would not have a single "what does
  this mean?" moment, AND
- Cross-file links all resolve (org-mode linter green), AND
- The 3 biggest src blocks have either prose preambles or noweb-splits.

Diminishing returns kick in fast. Don't refactor for refactor's sake.

## Anti-rule (don't apply this rubric mindlessly)

Some files are intentionally terse:

- `_glossary.org` may be all definitions with no prose preambles.
- `decisions-log.org` is chronological; no need to add See-also footers.
- Test-fixture `.org` files (under `lp/<sub>/tests/`) may have minimal
  prose if the test names are self-documenting.

When the audit flags something on these files, use judgment.
