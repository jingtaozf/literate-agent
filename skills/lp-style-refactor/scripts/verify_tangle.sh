#!/usr/bin/env bash
# Verify a tangle round-trip after editing an lp/<sub>/<file>.org.
#
# Exit codes:
#   0  prose-only edit → submodule diff is empty
#   1  code changed → submodule diff is non-empty (review + test before committing)
#   2  tangle itself failed
#   3  bad arguments
#
# Usage:
#   bash verify_tangle.sh lp/<sub>/<file>.org

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 lp/<sub>/<file>.org" >&2
  exit 3
fi

ORG_FILE="$1"
if [[ ! -f "$ORG_FILE" ]]; then
  echo "Not a file: $ORG_FILE" >&2
  exit 3
fi

# Derive submodule from the path lp/<sub>/...
SUB="$(echo "$ORG_FILE" | sed -E 's|^lp/([^/]+)/.*|\1|')"
if [[ "$SUB" == "$ORG_FILE" || -z "$SUB" ]]; then
  echo "Cannot derive submodule from $ORG_FILE (expected lp/<sub>/...)" >&2
  exit 3
fi

REPO_PATH="repos/$SUB"
if [[ ! -d "$REPO_PATH" ]]; then
  echo "Submodule directory not found: $REPO_PATH" >&2
  exit 3
fi

echo "==> Tangling $ORG_FILE"
if ! make tangle FILE="$ORG_FILE" 2>&1 | tail -3; then
  echo "tangle failed" >&2
  exit 2
fi

echo ""
echo "==> Submodule diff for $REPO_PATH"
DIFFSTAT="$(git -C "$REPO_PATH" diff --stat 2>/dev/null || true)"

if [[ -z "$DIFFSTAT" ]]; then
  echo "  (empty)"
  echo ""
  echo "✓ prose-only edit — tangle is byte-equivalent."
  exit 0
fi

echo "$DIFFSTAT"
echo ""
echo "==> Substantive (non-blank) line counts per changed file:"
git -C "$REPO_PATH" diff --name-only | while read -r f; do
  total=$(git -C "$REPO_PATH" diff "$f" | grep -cE '^[-+][^-+]' || echo 0)
  nonblank=$(git -C "$REPO_PATH" diff "$f" | grep -E '^[-+][^-+]' | grep -vcE '^[-+]\s*$' || echo 0)
  printf "  %-55s  total=%-4s nonblank=%-4s\n" "$f" "$total" "$nonblank"
done

echo ""
echo "⚠ Code changed. Decide:"
echo "  - Intentional? Run the submodule's test gate before committing."
echo "  - Unintentional? Re-edit the .org to keep prose-only."
exit 1
