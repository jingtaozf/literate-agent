# Prefer `model_validate` Over Manual Field Mapping

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

Use `Model.model_validate(dict)` (or `Model.model_validate_json(...)`)
to convert ORM rows, dicts, or wire payloads into Pydantic models.
Avoid one-by-one field assignment unless fields need renaming or
complex transforms.

Adapted from `repos/skill-scout-server/.claude/rules/prefer-model-validate.md`
+ `repos/py-foundation/.claude/rules/prefer-model-validate.md`. Both
copies say the same thing; lifting to the meta-repo gives agents
editing Python LP sources a single source.

## Rationale

- Pydantic validates in one shot — catches missing / extra / mistyped
  fields at the boundary where the data crosses into our model layer.
  Manual `Model(a=row.a, b=row.b, ...)` runs no validation, so a
  silently-`None` field rots until something downstream blows up.
- Keeps the model definition as the single source of truth for field
  names. Adding a field means one edit (the model). Manual mapping
  adds N edit sites — and forgetting one is the most common cause of
  "why is this field always null?" tickets.
- Dramatically fewer lines of code than enumerating every field, so
  reviews focus on real changes instead of boilerplate.
- `model_validate_json(...)` skips the intermediate dict allocation
  when the source is already JSON-bytes — measurable on hot paths.

## Forbidden patterns

```python
# NO — silent on missing/extra fields.
model = Skill(
    skill_id=row.skill_id,
    name=row.name,
    score=row.score,
    metadata=row.metadata,
    # …add four more here and forget one…
)
```

```python
# NO — manual dict construction then unpack with **; same
# silent-failure mode as the above, plus a wasted dict copy.
data = {"skill_id": row.skill_id, "name": row.name, ...}
model = Skill(**data)
```

## Acceptable patterns

```python
# YES — validation runs, field count is single-source-of-truth.
model = Skill.model_validate(row)

# YES — JSON bytes path; avoids the dict allocation.
model = Skill.model_validate_json(payload)

# YES — explicit mapping when fields rename or transform.
model = SkillSummary(
    skill_id=row.id,                          # rename
    display_name=row.name.title(),            # transform
    aggregate_score=sum(row.scores) / len(row.scores),  # derive
)
```

The third pattern is the one legitimate use case for the explicit
form: when the source dict's keys don't match the model's field
names, *or* one or more fields needs a non-trivial transform. Even
then, prefer to do the transform once and call `model_validate` on
the result if practical.

## When the source is a SQLAlchemy ORM row

Configure the model with `model_config = ConfigDict(from_attributes=True)`
once, then `Model.model_validate(orm_row)` works — Pydantic reads
attributes off the row object directly. This is the canonical form
in `repos/skill-scout-server/skill_scout/store/`.

## Enforcement

- Reviewed on PR. Grep for `Model(\n` patterns with > 4 keyword
  arguments inside Python LP sources or non-tangled `.py`; they are
  candidates for `Model.model_validate(...)` instead.
- No mechanical lint catches this today; the rule lives on author
  + reviewer discipline.
