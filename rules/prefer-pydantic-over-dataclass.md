# Prefer Pydantic BaseModel Over dataclass

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

Use `pydantic.BaseModel` instead of `@dataclass` for any data-shaped
type in Python LP edits across `lp/<sub>/*.org` (and freely-editable
non-tangled `.py` modules). The only acceptable `@dataclass` usage
is internal mutable sentinels (ContextVar holders, frozen
configuration stamps used at module scope) — anything that carries
fields a caller or downstream service consumes should be a Pydantic
model.

Adapted from `repos/skill-scout-server/.claude/rules/prefer-pydantic-over-dataclass.md`
+ `repos/py-foundation/.claude/rules/prefer-pydantic-over-dataclass.md`.
Both submodules already enforce this; lifting it to the meta-repo
gives agents editing the LP layer a single source.

## Rationale

- `model_dump()` / `model_dump_json()` for free serialization across
  FastAPI / message-bus / persistence boundaries.
- `model_validate()` for deserialization with validation at the
  boundary — catches missing/extra fields before they reach business
  logic.
- Integrates with FastAPI response models, OpenAPI schema, and the
  generated `api-types.ts` consumed by `repos/pcr-admin-ui/`.
- A single shape of "this is a data type" across submodules — less
  cognitive overhead when reading code across repo boundaries.

## When `@dataclass` is acceptable

- Internal `ContextVar` holders (`UsageContext`, `BYOKContext`,
  observability stamps) that are frozen sentinels with no
  serialization need.
- Simple internal-only structs that pass between two adjacent
  functions in the same module and never cross a boundary.
- Performance-critical hot paths where Pydantic's validation
  overhead has been measured to matter — these are rare and require
  a comment explaining the measurement.

## Forbidden

- Defining a `@dataclass` for any type that crosses an API / message
  boundary, gets serialized to JSON, or is consumed by a downstream
  TypeScript client.
- Defining a `@dataclass` for any "DTO" / "value object" / "record"
  type — those are Pydantic models by default.

## Acceptable

- `class UsageContext: ContextVar[...]` paired with a `@dataclass`
  frozen value type that lives in that ContextVar.
- `@dataclass(frozen=True, slots=True)` for tiny internal coordinate
  types used by a single algorithm and never serialized.

## Migration guidance

When you find a `@dataclass` that should be a Pydantic model:

1. Convert in place — `from pydantic import BaseModel` + remove
   `@dataclass`.
2. If fields used `field(default_factory=list)`, switch to
   `Field(default_factory=list)`.
3. If there were `__post_init__` validators, port them to
   `@model_validator(mode="after")` or `@field_validator`.
4. Re-run the submodule's `make check` / `make test` to confirm
   no behavioural drift.

## Enforcement

- Reviewed on PR. Grep for `@dataclass` in non-sentinel locations
  is a code-review signal.
- New additions of `@dataclass` for data-shaped types get pushed
  back on during review.
- No mechanical lint catches this today; the rule lives on author
  + reviewer discipline.
