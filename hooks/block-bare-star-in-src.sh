#!/usr/bin/env python3
# PreToolUse hook: reject Edit/Write/MultiEdit on .org files when the
# *resulting* buffer would contain a bare ``* …`` line at column 0
# inside a ``#+begin_src`` block. Such a line is parsed by Org as a
# headline and silently terminates the enclosing src block, so the
# tangler emits a corrupted .py.
#
# Reads the Claude Code tool payload from stdin (JSON), reconstructs
# what the file would look like AFTER the proposed edit, runs the
# bare-star scanner on the in-memory result, and exits 2 with a
# stderr diagnostic if any NEW violation appears (pre-existing
# offenders are out of scope here — `make check-structure` catches
# those).
#
# The file is named ``.sh`` because that's how Claude Code's hook
# matcher is wired; the shebang line forces the python interpreter
# so the suffix is cosmetic.
#
# Adapted from skill-scout-server's `block-bare-star-in-src.sh`. The
# scanner is inlined (skill-scout imports it from `scripts/`) — keeps
# this hook self-contained for cold-clone usability.

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC_BEGIN_RE = re.compile(r"^\s*#\+begin_src\b", re.I)
SRC_END_RE = re.compile(r"^\s*#\+end_src\b", re.I)
BARE_STAR_RE = re.compile(r"^\*+\s")


def _iter_violations(text: str):
    """Yield (line_no, raw_line) for every bare-star violation."""
    in_src = False
    for n, raw in enumerate(text.splitlines(), 1):
        if not in_src and SRC_BEGIN_RE.match(raw):
            in_src = True
            continue
        if in_src and SRC_END_RE.match(raw):
            in_src = False
            continue
        if not in_src:
            continue
        if BARE_STAR_RE.match(raw):
            yield n, raw


def _apply_edit(current: str, old_string: str, new_string: str, replace_all: bool) -> str:
    if not old_string:
        return current
    if replace_all:
        return current.replace(old_string, new_string)
    return current.replace(old_string, new_string, 1)


def _resolve_proposed_content(tool: str, inp: dict, target: Path) -> tuple[str, str]:
    before = target.read_text(encoding="utf-8") if target.is_file() else ""
    if tool == "Write":
        return before, inp.get("content", "") or ""
    if tool == "Edit":
        return before, _apply_edit(
            before,
            inp.get("old_string", "") or "",
            inp.get("new_string", "") or "",
            bool(inp.get("replace_all", False)),
        )
    if tool == "MultiEdit":
        cur = before
        for edit in inp.get("edits", []) or []:
            cur = _apply_edit(
                cur,
                edit.get("old_string", "") or "",
                edit.get("new_string", "") or "",
                bool(edit.get("replace_all", False)),
            )
        return before, cur
    return before, before


def main() -> int:
    payload = json.loads(sys.stdin.read())
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}
    path = inp.get("file_path", "") or ""

    if tool not in {"Edit", "Write", "MultiEdit"}:
        return 0
    if not path.endswith(".org"):
        return 0

    target = Path(path)
    before_text, after_text = _resolve_proposed_content(tool, inp, target)

    before_lines = {raw for _n, raw in _iter_violations(before_text)}
    new_violations = [
        (n, raw) for n, raw in _iter_violations(after_text)
        if raw not in before_lines
    ]

    if not new_violations:
        return 0

    print(
        f"Refusing to edit {path}: this change would introduce "
        f"{len(new_violations)} bare-`*` line(s) inside `#+begin_src` "
        f"blocks. Org parses each as a headline and silently terminates "
        f"the enclosing src block.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    for n, raw in new_violations:
        display = raw if len(raw) <= 100 else raw[:97] + "..."
        print(f"  proposed line ~{n}: {display}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "Fix each line by prepending a comma (`,*`) — Org strips the "
        "leading comma during tangle, so the tangled .py is byte-"
        "identical to what an unescaped block would have produced.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    print(
        "See .claude/rules/lp-comma-escape-leading-star.md for the rule.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
