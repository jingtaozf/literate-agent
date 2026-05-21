---
description: Audit a PR diff (or recent git history) for cowork-specific drift modes — sycophancy patterns, tone drift, convergent regression, citation hallucination, stake mismatch. Reports findings grouped by rule.
argument-hint: <git-revrange> | <pr-number>
allowed-tools: Bash Read Grep Glob WebSearch
---

# /lp-cowork-review — audit for cowork drift modes in a diff

Mechanises the diagnoses from `hints/cowork-failure-modes.org` over
a git diff range. Reports findings grouped by which `lp-cowork-*`
rule they would violate.

## What this command does

1. Resolve target — `$ARGUMENTS` is a git revrange (e.g. `HEAD~5..HEAD`),
   a PR number, or empty (defaults to staged changes).
2. Walk the diff hunks; for each prose change in an `.org` / `.md`
   file, run five static checks.
3. Verify citations introduced in the diff via WebSearch when the
   citation isn't obviously a known canonical reference.
4. Emit a report grouped by drift mode → which rule it violates.

## The five checks

| Check | Detects | Rule violated |
|-------|---------|---------------|
| K1 sycophancy pattern | review prose containing only agreement (`looks good`, `nicely done`, `polished`) without enumerated concerns or citation verifications | `rules/lp-cowork-anti-sycophancy.md` |
| K2 tone drift | diff replaces idiomatic project phrasing with textbook patterns (e.g. project says `comma-escape`, diff rewrites to `escape special characters per best practice`) | `rules/lp-cowork-anti-sycophancy.md` rule 3 |
| K3 convergent regression | diff strips project-specific decision history (triggering incident, dates, references) and replaces with generic guidance | `rules/lp-transfer-discipline-no-weak-metaphors.md` |
| K4 citation hallucination | diff introduces a citation (`Author Year` pattern) that doesn't match any entry in the existing reference cache AND WebSearch finds no canonical match | `rules/lp-transfer-discipline-no-weak-metaphors.md` |
| K5 stake mismatch | commit message lacks a `Risk:` declaration AND the diff touches a high-stake area (`rules/`, `hooks/`, `scripts/`, `.github/`, public API surface) | `rules/lp-cowork-stake-declaration.md` |

## Procedure

```!
set -euo pipefail
RANGE="${ARGUMENTS:-}"

if [ -z "$RANGE" ]; then
  RANGE=$(git diff --cached --name-only > /dev/null 2>&1 && echo "--cached" || echo "HEAD~1..HEAD")
fi

echo "=== /lp-cowork-review: range = $RANGE ==="
echo ""

echo "=== K1 sycophancy: review prose with no enumerated concerns ==="
git log "$RANGE" --pretty=format:"%H %s" --grep -i "review\|looks good\|polish" | head -10
echo ""

echo "=== K3 convergent regression: removed dates / incidents ==="
git diff "$RANGE" --unified=0 \
  | grep -E '^-.*\b(triggering incident|last-validated|2026-|2025-|fix incident)' \
  | head -10
echo ""

echo "=== K4 citation candidates introduced ==="
git diff "$RANGE" --unified=0 \
  | grep -E '^\+.*\b[A-Z][a-z]+\s+(et al\.?\s+)?(19|20)[0-9]{2}\b' \
  | head -20
echo "(verify each via WebSearch before merging)"
echo ""

echo "=== K5 stake declaration in commit messages ==="
for commit in $(git log "$RANGE" --pretty=format:"%H"); do
  msg=$(git log -1 --pretty=%B "$commit")
  if ! echo "$msg" | grep -qE "^Risk:\s+(low|med|high)"; then
    files_changed=$(git diff-tree --no-commit-id --name-only -r "$commit" 2>/dev/null)
    if echo "$files_changed" | grep -qE "^(rules/|hooks/|scripts/|\\.github/)"; then
      echo "  MISSING stake on high-impact commit: $(git log -1 --pretty='%h %s' $commit)"
    fi
  fi
done
echo ""

echo "=== K2 + K1 require prose-level analysis (synthesised below) ==="
```

After the bash steps run, synthesise findings into a per-commit /
per-file report. For each violation:

```
## <commit-sha> :: <file>

K3 (convergent regression) at line 42-45:
  diff stripped "triggering incident: 2026-05-15 #mega-release …"
  → rules/lp-transfer-discipline-no-weak-metaphors.md
  → reverting to research-grounded specific reference is the fix

K4 (unverified citation) at line 88:
  introduced "Smith 1995" — not in project reference cache
  → WebSearch returns no canonical match for that author/year
  → rules/lp-cowork-anti-sycophancy.md rule 2 — verify before ship
```

## Optional flags

- `--commit-msgs` — only scan commit messages (skip diff content)
- `--diff-only` — only scan diff content (skip commit messages)
- `--since <date>` — broaden range to all commits since a date
- `--strict` — also flag any commit missing stake declaration
  regardless of file scope

## When to use

- *Before merging a PR*: run on the PR's commit range, decide
  whether to request changes.
- *Quarterly audit*: run on a long-running module's git history,
  pattern-match for accumulating drift.
- *After observing drift*: run on the suspect range, get evidence
  for what specifically went wrong.

## See also

- `hints/cowork-failure-modes.org` — the five drift modes this
  command mechanises.
- `rules/lp-cowork-*.md` — the rules whose violations this command
  reports.
- `commands/lp-research-audit.md` — sibling command for *structural*
  audit (reader-side research-grounded); this command is for
  *cowork drift* audit (author-side).
