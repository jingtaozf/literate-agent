# Code Clarity Over Feature Velocity

> *Last-validated*: 2026-05-20
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: claude-agent; the principle generalises beyond that repo.

Readable, well-structured code matters more than shipping features or
adding tests. After every change, pause and ask:

1. **Would a newcomer understand this?** If a function needs a comment
   to explain *what* it does (not *why*), it should be renamed or
   restructured instead.

2. **Does the abstraction earn its weight?** Each layer, helper, or
   indirection must reduce total complexity. If removing it makes the
   code shorter *and* clearer, remove it.

3. **Does the literate narrative still flow?** This project uses
   literate programming — the org file is a document humans read
   top-to-bottom. After editing, re-read the surrounding section.
   Ensure headings, prose, and code tell a coherent story. Move
   misplaced code to where a reader would expect it.

4. **Are names precise?** A variable named `result` or `data` is a
   missed opportunity. Prefer names that encode the *role*:
   `cli-session-id`, `workspace-heading-pos`, `ready-pattern-re`.

5. **Is there unnecessary ceremony?** Boilerplate wrappers, defensive
   nil-checks that can never trigger, over-parameterised functions —
   delete them. The simplest correct code is the best code.

## When to apply

- After implementing a feature, review your diff for clarity before
  calling it done.
- During code review, prioritise readability feedback over style nits.
- When refactoring, measure success by whether the code is *easier to
  read*, not just shorter.

## Aphorisms (Zen-of-Python flavour)

The same rule, restated in heuristics worth memorising:

- *Beautiful is better than ugly.* Readable code matters more than
  just making features work and tests pass.
- *Flat is better than nested.* Can backward-compatibility shims be
  removed? Can deep nesting be unwound with an early return?
- *Explicit is better than implicit.* Are there string workarounds
  that should be proper data models?
- *There should be one — and preferably only one — obvious way to
  do it.* Is there duplicated logic with one branch slightly different?

## Prefer the simple and explicit — concrete patterns

| Reach for | Instead of |
|-----------|-----------|
| Hashable / frozen Pydantic models | string-key workarounds |
| `__lt__` for natural sorting | `key=` lambdas |
| `set` / `frozenset` operations | manual dedup loops |
| `model_dump()` | format strings to serialise a model |
| Direct field access (`obj.skill_id`) | string parsing of an id |
| Named methods or protocols | inline branching by type |

## Pacing

- *Now is better than never* — ship working code.
- *But never is often better than right now* — don't rush ugly
  solutions.
- *Practicality beats purity* — don't over-abstract for hypothetical
  futures.

## Enforcement

Reviewed during PR review and as part of the self-check ritual
before committing. No mechanical check — this is a taste rule,
enforced by human attention.
