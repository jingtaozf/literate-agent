#!/usr/bin/env bash
# PostToolUse hook: refresh a project .org file's :TOC: + tangle after
# Claude edits it.
#
# Two responsibilities, run in order:
#
#   1. TOC regen — call ``(toc-org-insert-toc)`` + ``(save-buffer)`` via
#      emacsclient so the bullet list under the ``* Table of Contents
#      :noexport:TOC:`` heading mirrors the current heading tree. The
#      call is idempotent — verified by 3x calls leaving the buffer
#      with a single TOC heading and a single content block. This step
#      runs UNCONDITIONALLY (modulo the global no-auto-tangle escape
#      hatch) because TOC drift is silent and noticed only when an
#      operator opens an outdated index.
#
#   2. Tangle — call ``(literate-org-tangle-by-path ...)`` via
#      emacsclient (preferred) or ``make tangle`` (batch fallback).
#      Both end at ``org-babel-tangle-file``. Gated by
#      ``LP_AUTO_TANGLE=1`` until each migrated submodule's
#      ``make format`` post-tangle integration is verified byte-
#      equivalent.
#
# Step 1 runs even when Step 2 is gated off — TOC regen has no
# byte-equivalence concerns and the cost is one emacsclient call.
#
# Escape hatches:
#   * LITERATE_ORG_NO_AUTO_TANGLE=1 → skip BOTH steps entirely.
#   * LP_AUTO_TANGLE unset → skip tangle only; TOC still refreshes.

set -euo pipefail

payload=$(cat)
read -r tool_name file_path <<<"$(python3 - "$payload" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
print(d.get("tool_name", ""), d.get("tool_input", {}).get("file_path", "") or "")
PY
)"

[ "${LITERATE_ORG_NO_AUTO_TANGLE:-0}" = "1" ] && exit 0

case "$tool_name" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac
case "$file_path" in *.org) ;; *) exit 0 ;; esac

cd "$CLAUDE_PROJECT_DIR"

# ── Step 1: TOC regen (unconditional best-effort) ──────────────────────
# Refresh the :TOC: heading's bullet list. toc-org-insert-toc is
# idempotent so re-running is a no-op when the TOC is already current.
# Best-effort: a missing host Emacs (emacsclient unreachable) is fine —
# next Emacs save by a human will catch up via toc-org's
# before-save-hook. We silence stderr but keep exit 0 so this step
# never blocks downstream tangle / hook chain.
if emacsclient -e "(condition-case err
                       (with-current-buffer (find-file-noselect \"$file_path\")
                         (when (fboundp 'toc-org-insert-toc)
                           (toc-org-insert-toc))
                         (save-buffer)
                         t)
                     (error (format \"toc-org err: %S\" err)))" >/dev/null 2>&1; then
  : # ok — silent on success to keep hook output tight
fi

# ── Step 2: Tangle (gated by LP_AUTO_TANGLE) ───────────────────────────
[ "${LP_AUTO_TANGLE:-0}" = "1" ] || exit 0

# Try host Emacs first.
if emacsclient -e "(literate-org-tangle-by-path \"$file_path\")" >/dev/null 2>&1; then
  echo "✓ tangled $file_path (via host Emacs)"
  exit 0
fi

# Fall back to batch tangle.
if make tangle FILE="$file_path" >/dev/null 2>&1; then
  echo "✓ tangled $file_path (batch fallback)"
  exit 0
fi

echo >&2 "tangle failed for $file_path"
echo >&2 "  - host Emacs unreachable (emacsclient -e errored)"
echo >&2 "  - batch fallback (make tangle FILE=$file_path) also failed"
echo >&2 "  set LITERATE_ORG_NO_AUTO_TANGLE=1 to bypass auto-tangle"
exit 2
