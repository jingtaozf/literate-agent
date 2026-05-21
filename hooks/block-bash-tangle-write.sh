#!/usr/bin/env python3
# PreToolUse hook: reject Bash commands that would WRITE to an LP-managed
# path via shell-level operations the Edit/Write matcher doesn't cover.
#
# Why this hook exists
# --------------------
# ``block-tangled-edit.sh`` only matches Edit / Write / MultiEdit. Claude
# Code has a documented bypass (see github.com/anthropics/claude-code
# issues #29709, #31292, #6876, #55313): when an Edit is rejected the
# agent will often retry via Bash — sed -i, awk -i inplace, perl -i,
# redirect (``>``, ``>>``), tee, cp/mv overwrite, dd of=, heredoc into a
# file. ``disallowedTools`` and the matcher field don't catch any of it
# because the Bash tool input is just a string. This hook reads that
# string, decomposes it into atomic sub-commands, identifies write
# targets, and rejects when any target lands inside LP scope.
#
# Design choices
# --------------
# - *Deny-first*: any sub-command's write target that hits LP scope blocks
#   the whole Bash command. Mirrors the liberzon/claude-hooks pattern.
# - *Fail-closed* on opaque writers: ``python -c '...'``, ``bash -c "..."``,
#   ``sh -c "..."``, ``eval``, ``xargs -I {} cmd {}`` are too dynamic to
#   parse safely. If the command contains one of these AND mentions a
#   ``repos/<sub>/`` path, reject — even if we cannot pin down the exact
#   target. False positives are cheaper than a missed bypass.
# - *Same reject message* as block-tangled-edit.sh, via the shared lib
#   ``lib.tangle_lookup.reject_message_for``. The agent learns one shape.
# - *No env-var bypass.* For a true one-off, edit the owning .org and
#   re-tangle. There is no escape hatch; that is the point.

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.tangle_lookup import (  # noqa: E402
    REPO_ROOT,
    is_in_block_scope_anywhere,
    reject_message_for,
)

# Top-level sub-command separators. Splits on ``&&``, ``||``, ``;``, and
# pipe ``|`` (but not the OR operator ``||``).
SUBCOMMAND_SEPS = re.compile(r"\s*(?:\|\||&&|;|\|(?!\|))\s*")

# Commands whose semantics we can't decode statically. If any of these
# appears alongside a ``repos/<sub>/`` mention anywhere in the command,
# the catch-all fires and rejects.
#
# Each entry is a regex pattern matched against the full Bash command
# string. Word boundaries (\b) make sure ``perl -e`` isn't mistaken for
# ``perl -i`` and ``eval`` at position 0 still trips (a plain substring
# search wouldn't, because the leading-space form would miss the head).
OPAQUE_WRITER_PATTERNS = (
    (r"\bpython3?\s+-c\b", "python -c"),
    (r"\bnode\s+-e\b",      "node -e"),
    (r"\bruby\s+-e\b",      "ruby -e"),
    (r"\bperl\s+-e\b",      "perl -e"),
    (r"\b(?:bash|sh|zsh|ksh)\s+-c\b", "bash/sh -c"),
    (r"\beval\b",           "eval"),
    (r"\bxargs\b",          "xargs"),
    # ``find`` is read-only on its own; flag only when paired with a
    # ``-exec <writer>`` body (sed / awk / perl / tee / cp / mv / dd /
    # interpreter -c). The ``{}`` placeholder makes the actual target
    # opaque to static analysis — fail-closed if find's exec body looks
    # like a writer.
    (r"\bfind\b.*\s-exec(?:dir)?\s+(?:sed|awk|perl|tee|cp|mv|dd|"
     r"python3?|node|ruby|bash|sh|zsh|install|rsync)\b",
     "find -exec <writer>"),
)

# Pattern that catches "this string mentions a repos/<sub> path." Used by
# the catch-all heuristic. Intentionally loose — even if the path is inside
# a quoted string, or referenced without a trailing slash (``find repos/sub
# -name ...``), it still counts. The point is: ANY mention of a submodule
# combined with an opaque writer is suspicious enough to fail-closed.
REPOS_PATH_RE = re.compile(r"\brepos/[A-Za-z0-9_.-]+")


# ── command decomposition ────────────────────────────────────────────────────

def strip_subshells(cmd: str) -> tuple[str, list[str]]:
    """Recursively extract ``$(...)`` and backtick subshell contents.

    Returns ``(cmd_with_subshells_replaced_by_placeholder, [subshell_contents])``.
    Nested subshells are flattened — each one becomes its own item in the list.
    """
    subs: list[str] = []
    out: list[str] = []
    i = 0
    while i < len(cmd):
        if cmd[i : i + 2] == "$(":
            depth = 1
            j = i + 2
            while j < len(cmd) and depth > 0:
                if cmd[j : j + 2] == "$(":
                    depth += 1
                    j += 2
                elif cmd[j] == ")":
                    depth -= 1
                    j += 1
                else:
                    j += 1
            if depth == 0:
                subs.append(cmd[i + 2 : j - 1])
                out.append(" __SUB__ ")
                i = j
                continue
        if cmd[i] == "`":
            j = cmd.find("`", i + 1)
            if j > i:
                subs.append(cmd[i + 1 : j])
                out.append(" __SUB__ ")
                i = j + 1
                continue
        out.append(cmd[i])
        i += 1
    return "".join(out), subs


def strip_heredocs(cmd: str) -> str:
    """Strip heredoc bodies while preserving the redirect operator + target.

    Best-effort: a poorly-formed heredoc (unclosed, weird quoting) may not be
    stripped, in which case its content stays in the command — the regex
    write-pattern scan will still see ``> target`` and the catch-all may also
    trip. Either failure mode lands on "reject", which is the safe default.
    """
    return re.sub(
        r"<<-?\s*[\"']?(\w+)[\"']?\s*\n.*?\n\1\s*(?:\n|$)",
        " ",
        cmd,
        flags=re.DOTALL,
    )


def all_subcommands(cmd: str) -> list[str]:
    """Yield every atomic sub-command from a shell command string."""
    cmd, subs = strip_subshells(cmd)
    cmd = strip_heredocs(cmd)
    out = [p.strip() for p in SUBCOMMAND_SEPS.split(cmd) if p.strip()]
    for s in subs:
        out.extend(all_subcommands(s))
    return out


# ── per-subcommand write-target extraction ───────────────────────────────────

REDIRECT_OP_RE = re.compile(r"^(\d*)>{1,2}$|^>&$")


# Bash builtins / wrappers that take a command as argument and run it
# transparently. Stripping these lets the cmd-table dispatch see the real
# command. Caught by E2E 2026-05-16: ``command sed -i ... LP-path`` was
# not detected because cmd parsed as ``command`` not ``sed``. The
# ``command`` builtin in particular is the agent's natural reach when
# disabling alias / function lookup.
BASH_CMD_WRAPPERS = {
    "command", "builtin", "exec", "time",
    "nice", "nohup", "ionice", "chrt", "taskset", "caffeinate",
    "stdbuf", "unbuffer", "env",
}


def _strip_env_prefix(tokens: list[str]) -> list[str]:
    """Drop leading ``VAR=value`` assignments from a tokenized command."""
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    return tokens[i:]


def _strip_cmd_wrappers(tokens: list[str]) -> list[str]:
    """Peel off transparent Bash wrappers (``command``, ``exec``, ``time``,
    ``nice``, ``env``, ...) from the head of a tokenized command. Recursive
    so ``command time sed -i ...`` collapses to ``sed -i ...``.

    Also strips any flags those wrappers take that don't look like the next
    command (``env -i``, ``nice -n 10``, ``time -p``, ...). Conservative —
    only well-known flag shapes; if we see something we don't recognise we
    stop peeling.
    """
    out = list(tokens)
    while out and out[0] in BASH_CMD_WRAPPERS:
        wrapper = out[0]
        out = out[1:]
        # Some wrappers take optional flags before the real command.
        # Heuristic: skip while the next token looks like a flag (starts
        # with ``-``) or, for ``env``, looks like ``VAR=value``.
        if wrapper == "env":
            while out and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", out[0]):
                out = out[1:]
            if out and out[0] == "-i":
                out = out[1:]
        elif wrapper == "nice":
            if out and out[0] in ("-n",):
                out = out[2:] if len(out) >= 2 else []
        elif wrapper in ("time", "command", "exec"):
            # ``command -p`` / ``command -v`` / ``time -p`` — skip the
            # short flag if present. ``command -v X`` is "lookup type",
            # not actually run, but we treat it as opaque.
            while out and re.match(r"^-[a-zA-Z]+$", out[0]):
                out = out[1:]
    return out


def _basename_cmd(cmd: str) -> str:
    """``/usr/bin/sed`` -> ``sed``; ``sed`` -> ``sed``; ``\\sed`` -> ``sed``.

    Defeats two bypass shapes seen in practice:
    - absolute-path: ``/usr/bin/sed -i ... LP-path`` would miss the
      ``cmd == "sed"`` branch otherwise.
    - backslash-escape: ``\\sed -i ...`` is shell idiom for "skip alias
      lookup" — posix-mode shlex preserves one backslash, so without
      stripping the cmd parses as ``\\sed`` not ``sed``.
    """
    return cmd.rsplit("/", 1)[-1].lstrip("\\")


def _positional(args: list[str]) -> list[str]:
    """Return arguments that don't start with ``-``."""
    return [a for a in args if not a.startswith("-")]


def extract_write_targets(subcmd: str) -> list[str]:
    """Return paths this sub-command would WRITE to.

    Returns the sentinel ``"__OPAQUE__"`` if the sub-command contains an
    opaque writer (python -c / bash -c / eval / xargs) so the caller can
    apply the fail-closed catch-all.
    """
    # shlex barfs on unclosed quotes; on a parse error we yield a sentinel
    # that the caller treats like opaque — fail-closed.
    try:
        tokens = shlex.split(subcmd, posix=True)
    except ValueError:
        return ["__UNPARSEABLE__"]
    if not tokens:
        return []

    tokens = _strip_env_prefix(tokens)
    tokens = _strip_cmd_wrappers(tokens)
    if not tokens:
        return []

    cmd = _basename_cmd(tokens[0])
    args = tokens[1:]
    targets: list[str] = []

    # Opaque writers are checked at the catch-all level (we don't return any
    # parsed target — the caller will see the ``repos/`` substring + the
    # opaque keyword and reject without us needing to pin a target).
    # We still try the redirect scan below in case the OPAQUE form happens
    # to also use a plain ``>`` write.

    # Redirects: scan args for ``>`` / ``>>`` / ``2>`` style tokens.
    j = 0
    while j < len(args):
        tok = args[j]
        if REDIRECT_OP_RE.match(tok):
            if j + 1 < len(args):
                tgt = args[j + 1]
                if not tgt.isdigit():
                    targets.append(tgt)
            j += 2
            continue
        j += 1

    # Per-command target extraction.
    if cmd == "sed":
        if any(a.startswith("-i") for a in args) or "--in-place" in args:
            # Last non-flag positional is the target. (sed expressions are
            # always one of the positionals; conservatively flag everything
            # — if multiple positionals exist we add them all.)
            for a in reversed(args):
                if not a.startswith("-"):
                    targets.append(a)
                    break
    elif cmd == "awk":
        if ("-i" in args and "inplace" in args) or "--inplace" in args:
            for a in reversed(args):
                if not a.startswith("-") and a != "inplace":
                    targets.append(a)
                    break
    elif cmd == "perl":
        if any(re.match(r"^-[ip]", a) or a == "--inplace" for a in args):
            for a in reversed(args):
                if not a.startswith("-"):
                    targets.append(a)
                    break
    elif cmd == "tee":
        for a in args:
            if not a.startswith("-"):
                targets.append(a)
    elif cmd in ("cp", "mv", "install", "rsync"):
        positional = _positional(args)
        if len(positional) >= 2:
            targets.append(positional[-1])
    elif cmd == "dd":
        for a in args:
            if a.startswith("of="):
                targets.append(a[3:])

    return targets


# ── opaque-writer catch-all ──────────────────────────────────────────────────

_OPAQUE_RE = [(re.compile(pat), name) for pat, name in OPAQUE_WRITER_PATTERNS]


def opaque_writer_in(cmd: str) -> str | None:
    """Return the matched opaque-writer fragment, or None.

    Uses word-boundary regex so ``eval`` and ``xargs`` at the head of a
    command trip, and so ``perl -i`` (inplace, which we handle precisely)
    is not confused with ``perl -e`` (the opaque catch-all).
    """
    for rx, name in _OPAQUE_RE:
        if rx.search(cmd):
            return name
    return None


# ── target → LP-scope decision ───────────────────────────────────────────────

def is_blocked_target(target: str) -> tuple[bool, str | None, "Path | None", dict]:
    """Resolve ``target`` to an absolute path and ask the shared lib.

    Returns ``(blocked, abs_path_or_None, owning_project_or_None, env_dict)``.
    The two extra fields let the caller render the reject message in the
    *owning* project's frame (the 2026-05-21 cross-project fix) — when
    they're None/empty the caller falls back to the CLAUDE_PROJECT_DIR
    frame, which is what the single-project Edit/Write tests expect.
    """
    if target.startswith("__"):
        return False, None, None, {}  # sentinel — caller handles separately
    p = Path(target)
    if not p.is_absolute():
        p = REPO_ROOT / target
    abs_str = str(p)
    blocked, project, env = is_in_block_scope_anywhere(abs_str)
    return blocked, abs_str, project, env


# ── reject-message formatters ────────────────────────────────────────────────

def format_blocked(
    targets: list[tuple[str, "Path | None", dict]], full_cmd: str
) -> str:
    """Render the reject message for the FIRST blocked target.

    ``targets`` is a list of ``(abs_path, owning_project_or_None, env)``
    tuples so each target can be rendered in its own owning-project
    frame.  Additional targets are listed by path only (no per-frame
    detail) to keep the message scannable.
    """
    first_path, first_project, first_env = targets[0]
    head = reject_message_for(
        first_path, action_verb="write to (via Bash)",
        project_root=first_project, env=first_env if first_env else None,
    )
    if len(targets) > 1:
        head += (
            "\n\nAdditional LP-managed paths the same command would write:\n"
            + "\n".join(f"  - {t[0]}" for t in targets[1:])
        )
    head += (
        "\n\nThis was a Bash hook reject (matcher: Bash) — the Edit/Write\n"
        "matcher only blocks the named tools; Bash commands that perform\n"
        "file writes (sed/awk/perl/redirect/tee/cp/mv/dd) are caught here\n"
        "instead. Edit the owning .org and re-tangle.\n\n"
        f"Original Bash command: {full_cmd!r}"
    )
    return head


def format_fail_closed(opaque: str, full_cmd: str) -> str:
    return (
        f"Refusing to run Bash command — opaque writer ({opaque}) combined\n"
        f"with a repos/<sub>/ path reference. This pattern is too dynamic\n"
        "to safely classify (python -c / bash -c / eval / xargs can write\n"
        "anywhere), so the LP-tangle hook fails closed.\n"
        "\n"
        "If you intended to read or compute (not write), use the dedicated\n"
        "Read/Grep/Glob tools — they do not trip this catch-all.\n"
        "If you intended to write, edit the owning lp/<sub>/<x>.org section\n"
        "instead and re-tangle. There is no env-var bypass.\n"
        "\n"
        f"Original Bash command: {full_cmd!r}"
    )


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    payload = json.loads(sys.stdin.read())
    if payload.get("tool_name") != "Bash":
        return 0
    inp = payload.get("tool_input", {}) or {}
    cmd = inp.get("command", "") or ""
    if not cmd:
        return 0

    # Each entry is ``(abs_path, owning_project_or_None, env_dict)`` so
    # ``format_blocked`` can render each target in its own LP frame
    # (post-2026-05-21 cross-project change).
    blocked_targets: list[tuple[str, "Path | None", dict]] = []
    seen_paths: set[str] = set()
    opaque_hit: str | None = None

    for sub in all_subcommands(cmd):
        # Targeted detection.
        for target in extract_write_targets(sub):
            if target.startswith("__"):
                continue
            blocked, abs_path, project, env = is_blocked_target(target)
            if blocked and abs_path is not None and abs_path not in seen_paths:
                blocked_targets.append((abs_path, project, env))
                seen_paths.add(abs_path)
        # Catch-all heuristic.
        if opaque_hit is None:
            kw = opaque_writer_in(sub)
            if kw and REPOS_PATH_RE.search(sub):
                opaque_hit = kw

    if blocked_targets:
        print(format_blocked(blocked_targets, cmd), file=sys.stderr)
        return 2

    # Catch-all only fires when no targeted hit caught the write — the
    # targeted message is more actionable, prefer it whenever available.
    if opaque_hit:
        print(format_fail_closed(opaque_hit, cmd), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
