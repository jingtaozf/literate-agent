#!/usr/bin/env bash
# PostToolUse hook: tangle a project .org file after Claude edits it.
#
# Strategy: prefer the host Emacs (single-process truth), fall back to
# `emacs --batch` via `make tangle FILE=...`. Either path eventually
# calls the same logic — `org-babel-tangle` over the whole buffer.
#
# Why prefer host Emacs:
#   - It already has the file open as a buffer in 99% of the
#     maintainer's workflow, so `find-file-noselect` is free.
#   - It can detect dual-writer conflicts (buffer dirty + disk
#     externally changed) via `verify-visited-file-modtime` and bail
#     with a clean error message.
#   - The batch path re-parses Org from scratch every time (~5s for
#     this 3300-line file); the host Emacs reuses cached parse trees.
#
# Why a fallback at all: if the host Emacs is down (server crash,
# user restarting it, or cmux-only context with no Emacs), we still
# want auto-tangle. Losing it silently is worse than 5 seconds of
# batch latency.
#
# Escape hatch: set LITERATE_ORG_NO_AUTO_TANGLE=1 to skip entirely
# (e.g. when bulk-patching .org without wanting per-edit tangle).

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
