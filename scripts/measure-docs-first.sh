#!/usr/bin/env bash
# measure-docs-first.sh — score docs-first reflex adoption over recent commits
#
# Adapted from claude-agent (iter#9 of the 10-iter docs-first refinement
# loop, 2026-05-19).  For each commit in the last N (default 20) that
# touched any lp/**/*.org file, classify into:
#
#   1. CO-EDIT     — both prose lines and code-shaped lines changed.
#                    The docs-first signal we want.
#   2. PROSE-ONLY  — only prose lines changed.  Healthy maintenance.
#   3. BYPASS      — only code lines AND commit message contains a
#                    stated-bypass phrase.
#   4. VIOLATION   — only code lines and NO stated bypass.
#                    Drive to zero.
#
# This script answers "did prose evolve with the src block?".  The
# existing `scripts/audit_tangle_drift.py` answers a different
# question: "did src diverge from its tangle target?".  Run both;
# they're orthogonal.
#
# Configuration (set in the host project's shell env):
#
#   LITERATE_AGENT_DOCS_FIRST_FILE_PATTERN
#     Regex matching .org files this script watches. Default covers
#     both common layouts: multi-submodule (lp/<sub>/*.org) and
#     single-repo (top-level *.org). Override for a tighter scope:
#       export LITERATE_AGENT_DOCS_FIRST_FILE_PATTERN='claude-agent.*\.org$'
#
#   LITERATE_AGENT_DOCS_FIRST_GIT_GLOB
#     Git pathspec passed to `git log -- <glob>`. Defaults to matching
#     the file pattern's locations. Override for project-specific globs.
#
#   LITERATE_AGENT_DOCS_FIRST_BYPASS_RE
#     Regex of legitimate "no prose needed" reasons in commit subjects.
#
# Usage:
#   measure-docs-first.sh               # last 20 .org-touching commits
#   measure-docs-first.sh 50            # last 50
#   measure-docs-first.sh 50 v1..HEAD   # within a revrange

set -euo pipefail

N="${1:-20}"
REVRANGE="${2:-HEAD}"

FILE_PATTERN="${LITERATE_AGENT_DOCS_FIRST_FILE_PATTERN:-^(lp/.+|[^/]+)\.org$}"
GIT_GLOB="${LITERATE_AGENT_DOCS_FIRST_GIT_GLOB:-*.org}"
BYPASS_RE="${LITERATE_AGENT_DOCS_FIRST_BYPASS_RE:-trivial[;:]? skipping prose|mechanical (rename|format|bump)|dependency bump|test-only|revert[;:]? prose|tangle-only|submodule pointer bump|alembic auto-gen}"

declare -i N_COEDIT=0 N_PROSE=0 N_BYPASS=0 N_VIO=0

# Collect commits touching any .org file matching GIT_GLOB.
COMMITS=$(
  git log --format='%H' --diff-filter=ACM -n "$N" "$REVRANGE" -- "$GIT_GLOB" \
  | head -n "$N" || true
)

if [[ -z "$COMMITS" ]]; then
  echo "no commits matched"
  exit 0
fi

printf '%-12s  %-9s  %s\n' "commit" "verdict" "subject"
printf '%-12s  %-9s  %s\n' "------------" "---------" "-------------------------------"

for sha in $COMMITS; do
  # Classify each +/- diff line by content heuristic (not src-block
  # state machine — that fails on hunks fully INSIDE a #+begin_src
  # block; the boundary marker is absent from the diff so default
  # in_src=0 was wrong).  See claude-agent iter#9 commit for the bug
  # discovery.
  read -r prose_lines src_lines <<<"$(
    git show "$sha" -- 'lp/**/*.org' 2>/dev/null | awk '
      /^[+-][^+-]/ {
        body = substr($0, 2)
        if (body ~ /^[[:space:]]*\((defun|cl-defun|defcustom|defvar|cl-defstruct|cl-defgeneric|cl-defmethod|defmacro|let\*?|when|unless|if|cond|setf|setq|require|provide|dolist|while|save-excursion|with-current-buffer|condition-case|ignore-errors|interactive)/ ||
            body ~ /^[[:space:]]*(def |class |from .* import|import |return |if |elif |else:|for |while |try:|except|raise |yield |async )/ ||
            body ~ /^[[:space:]]*(fn |impl |pub |use |mod |let |match |enum |struct |trait )/ ||
            body ~ /^[[:space:]]*(const |let |var |function |interface |type |export |import )/ ||
            body ~ /^[[:space:]]*(resource |module |variable |output |data |provider )/ ||
            body ~ /^[[:space:]]*#\+(begin_src|end_src|name:|property:|BEGIN_SRC|END_SRC|NAME:|PROPERTY:)/ ||
            body ~ /^[[:space:]]*[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*=[[:space:]]/ ||
            body ~ /^[[:space:]]*[)}]/ ||
            body ~ /^[[:space:]]*;;[[:space:]]/) {
          src++
        } else if (body ~ /[a-z][.!?]([[:space:]]|$)/ ||
                   body ~ /^[[:space:]]*\*+[[:space:]]/ ||
                   body ~ /^[[:space:]]*[-+*][[:space:]][A-Z]/ ||
                   body ~ /^[[:space:]]*\|/) {
          prose++
        }
      }
      END { print prose+0, src+0 }
    '
  )"
  subj=$(git log -1 --format='%s' "$sha")

  if (( prose_lines > 0 && src_lines > 0 )); then
    verdict=CO-EDIT
    N_COEDIT+=1
  elif (( prose_lines > 0 && src_lines == 0 )); then
    verdict=PROSE-ONLY
    N_PROSE+=1
  else
    body=$(git log -1 --format='%B' "$sha")
    if echo "$body" | grep -Eqi "$BYPASS_RE"; then
      verdict=BYPASS
      N_BYPASS+=1
    else
      verdict=VIOLATION
      N_VIO+=1
    fi
  fi
  printf '%-12s  %-9s  %s\n' "${sha:0:12}" "$verdict" "${subj:0:60}"
done

total=$(( N_COEDIT + N_PROSE + N_BYPASS + N_VIO ))
echo
echo "tally over ${total} lp/-touching commits:"
printf '  CO-EDIT     %3d  (%.0f%%)  ← docs-first signal\n'   "$N_COEDIT"  "$(awk "BEGIN{print 100*$N_COEDIT/$total}")"
printf '  PROSE-ONLY  %3d  (%.0f%%)\n'                          "$N_PROSE"   "$(awk "BEGIN{print 100*$N_PROSE/$total}")"
printf '  BYPASS      %3d  (%.0f%%)  ← legitimate skips\n'      "$N_BYPASS"  "$(awk "BEGIN{print 100*$N_BYPASS/$total}")"
printf '  VIOLATION   %3d  (%.0f%%)  ← drive to zero (< 10%% goal)\n' "$N_VIO" "$(awk "BEGIN{print 100*$N_VIO/$total}")"
