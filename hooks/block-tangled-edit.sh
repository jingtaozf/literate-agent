#!/usr/bin/env python3
# PreToolUse hook: reject Edit/Write/MultiEdit on every tangle-managed
# source path inside this meta-repo.
#
# Strict policy — LP tangle is the only way to update tracked source:
#   - All *.py, *.ts, *.tsx, *.rs, *.tf UNDER ``repos/<sub>/`` are
#     LP-managed. The only path forward is "edit the owning
#     ``lp/<sub>/<x>.org`` section, then re-tangle."
#   - Anything outside ``repos/`` (scripts/, .claude/, etc.) is meta-
#     repo tooling and editable directly.
#   - Whitelist (narrow, no env-var escape hatch):
#       * alembic/versions/*.py — auto-generated, timestamp-named
#       * *.tfvars / *.tfvars.json — env-specific *values* (image
#         tags, CIDR blocks, bucket names) edited freely; only the
#         *.tf *structure* is LP-managed
#       * *-values.yaml under mega-code-infra (Helm overrides — same
#         role as .tfvars: values, not structure)
#
# Earlier versions honoured ``LITERATE_ORG_BYPASS_BLOCK=1`` for
# "one-off pre-migration edits"; every consumer turned into a
# load-bearing path that bypassed LP discipline indefinitely. The env
# var is gone.
#
# Bash-tool bypass is closed by the SIBLING hook
# ``block-bash-tangle-write.sh`` (matcher: Bash) — it rejects
# sed/awk/perl/redirect/tee/cp/mv/dd writes to LP-managed paths.
#
# Smart hint:
#   On block, look up the path in .cache/tangle-map.tsv to find the
#   exact lp/<sub>/<x>.org section that owns it. If the cache is
#   missing or stale, rebuild via scripts/build_tangle_map.py and try
#   again. If still no exact match, fall back to listing the lp/<sub>/
#   folder with a best-prefix-guess on the most likely .org.
#
# All the LP-scope / cache-lookup / message-rendering logic lives in
# ``lib/tangle_lookup.py`` so both hooks share one source of truth.
#
# The file is named .sh because that's how Claude Code's hook matcher
# is wired; the shebang forces python so the suffix is cosmetic.

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.tangle_lookup import (  # noqa: E402
    is_in_block_scope_anywhere,
    reject_message_for,
)


def main() -> int:
    payload = json.loads(sys.stdin.read())
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}
    path = inp.get("file_path", "") or ""

    if tool not in {"Edit", "Write", "MultiEdit"}:
        return 0
    if not path:
        return 0
    # Cross-project-aware scope check.  ``is_in_block_scope_anywhere``
    # walks up from ``path`` to find the OWNING LP project (any dir
    # containing ``.claude/hooks/_env.sh``), sources its LP config, and
    # evaluates scope in that frame.  This closes the 2026-05-21 incident
    # where ``CLAUDE_PROJECT_DIR=mind-ai/dev-agent`` let an absolute path
    # into ``mind-ai/edo-literate/repos/.../*.py`` slip past the block
    # because the file wasn't under the agent's own project root.
    blocked, project, env = is_in_block_scope_anywhere(path)
    if not blocked:
        return 0

    print(
        reject_message_for(
            path, action_verb="edit",
            project_root=project, env=env if env else None,
        ),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
