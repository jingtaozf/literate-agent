"""Shared helpers for the LP-tangle PreToolUse hooks.

Two hooks consume this module:

- ``block-tangled-edit.sh`` — rejects Edit/Write/MultiEdit on any LP-managed path.
- ``block-bash-tangle-write.sh`` — rejects Bash commands that would WRITE to
  an LP-managed path via sed/awk/perl/redirect/tee/cp/mv/dd.

Both hooks share the same definition of "LP scope" (which extensions, which
whitelist, which submodule layout) and the same lookup + reject-message
pipeline. Centralising it here:

1. Keeps the two hooks honest — same paths get treated the same.
2. Keeps the reject message format consistent so the agent learns one shape.
3. Self-heals the same way (one place that knows how to rebuild the cache).

The .sh suffix on the wrapping hook scripts is for Claude Code's matcher
machinery; the shebang forces python3, so the suffix is cosmetic.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))
CACHE_FILE = REPO_ROOT / ".cache" / "tangle-map.tsv"

# Self-heal script can live in two places, in order of preference:
#  1. The host project's local scripts/ (project-specific override).
#  2. literate-agent's scripts/ (the shared canonical version).
# This lets a project pin a forked build_tangle_map.py while the
# default uses the literate-agent build.
_LITERATE_AGENT_HOME = Path(
    os.environ.get(
        "LITERATE_AGENT_HOME",
        Path.home() / "projects" / "literate-agent",
    )
).resolve()


def _resolve_build_map_script() -> Path:
    local = REPO_ROOT / "scripts" / "build_tangle_map.py"
    if local.is_file():
        return local
    return _LITERATE_AGENT_HOME / "scripts" / "build_tangle_map.py"


BUILD_MAP_SCRIPT = _resolve_build_map_script()

# ── per-project configuration (set via env vars in the host project) ────────
#
# LITERATE_AGENT_TANGLED_OUTPUT_EXTS
#   Comma-separated extensions the block hook treats as LP-managed.
#   Default: ".py" — single-language Python LP project.
#   Multi-language meta-repo example: ".py,.ts,.tsx,.rs,.tf"
#
# LITERATE_AGENT_TANGLED_ROOTS
#   Comma-separated path prefixes (relative to project root) under which
#   files with the above extensions are considered LP-managed. Anything
#   outside these prefixes is editable directly (meta-repo tooling,
#   scripts/, .claude/, etc.).
#   Default: "" (empty) → ALL files with matching extension are LP-managed.
#   Multi-submodule example: "repos/"
#
# LITERATE_AGENT_LP_ROOT
#   Path (relative to project root) where the .org sources live. Used by
#   the best-guess fallback to suggest "edit lp/<sub>/<x>.org" on a block.
#   Default: "lp"
#
# LITERATE_AGENT_TANGLED_WHITELIST_FRAGMENTS
#   Comma-separated substring patterns. Paths containing ANY of these
#   fragments are NOT blocked, even with a matching extension. Use for
#   generated files (alembic migrations, codegen output, vendored data).
#   Default: "/alembic/versions/"

def _parse_csv_env(name: str, default: str) -> tuple[str, ...]:
    val = os.environ.get(name, default).strip()
    if not val:
        return ()
    return tuple(s.strip() for s in val.split(",") if s.strip())

BLOCK_EXTS = set(_parse_csv_env("LITERATE_AGENT_TANGLED_OUTPUT_EXTS", ".py"))
TANGLED_ROOTS = _parse_csv_env("LITERATE_AGENT_TANGLED_ROOTS", "")
LP_ROOT_REL = os.environ.get("LITERATE_AGENT_LP_ROOT", "lp")
WHITELIST_FRAGMENTS = _parse_csv_env(
    "LITERATE_AGENT_TANGLED_WHITELIST_FRAGMENTS",
    "/alembic/versions/",
)


# ── reverse-map I/O ──────────────────────────────────────────────────────────

def load_map() -> dict[str, str]:
    """Return {tangled_rel: org_rel}. Empty dict if file missing/empty."""
    if not CACHE_FILE.is_file():
        return {}
    out: dict[str, str] = {}
    for line in CACHE_FILE.read_text().splitlines():
        if not line or "\t" not in line:
            continue
        tang, org = line.split("\t", 1)
        out[tang] = org
    return out


def rebuild_map() -> dict[str, str]:
    """Run the rebuilder and reload. Best-effort — no exception on
    failure, just returns whatever's on disk after the attempt.

    Emits a one-line stderr breadcrumb so the agent / user can see
    the cache was just self-healed (and how many entries changed),
    rather than wondering why an exact-org line appeared "for free"
    after a miss. The reject message that follows is the loud part;
    this is the quiet trail of *why* it knew the answer.
    """
    if not BUILD_MAP_SCRIPT.is_file():
        print(
            f"(tangle-lookup: cannot self-heal — {BUILD_MAP_SCRIPT.name} not found)",
            file=sys.stderr,
        )
        return load_map()
    before = len(load_map())
    rc: int | None = None
    try:
        result = subprocess.run(
            [sys.executable, str(BUILD_MAP_SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
            check=False,
        )
        rc = result.returncode
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"(tangle-lookup: cache rebuild failed: {exc!r})",
            file=sys.stderr,
        )
        return load_map()
    after_map = load_map()
    delta = len(after_map) - before
    if delta != 0:
        sign = "+" if delta > 0 else ""
        print(
            f"(tangle-lookup: cache self-healed — now {len(after_map)} "
            f"entries, {sign}{delta} since miss)",
            file=sys.stderr,
        )
    elif rc != 0:
        print(
            f"(tangle-lookup: cache rebuild exit {rc}, no change)",
            file=sys.stderr,
        )
    return after_map


# ── path classification ──────────────────────────────────────────────────────

def resolve_tangled_path(file_path: str) -> str | None:
    """Project-rel path, or None if outside the repo. Works even when the
    path doesn't exist yet (Path.resolve handles non-existent paths)."""
    try:
        return str(Path(file_path).resolve().relative_to(REPO_ROOT))
    except (ValueError, OSError):
        return None


def submodule_of(rel_path: str) -> str | None:
    """For a multi-submodule project (e.g. ``repos/<sub>/...``), return the
    submodule name; for single-repo projects, return None and the caller
    falls back to project-wide LP-root suggestion. Generic: the first
    TANGLED_ROOTS prefix that matches the path determines the "sub" — the
    next path segment after the prefix is taken as the submodule name.
    """
    if not TANGLED_ROOTS:
        return None
    for root in TANGLED_ROOTS:
        root_norm = root.strip("/")
        if not root_norm:
            continue
        parts = rel_path.split("/")
        if len(parts) >= len(root_norm.split("/")) + 1 and "/".join(
            parts[: len(root_norm.split("/"))]
        ) == root_norm:
            return parts[len(root_norm.split("/"))]
    return None


def _under_tangled_root(rel_path: str) -> bool:
    """True iff the path lives under one of the configured TANGLED_ROOTS.
    When TANGLED_ROOTS is empty (default), every path is considered
    in-scope (single-repo Python LP shape)."""
    if not TANGLED_ROOTS:
        return True
    for root in TANGLED_ROOTS:
        root_norm = root.strip("/")
        if not root_norm:
            continue
        if rel_path == root_norm or rel_path.startswith(root_norm + "/"):
            return True
    return False


def is_in_block_scope(file_path: str) -> bool:
    """True iff this path is one the LP block would reject.

    Checks (in order):
    1. Extension is in BLOCK_EXTS (from LITERATE_AGENT_TANGLED_OUTPUT_EXTS).
    2. Not in the WHITELIST_FRAGMENTS whitelist.
    3. Path resolves inside the project root.
    4. Path lives under one of TANGLED_ROOTS (or TANGLED_ROOTS is empty —
       meaning the whole repo is LP-managed for matching extensions).

    Doesn't touch the reverse-map cache — caller decides what to do on hit.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in BLOCK_EXTS:
        return False
    if any(frag in file_path for frag in WHITELIST_FRAGMENTS):
        return False
    rel = resolve_tangled_path(file_path)
    if rel is None:
        return False
    return _under_tangled_root(rel)


# ── best-guess fallback (when cache has no exact match) ─────────────────────

def best_guess_org(rel_path: str, lp_subdir: Path) -> tuple[Path | None, list[Path]]:
    """Rank .org files in lp_subdir by shared-path-prefix with rel_path.

    Returns (best_match_or_none, sorted_other_choices). The "best" is None
    when no candidate has any path-segment overlap with rel_path; the caller
    then falls back to listing every .org in the folder.
    """
    if not lp_subdir.is_dir():
        return None, []
    candidates = sorted(p for p in lp_subdir.glob("*.org") if not p.name.startswith("_"))
    if not candidates:
        return None, []

    rel_segments = {seg.lower() for seg in rel_path.split("/")}

    def score(p: Path) -> tuple[int, str]:
        stem = p.stem.lower()
        if stem in rel_segments:
            return (-2, stem)
        if any(stem in seg for seg in rel_segments):
            return (-1, stem)
        return (0, stem)

    ranked = sorted(candidates, key=score)
    best = ranked[0]
    if score(best)[0] == 0:
        return None, candidates
    return best, list(ranked[1:])


# ── render the rejection message ─────────────────────────────────────────────

def render_message(file_path: str, rel_path: str, exact_org: str | None,
                   best_guess: Path | None, others: list[Path],
                   lp_subdir: Path | None,
                   action_verb: str = "edit") -> str:
    """Build the human-facing rejection text.

    ``action_verb`` lets the caller customise the first line ("edit" vs "write
    to" vs "modify") so the message reads naturally for the Bash hook too.
    """
    exts_pretty = " / ".join(sorted(BLOCK_EXTS))
    scope_clause = (
        f"under {', '.join(TANGLED_ROOTS)} " if TANGLED_ROOTS else ""
    )
    whitelist_clause = (
        f" (whitelist: {', '.join(WHITELIST_FRAGMENTS)})"
        if WHITELIST_FRAGMENTS else ""
    )
    lines = [
        f"Refusing to {action_verb} {file_path}: every {exts_pretty} {scope_clause}"
        f"in this project{whitelist_clause} is owned by a literate `.org` source.",
        "",
    ]
    if exact_org:
        tangle_target = os.environ.get("LITERATE_AGENT_TANGLE_MAKE_TARGET", "tangle")
        # Most tangle targets take FILE=...; allow per-project override of
        # the entire command via LITERATE_AGENT_TANGLE_RETANGLE_CMD if needed.
        retangle_cmd = os.environ.get(
            "LITERATE_AGENT_TANGLE_RETANGLE_CMD",
            f"make {tangle_target} FILE={exact_org}",
        )
        lines += [
            f"This file is tangled FROM:  {exact_org}",
            "",
            "Edit the matching section there and re-tangle:",
            f"    {retangle_cmd}",
        ]
    elif lp_subdir is not None and (best_guess or others):
        rel_lp = lp_subdir.relative_to(REPO_ROOT)
        lines.append(f"The matching org folder is: {rel_lp}/")
        if best_guess:
            rel_best = best_guess.relative_to(REPO_ROOT)
            lines += ["", f"  Most likely .org for this path:  {rel_best}"]
            other_names = ", ".join(p.name for p in others)
            if other_names:
                lines.append(f"  Other .org in the same folder:   {other_names}")
        else:
            other_names = ", ".join(p.name for p in others)
            lines += ["", f"  Existing .org files in this folder: {other_names}"]
        lines += [
            "",
            "If a section already wraps this file, edit it there and re-tangle.",
            "Otherwise ADD a new section in the appropriate .org and re-tangle.",
        ]
    else:
        sub = submodule_of(rel_path)
        if sub:
            lines += [
                f"No {LP_ROOT_REL}/{sub}/ folder yet — this submodule has not",
                "been onboarded into LP. Bootstrap order:",
                f"  1. Create {LP_ROOT_REL}/{sub}/_project.org as the overview.",
                f"  2. Add per-module {LP_ROOT_REL}/{sub}/<x>.org files.",
                "Then re-tangle.",
            ]
        else:
            lines += [
                f"No matching .org found under {LP_ROOT_REL}/.",
                "Create the owning .org section in the appropriate file",
                "and re-tangle.",
            ]
    lines += [
        "",
        "No env-var bypass: for a true one-off, edit the owning .org and",
        "re-tangle. The Bash matcher hook will also reject sed / awk /",
        "redirect bypass attempts; see block-bash-tangle-write.sh.",
    ]
    return "\n".join(lines)


def reject_message_for(file_path: str, action_verb: str = "edit") -> str:
    """Build the full rejection message for a path inside LP scope.

    Handles the self-heal-on-miss flow internally. Caller must have already
    confirmed ``is_in_block_scope(file_path)`` is True.
    """
    rel_path = resolve_tangled_path(file_path)
    assert rel_path is not None, "caller must guarantee is_in_block_scope"
    sub = submodule_of(rel_path)

    mp = load_map()
    exact = mp.get(rel_path)
    if exact is None:
        mp = rebuild_map()
        exact = mp.get(rel_path)

    # Multi-submodule layout: lp_subdir is per-submodule.
    # Single-repo layout: lp_subdir is the project-wide LP root.
    if sub:
        lp_subdir = REPO_ROOT / LP_ROOT_REL / sub
    else:
        lp_subdir = REPO_ROOT / LP_ROOT_REL

    best, others = best_guess_org(rel_path, lp_subdir)
    return render_message(file_path, rel_path, exact, best, others, lp_subdir,
                          action_verb=action_verb)
