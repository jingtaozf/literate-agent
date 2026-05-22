# Tests Embedded in Narrative (Crafting Interpreters Style)

A test is a worked example. The reader has just learned a concept and
should immediately see it verified, not have to jump to a separate
`tests/` file at the end of the document.

This rule is borrowed from Bob Nystrom's *Crafting Interpreters* and
appears in Norvig's PAIP and SICP for the same reason: tests next to
the code they validate teach the code.

## The strict form (preferred for new modules)

A new module section in `literate-org.org` should contain the tests
that exercise it. Layout:

```org
*** HTTP execute endpoint
:PROPERTIES:
:LITERATE_ORG_MODULE: literate_python.server
:header-args:python: :tangle ./literate_python/server.py :results silent :session
:END:

The =/lpy/execute= endpoint runs a string of Python in a named module
context. We capture stdout/stderr because the caller (Emacs) wants
both the value and any side-effect output.

#+BEGIN_SRC python
def execute(...):
    ...
#+END_SRC

**Verification.** A round-trip POST that defines a function and then
calls it confirms namespace persistence across requests.

#+BEGIN_SRC python :tangle ./literate_python/tests/test_server_inline.py
def test_execute_round_trip(client):
    r1 = client.post("/lpy/execute", json={"module": "x", "code": "y = 1"})
    r2 = client.post("/lpy/execute", json={"module": "x", "code": "print(y)"})
    assert r2.json["stdout"].strip() == "1"
#+END_SRC
```

The two `:tangle` paths split prod and test code at tangle time;
narrative-wise they're in the same place. `pytest` discovers the test
through normal collection because the file lands at
`literate_python/tests/...`.

## The light form (for sections whose tests already live in tests/)

Sections that already have tests in `literate_python/tests/test_*.py`
are not refactored unless a larger rewrite is happening. Instead, the
section ends with one cross-reference line:

```org
**Verified by:** [[file:literate-org.org::*test_hot_reload][test_hot_reload]]
```

This costs one prose line, gives the reader a one-click jump to the
tests, and survives line-number drift (org link by heading text).

## What is not allowed

- A "Tests" subtree at the end of the document with no narrative
  connection to the code it tests. Even if you keep tests in a
  separate top-level section, every code section that has tests
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
