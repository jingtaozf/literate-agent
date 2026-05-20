---
description: Research-grounded structural audit of one literate `.org` file or a whole project tree. Checks for the anti-patterns the transfer-gradient research identifies — phase-name headings, missing :CUSTOM_ID: anchors on multi-referenced sections, missing prose-before-src, sections with no stable anchor for cold-start retrieval, typographic-only load-bearing affordances. Reports violations grouped by rule.
argument-hint: <file.org> | <project-root>
allowed-tools: Bash Read Grep Glob
---

# /lp-research-audit — structural audit grounded in the transfer-gradient research

Runs a static audit on literate `.org` content checking for the six
anti-patterns the research identifies. Each finding cites the
literate-agent rule it violates.

## What this command does

1. Resolve target — `$ARGUMENTS` is a file path or a directory. If
   a directory, audit every non-underscore `.org` under it (subject
   to `LITERATE_AGENT_LP_ROOT` if the project uses lp/ layout).
2. Scan each file section-by-section.
3. For each section, run six structural checks (Items 1, 2, 3, 4,
   5, 6 from `hints/dual-audience-checklist.org`).
4. Emit a markdown report grouped by file → section → which check
   failed, with the literate-agent rule reference.

## The six checks

| Check | Detects | Rule violated |
|-------|---------|---------------|
| C1 phase-name heading | `^(Functions\|Helpers\|Utilities\|Misc\|Things\|Stuff)$` | `rules/literate-programming-document-first.md` heading-as-concept |
| C2 missing :CUSTOM_ID: | heading referenced ≥ 2× elsewhere but no :CUSTOM_ID: drawer | `rules/lp-stable-anchors-for-multi-referenced-sections.md` |
| C3 missing prose-before-src | section with `:tangle` target has no prose between heading and first `#+begin_src` | `rules/literate-programming-document-first.md` intent-before-implementation |
| C4 grab-bag mechanism | section with > 80 lines and no sub-section breakdown | `rules/lp-module-section-hierarchy.md` element-interactivity |
| C5 typographic-only affordance | prose uses `*bold*` / `/italic/` to signal "public API" / "entry point" / "do not edit" without matching :PROPERTIES: drawer | `rules/lp-load-bearing-affordances-structural.md` |
| C6 no stable anchor | section heading is generic (>= 60 chars OR generic-name) AND not `:CUSTOM_ID:`-anchored AND referenced from other files | `rules/lp-agent-persistence-hooks.md` |

Some checks (C1, C3, C4) are mechanically decidable. Others (C2, C5,
C6) need a project-wide scan to count cross-references; the audit
does that scan once per invocation.

## Procedure

```!
set -euo pipefail
LITERATE_AGENT_HOME="${LITERATE_AGENT_HOME:-$HOME/projects/literate-agent}"
TARGET="${ARGUMENTS:-.}"

echo "=== lp-research-audit: target = $TARGET ==="
echo ""

# Use check_org_structure.py for the C1 / C3 / C4 mechanical checks
# (they're the existing structural lint).
python3 "$LITERATE_AGENT_HOME/scripts/check_org_structure.py" "$TARGET" 2>&1 | head -50

echo ""
echo "=== Cross-reference audit (C2, C6) ==="
# Find sections that look referenceable but aren't anchored
if [ -d "$TARGET" ]; then
  find "$TARGET" -name '*.org' -not -name '_*' -print0 \
    | xargs -0 grep -hE "^\\*+ " \
    | sort | uniq -c | sort -rn \
    | awk '$1 >= 2 {print}' | head -20
else
  echo "(single-file mode — skipping cross-ref audit)"
fi

echo ""
echo "=== Typographic-only affordance scan (C5 heuristic) ==="
# Heuristic: bold/italic adjacent to load-bearing nouns without matching property
if [ -d "$TARGET" ]; then
  grep -rEn "(\\*|/)(public api|entry point|do not edit|deprecated|internal)\\1" "$TARGET" --include='*.org' 2>/dev/null | head -10
else
  grep -En "(\\*|/)(public api|entry point|do not edit|deprecated|internal)\\1" "$TARGET" 2>/dev/null | head -10
fi
```

After the bash steps, synthesise the output into a per-file /
per-section report. For each violation, name the rule it maps to
and link to the rule file:

```
## <file> :: <heading>

✗ C1 (phase-name heading): "Functions" at line 42
  → rules/literate-programming-document-first.md (heading-as-concept)

✗ C2 (missing :CUSTOM_ID:): "Persistent Client Registry" at line 78
  referenced from 3 other files
  → rules/lp-stable-anchors-for-multi-referenced-sections.md
```

## Optional: --strict mode

If `$ARGUMENTS` ends with `--strict`, also fail on:

- Headings ≥ 60 chars (signifier-text drift — `lp-stable-anchors`)
- Prose preamble missing a verb-of-WHY (heuristic check)
- Sections without `:CUSTOM_ID:` even when only referenced from
  within the same file (forces full anchor density)

Strict mode is for new modules or refactored ones; default mode is
for incremental audits.

## See also

- `~/projects/literate-agent/hints/dual-audience-checklist.org` —
  the canonical 6-item checklist this command mechanises.
- `~/projects/literate-agent/docs/transfer-gradient.org` — the
  research figure that motivates each check.
- `~/projects/literate-agent/skills/lp-style-refactor/` — a
  companion skill for fixing the violations one iteration at a time.
- `~/projects/literate-agent/commands/lp-check.md` — broader
  lint-and-tangle command; `/lp-research-audit` is structurally
  narrower (research-grounded) than `/lp-check` (general).
