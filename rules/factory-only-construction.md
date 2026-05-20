# Factory-Only Construction for Backends

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

Adapted from two submodule variants with essentially identical
content:
`repos/pcr-skill-networking/.claude/rules/factory-only-construction.md`,
`repos/skill-scout-server/.claude/rules/factory-only-construction.md`.
Both submodules reference the same PCR-side backend factories, so the
rule is merged into one — it applies anywhere code constructs
`pcr_skill_networking` backend objects, regardless of which submodule
the calling code lives in.

## Rule

Never import or construct backend implementation classes directly.
Always use factory functions:

- **WisdomGraph**: `get_store()` from `pcr_skill_networking.wisdomgraph`
  — never import `LocalWisdomGraph`, `PostgresWisdomGraph`, or
  `JsonlBackend` directly.
- **SkillFS**: `create_skill_fs()` from
  `pcr_skill_networking.utils.skill_fs` — never import `FileSkillFS`
  or `S3SkillFS` directly.

## Rationale

Factory functions encapsulate backend selection. Direct construction
couples callers to specific implementations, which:

- Breaks the ability to swap backends via configuration
  (local → postgres, file → s3).
- Forces every caller to know about every concrete backend class.
- Makes testing painful — mocking by patching factory output is
  cheap; mocking by replacing class imports is not.

## Scope

Applies anywhere `pcr_skill_networking` is imported, including from
`repos/skill-scout-server/` (which depends on it) and any future
submodule that consumes the same factories.

## Enforcement

Reviewed during PR review in any submodule that imports
`pcr_skill_networking`. Any direct concrete-class import gets flagged
and replaced with the factory call.
