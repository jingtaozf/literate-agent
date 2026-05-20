# Comma-Escape Leading `*` Inside `#+begin_src` Blocks

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

A line that starts at column 0 with `* ` *anywhere* inside an Org src
block — including inside Python triple-quoted docstrings — is parsed
by Org as a **headline** that silently terminates the enclosing src
block. Every line after that point is misclassified as top-level Org
content; the tangler emits a partial / corrupted `.py`.

The fix is the canonical one from the Org manual (§14.2): prepend a
single `,` to the offending line in the `.org` source. Org strips the
leading comma during tangle, so the tangled `.py` is byte-identical
to what you would have written without escaping.

This rule is universal Org-parser behaviour and travels verbatim from
skill-scout-server.

## When the bug bites

Most often in *Python docstrings* containing markdown bullets:

```org
#+begin_src python
"""Module docstring.

* First bullet         ← BAD — Org parses this as a heading
* Second bullet
"""

def foo() -> int: ...
#+end_src
```

After Org sees `* First bullet`, the entire src block is implicitly
abandoned. The `def foo` line is parsed as a top-level paragraph;
tangle output drops the function entirely.

## Safe vs unsafe patterns

| Source line at column 0      | Org element type | Outcome   |
|------------------------------|------------------|-----------|
| `* foo`                      | `headline`       | **BAD** — terminates src block |
| `# * foo`                    | `comment`*       | safe (mostly) — see note |
| `,* foo`                     | `src-block`      | **GOOD** — comma stripped on tangle |
| `    * foo` (any indent ≥ 1) | `src-block`      | safe — Org's heading regex is anchored at col 0 |

\* `# * foo` *inside* a src block is parsed as `src-block` content;
the `comment` classification only happens when the surrounding src
block has *already* been broken by a sibling `* foo` heading
elsewhere. Either way, prefer `,*` for any column-0 star to keep
the parser unambiguous.

## How to escape

In the `.org` source, prepend a single `,` (just the comma — no
space) to every line that starts at column 0 with one or more `*`:

```org
#+begin_src python :tangle ../../repos/skill-scout-server/skill_scout/foo.py
"""Module doc.

,* First bullet
,* Second bullet
,** Sub-bullet under second
"""

def foo() -> int: ...
#+end_src
```

After `make tangle`, the output `.py` contains:

```python
"""Module doc.

* First bullet
* Second bullet
** Sub-bullet under second
"""


def foo() -> int: ...
```

The leading commas are gone — that is Org's
`org-babel-strip-protective-commas` running automatically.

## Defence in depth

Three independent layers — any one catches the bug, and they accumulate:

1. **`.claude/hooks/block-bare-star-in-src.sh`** — PreToolUse hook.
   Inspects Edit/Write/MultiEdit payloads for `.org` files, runs a
   state-machine scan on the *new* file content, rejects the edit
   (exit 2) before it touches disk. Catches Claude sessions that
   would otherwise introduce the pattern.

2. **`scripts/check_org_structure.py`** — adds the same scan as a
   future enhancement (currently checks depth / grab-bag / prose;
   the bare-star scan can be folded in).

3. **`make tangle FILE=…` + `git -C repos/<sub> diff`** — the
   tangle round-trip. A bad `*` at col 0 produces a tangled `.py`
   that diffs against the committed reference; the byte-equivalence
   gate already requires that diff be empty.
