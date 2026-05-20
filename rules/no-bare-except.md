# No Bare `except Exception`

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

Never write `except Exception` (or `except BaseException` or a bare
`except:`) in any Python source — `.py` directly editable in a
submodule, or a Python `#+begin_src` block in `lp/<sub>/<x>.org`.
Always catch the specific exception types you can actually recover
from. If you don't know what exceptions a call can raise, find out —
don't paper over uncertainty with a catch-all.

Adapted from `repos/skill-scout-server/.claude/rules/no-bare-except.md`
+ `repos/py-foundation/.claude/rules/no-bare-except.md`. Both copies
say the same thing; lifting to the meta-repo gives a single source
for agents editing Python via the LP layer.

## Why

`except Exception` swallows bugs. It hides:

- Typos (`NameError`, `AttributeError`) — should crash loudly.
- `KeyboardInterrupt`, `SystemExit` (in older versions) — should
  never be silenced.
- Programmer errors (e.g. `ValueError` from bad arguments we *should*
  fix at the call site).
- Future failure modes that don't exist today — silent rot as the
  dependency surface evolves.

A "documented reason" carve-out was tried in earlier versions of this
rule and immediately became a loophole for any call site that "might
fail somehow." We are closing the loophole entirely: catch the
specific exception type, or let it propagate.

## What to do instead

| Symptom | Right move |
|---------|-----------|
| HTTP call may fail | `except httpx.HTTPError:` (or the specific subclass) |
| File may be missing / unreadable | `except (FileNotFoundError, PermissionError, OSError):` |
| JSON may be malformed | `except json.JSONDecodeError:` |
| Pydantic validation may fail | `except pydantic.ValidationError:` |
| LLM call may time out | `except (TimeoutError, ProviderError):` |
| Subprocess may fail | `except subprocess.CalledProcessError:` |
| "Anything could happen" mirror / observability path | **Don't catch — let it crash and surface in OTel.** |

For "best effort" mirrors (audit, telemetry, secondary store writes):
do the smallest specific exception possible. If a SQLite mirror write
fails, `except sqlite3.OperationalError` is fine; `except Exception`
is not.

## Forbidden patterns

```python
# NO — silently swallows bugs.
try:
    do_something()
except Exception:
    logger.warning("oops")

# NO — same with noqa.
try:
    do_something()
except Exception:  # noqa: BLE001
    logger.exception("anything")

# NO — even with a "documented reason" comment.
try:
    do_something()
except Exception:  # observability path; not critical
    pass
```

## Acceptable patterns

```python
# YES — narrow, specific.
try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    logger.warning("malformed payload: %s", exc)
    return None

# YES — multiple specific types.
try:
    resp = await client.get(url)
except (httpx.HTTPError, asyncio.TimeoutError) as exc:
    return Failure(reason="network", detail=str(exc))

# YES — re-raise after side effect (logging, audit).
try:
    do_thing()
except SpecificError:
    logger.exception("...")
    raise
```

## Interaction with the global rule

The global `~/.claude/CLAUDE.md` already states "let exceptions
propagate — never add bare `except Exception` automatically." This
file is the **stronger meta-repo version**: it bans the pattern even
with a `# noqa: BLE001` suppression or a "documented reason" comment.
The cost is one extra minute thinking about which exception is the
right one to catch; the saving is hours of "why is my LLM call
silently returning None?" archaeology.

## Enforcement

- Reviewed on every PR that touches a Python source (either
  `lp/<sub>/<x>.org` Python src blocks, or any non-tangled `.py`).
- `ruff` rule `BLE001` is on by default in every Python submodule's
  `pyproject.toml`; do not suppress it with `# noqa: BLE001`. Either
  narrow the except or remove the try entirely.
- Pre-commit hooks in each submodule run `ruff check` (which
  includes `BLE001`); a violating commit is blocked before push.
