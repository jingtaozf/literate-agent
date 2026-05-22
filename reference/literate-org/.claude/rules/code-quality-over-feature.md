# Code Quality Over Feature Completion

Adapted from `~/projects/mind-ai/agents/mega/pcr_skill_networking/.claude/rules/code-quality-over-feature.md`.
The points apply to Python code blocks tangled out of `literate-org.org`,
*and* to the surrounding org prose itself.

Beautiful is better than ugly. Readable code matters more than just
making features work and tests pass.

## After every change, ask

- Is the implementation easy to explain in the org prose? If you can't
  write the "why" sentence, the code isn't ready.
- Is there one obvious way to do this? Refuse the temptation to guess.
- Are there string workarounds that should be proper data models?
  Explicit is better than implicit.
- Is there duplicated logic across code blocks? There should be one —
  and preferably only one — obvious way.

## Prefer the simple and explicit

- Direct field access (`.attr`) over string parsing.
- `set` operations over manual dedup loops.
- `__lt__` for natural sorting over `key=` lambdas everywhere.
- Named functions over inline lambdas when the body is non-trivial.

## Error discipline

- Errors should never pass silently — let exceptions propagate.
- Unless explicitly silenced with a documented reason in the org prose.
- No bare `except Exception` — catch specific types.
- The org section that owns the `try/except` must explain *why* the
  exception is caught here and not propagated.

## Pacing

- Now is better than never — ship working code.
- But never is often better than right now — don't rush ugly solutions
  that pollute the master org file.
- Practicality beats purity — don't over-abstract for hypothetical
  futures.
