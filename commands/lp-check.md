---
description: Run the project's literate-programming verification — tangle + structure check + smoke test. Reports any violations of the four-part section shape or prose discipline.
argument-hint: <optional-org-file>
allowed-tools: Bash Read Grep Glob
---

# /lp-check — verify LP discipline

Runs the standard LP verification pipeline for the current project:

1. Tangle any literate `.org` source (if a tangle target is set)
2. Check the byte-equivalence between `.org` source and tangle
   output (no manual `.py` / `.el` edits leaked in)
3. Apply the four-part-section structural check on the targeted
   file (or all `.org` files if no argument)
4. Apply the deletion-test prose check (manual pass — flags
   suspect paragraphs, does NOT auto-delete)

## Configuration

The command respects these env vars (set in the host project):

| Variable | Default | Used for |
|----------|---------|----------|
| `LITERATE_AGENT_TANGLE_MAKE_TARGET` | `tangle` | Tangle step |
| `LITERATE_AGENT_CHECK_MAKE_TARGET` | `check-python-structure` | Structure check |
| `LITERATE_AGENT_SMOKE_MAKE_TARGET` | `test-smoke` | Smoke test |

If a target doesn't exist in the project's `Makefile`, the step
is skipped with a note rather than failing.

## Procedure

```!
TANGLE_TARGET="${LITERATE_AGENT_TANGLE_MAKE_TARGET:-tangle}"
CHECK_TARGET="${LITERATE_AGENT_CHECK_MAKE_TARGET:-check-python-structure}"
SMOKE_TARGET="${LITERATE_AGENT_SMOKE_MAKE_TARGET:-test-smoke}"
ARG="$ARGUMENTS"

echo "=== /lp-check: tangle ==="
if make -n "$TANGLE_TARGET" >/dev/null 2>&1; then
  make "$TANGLE_TARGET" || echo "(tangle failed)"
else
  echo "(no '$TANGLE_TARGET' target — skipping)"
fi

echo
echo "=== /lp-check: byte-equivalence ==="
git diff --stat 2>/dev/null | grep -E '\.(py|el)$' || echo "OK (no drift in tangle outputs)"

echo
echo "=== /lp-check: structure ==="
if make -n "$CHECK_TARGET" >/dev/null 2>&1; then
  make "$CHECK_TARGET" || echo "(structure check failed)"
else
  echo "(no '$CHECK_TARGET' target — skipping)"
fi

echo
echo "=== /lp-check: smoke ==="
if make -n "$SMOKE_TARGET" >/dev/null 2>&1; then
  make "$SMOKE_TARGET" || echo "(smoke test failed)"
else
  echo "(no '$SMOKE_TARGET' target — skipping)"
fi
```

After the bash steps above complete, if `$ARGUMENTS` named a
specific `.org` file, run the prose deletion-test manually on
that file using the same procedure as `/audit-prose`.

## See also

- `~/projects/literate-agent/rules/literate-programming-document-first.md`
- `~/projects/literate-agent/skills/audit-prose/SKILL.md`
