# Tests Embedded in Narrative (Crafting Interpreters Style)

> *Last-validated*: 2026-05-15
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: edo-literate; the principle generalises beyond that repo.

A test is a worked example. The reader has just learned a concept and
should immediately see it verified, not have to jump to a separate
`tests/` file at the end of the document.

This rule is borrowed from Bob Nystrom's *Crafting Interpreters* and
appears in Norvig's PAIP and SICP for the same reason: tests next to
the code they validate teach the code.

Adapted from skill-scout-server's `tests-embedded-in-narrative.md` for
the meta-repo's cross-submodule layout: production code tangles to
`../../repos/<sub>/<pkg>/<mod>.py`, tests tangle to
`../../repos/<sub>/tests/.../test_<mod>.py`.

## The strict form (preferred for new modules)

A new module section in `lp/<sub>/<x>.org` should contain the tests
that exercise it. Layout:

```org
*** Tracing — main_root_span helper
:PROPERTIES:
:LITERATE_ORG_MODULE: <sub_pkg>.obs.tracing
:header-args: :tangle ../../repos/<sub>/<sub_pkg>/obs/tracing.py :mkdirp yes
:END:

The helper exists to spare every CLI ~7 lines of OTel boilerplate …

#+BEGIN_SRC python
@contextmanager
def main_root_span(name: str, **attrs: Any) -> Iterator[None]:
    ...
#+END_SRC

**Verification.** A round-trip that opens a span, records an attribute,
and reads it back through the OTel API confirms the wgu-configure +
setup_tracing chain wires through to the running tracer.

#+BEGIN_SRC python :tangle ../../repos/<sub>/tests/unit/obs/test_tracing_inline.py :mkdirp yes
def test_main_root_span_records_attrs():
    from <sub_pkg>.obs.tracing import main_root_span
    with main_root_span("smoke", cycle_id="x") as _:
        ...
#+END_SRC
```

The two `:tangle` paths split prod and test code at tangle time;
narrative-wise they're in the same place. `pytest` discovers the test
through the submodule's normal collection because the file lands at
`repos/<sub>/tests/unit/<pkg>/test_<mod>_inline.py`.

## The light form (for sections whose tests already live in tests/)

Sections with tests already in `repos/<sub>/tests/unit/...` (the bulk
of existing code that gets onboarded) are not refactored unless a
larger rewrite is happening. Instead, the section ends with one
cross-reference line:

```org
**Verified by:** [[file:../../repos/<sub>/tests/unit/obs/test_tracing.py][test_tracing.py]]
```

This costs one prose line, gives the reader a one-click jump to the
tests, and survives line-number drift (org link by file path, not
heading text).

## What is not allowed

- A "Tests" subtree at the end of a `lp/<sub>/<x>.org` with no
  narrative connection to the code it tests. Even if you keep tests
  in a separate top-level section, every code section that has tests
  must point at them.
- A test for behaviour the surrounding prose does not describe. The
  prose must mention what the test verifies; otherwise the test is
  validating an undocumented contract.
- Tests inside a code block that mixes production and test code
  (lose the tangle split). One block = one tangle target.

## Rationale

LP's claim is "the document teaches". A teaching document with the
worked example chapters away from the lesson is failing at its core
job. Tests are the worked examples; they belong with the lesson.

The light form is the surgical compromise for an existing codebase: it
admits we won't rewrite history but refuses to lose the connection.
