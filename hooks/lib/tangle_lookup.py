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


# ── owning-project detection (cross-project guard) ──────────────────────────
#
# Why this exists.  Without it, ``CLAUDE_PROJECT_DIR`` pins the hook to ONE
# project; any Edit/Write targeting a path *outside* that project (an absolute
# path into a sibling repo) silently fell out of scope and was allowed
# unchecked.  This was the 2026-05-21 incident: a claude session whose
# ``CLAUDE_PROJECT_DIR`` was ``mind-ai/dev-agent`` directly edited
# ``mind-ai/edo-literate/repos/mega-code/mega_code/config.py`` and several
# sibling .py files, bypassing the LP-tangle block entirely.
#
# Fix shape.  Walk up from the file path looking for a marker file that says
# "an LP-managed project lives here" — by convention ``.claude/hooks/_env.sh``
# (every host project that uses literate-agent's hooks ships one).  If found,
# source it to get THAT project's LP config and re-run ``is_in_block_scope``
# in its frame.  If not found anywhere up to filesystem root, the file isn't
# LP-managed — fall through to the original CLAUDE_PROJECT_DIR-based check.
#
# Performance: the walk is pure ``Path.is_file()`` checks (a handful of
# syscalls); the env sourcing is one ``bash -c 'set -a; source X; env'``
# (~10-30ms) and the result is cached in-process so repeated edits in the
# same Bash hook invocation pay the cost once.

_MARKER_REL = Path(".claude") / "hooks" / "_env.sh"
_env_cache: dict[str, dict[str, str]] = {}


def find_owning_project(file_path: str) -> Path | None:
    """Walk up from ``file_path`` looking for ``.claude/hooks/_env.sh``.

    Returns the directory containing ``.claude/`` (treated as the owning
    project's root for LP scope evaluation), or None when no LP marker is
    found anywhere along the path.

    Works even when the file doesn't exist yet — ``Path.resolve`` handles
    non-existent leaves, and we don't dereference the leaf, only its parents.
    """
    try:
        start = Path(file_path).resolve()
    except (OSError, RuntimeError):
        return None
    # `start.parents` returns parents from immediate to root.  We include
    # `start` itself first so a literal `/some/proj/.claude/hooks/_env.sh`
    # path resolves to `/some/proj` rather than `/some`.
    for parent in (start, *start.parents):
        if (parent / _MARKER_REL).is_file():
            return parent
    return None


def load_project_env(project_root: Path) -> dict[str, str]:
    """Source ``project_root/.claude/hooks/_env.sh`` and return its
    ``LITERATE_AGENT_*`` exports as a plain dict.

    Cached on ``project_root`` so the same Bash hook firing on a
    multi-target command pays the bash-fork cost once.  Returns an empty
    dict on subprocess error so the caller still falls back to module
    defaults instead of crashing the hook.
    """
    key = str(project_root)
    if key in _env_cache:
        return _env_cache[key]
    env_script = project_root / _MARKER_REL
    if not env_script.is_file():
        _env_cache[key] = {}
        return {}
    try:
        result = subprocess.run(
            ["bash", "-c", f"set -a; source {env_script}; env"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        _env_cache[key] = {}
        return {}
    out: dict[str, str] = {}
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.startswith("LITERATE_AGENT_"):
                out[k] = v
    _env_cache[key] = out
    return out


def _scoped_globals(env: dict[str, str]) -> tuple[set[str], tuple[str, ...], str, tuple[str, ...]]:
    """Translate an ``LITERATE_AGENT_*`` env dict into the four LP-scope
    knobs used by the block check.  Each knob falls back to the module-
    level default when the env dict omits it — projects that share most
    settings only need to override the deltas.
    """
    raw_exts = env.get("LITERATE_AGENT_TANGLED_OUTPUT_EXTS")
    block_exts = (
        {s.strip() for s in raw_exts.split(",") if s.strip()} if raw_exts is not None
        else BLOCK_EXTS
    )
    raw_roots = env.get("LITERATE_AGENT_TANGLED_ROOTS")
    tangled_roots = (
        tuple(s.strip() for s in raw_roots.split(",") if s.strip()) if raw_roots is not None
        else TANGLED_ROOTS
    )
    lp_root_rel = env.get("LITERATE_AGENT_LP_ROOT", LP_ROOT_REL)
    raw_white = env.get("LITERATE_AGENT_TANGLED_WHITELIST_FRAGMENTS")
    whitelist = (
        tuple(s.strip() for s in raw_white.split(",") if s.strip()) if raw_white is not None
        else WHITELIST_FRAGMENTS
    )
    return block_exts, tangled_roots, lp_root_rel, whitelist


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

def resolve_tangled_path(
    file_path: str, project_root: Path | None = None
) -> str | None:
    """Project-rel path, or None if outside the project root.

    Works even when the path doesn't exist yet (Path.resolve handles
    non-existent paths).  ``project_root`` defaults to ``REPO_ROOT``
    (the original CLAUDE_PROJECT_DIR-based behaviour); callers that
    have walked up via ``find_owning_project`` pass the owning project
    instead so the result is relative to THAT project's tree.
    """
    base = project_root if project_root is not None else REPO_ROOT
    try:
        return str(Path(file_path).resolve().relative_to(base))
    except (ValueError, OSError):
        return None


def submodule_of(
    rel_path: str, tangled_roots: tuple[str, ...] | None = None
) -> str | None:
    """For a multi-submodule project (e.g. ``repos/<sub>/...``), return the
    submodule name; for single-repo projects, return None and the caller
    falls back to project-wide LP-root suggestion. Generic: the first
    TANGLED_ROOTS prefix that matches the path determines the "sub" — the
    next path segment after the prefix is taken as the submodule name.

    ``tangled_roots`` defaults to the module-level ``TANGLED_ROOTS``;
    pass a project-specific tuple from ``_scoped_globals`` when classifying
    a cross-project path against its OWNING project's config.
    """
    roots = tangled_roots if tangled_roots is not None else TANGLED_ROOTS
    if not roots:
        return None
    for root in roots:
        root_norm = root.strip("/")
        if not root_norm:
            continue
        parts = rel_path.split("/")
        if len(parts) >= len(root_norm.split("/")) + 1 and "/".join(
            parts[: len(root_norm.split("/"))]
        ) == root_norm:
            return parts[len(root_norm.split("/"))]
    return None


def _under_tangled_root(
    rel_path: str, tangled_roots: tuple[str, ...] | None = None
) -> bool:
    """True iff the path lives under one of the configured TANGLED_ROOTS.
    When TANGLED_ROOTS is empty (default), every path is considered
    in-scope (single-repo Python LP shape)."""
    roots = tangled_roots if tangled_roots is not None else TANGLED_ROOTS
    if not roots:
        return True
    for root in roots:
        root_norm = root.strip("/")
        if not root_norm:
            continue
        if rel_path == root_norm or rel_path.startswith(root_norm + "/"):
            return True
    return False


def is_in_block_scope(
    file_path: str,
    *,
    project_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> bool:
    """True iff this path is one the LP block would reject.

    Checks (in order):
    1. Extension is in BLOCK_EXTS (from LITERATE_AGENT_TANGLED_OUTPUT_EXTS).
    2. Not in the WHITELIST_FRAGMENTS whitelist.
    3. Path resolves inside the project root.
    4. Path lives under one of TANGLED_ROOTS (or TANGLED_ROOTS is empty —
       meaning the whole repo is LP-managed for matching extensions).

    ``project_root`` and ``env`` keyword args opt into the cross-project
    flow: the caller has walked up from ``file_path`` to find the actual
    OWNING project (via ``find_owning_project``) and sourced its
    ``_env.sh``; we evaluate scope against THAT project, not the
    process-wide ``CLAUDE_PROJECT_DIR``.  When both are None, the
    behaviour is identical to the pre-2026-05-21 single-project path.

    Doesn't touch the reverse-map cache — caller decides what to do on hit.
    """
    block_exts, tangled_roots, _lp_root_rel, whitelist = (
        _scoped_globals(env or {})
        if env is not None
        else (BLOCK_EXTS, TANGLED_ROOTS, LP_ROOT_REL, WHITELIST_FRAGMENTS)
    )
    ext = Path(file_path).suffix.lower()
    if ext not in block_exts:
        return False
    if any(frag in file_path for frag in whitelist):
        return False
    rel = resolve_tangled_path(file_path, project_root=project_root)
    if rel is None:
        return False
    return _under_tangled_root(rel, tangled_roots=tangled_roots)


def is_in_block_scope_anywhere(file_path: str) -> tuple[bool, Path | None, dict[str, str]]:
    """Cross-project-aware scope check.

    Returns ``(blocked, owning_project, env)`` so the caller can use the
    same project + env for the follow-up reject-message render.

    Decision tree:
    1. ``find_owning_project(file_path)`` — walks up from the file.
    2. If an owning project is found, evaluate scope using ITS config.
       This catches the cross-project case (file lives in repo B but
       CLAUDE_PROJECT_DIR=A).
    3. If no owning project is found, fall back to the original
       single-project ``is_in_block_scope`` (CLAUDE_PROJECT_DIR-based).
       This keeps the existing single-repo flow working unchanged.
    """
    owning = find_owning_project(file_path)
    if owning is not None:
        env = load_project_env(owning)
        blocked = is_in_block_scope(file_path, project_root=owning, env=env)
        return blocked, owning, env
    # Fallback: original CLAUDE_PROJECT_DIR-based scope.
    return is_in_block_scope(file_path), None, {}


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
                   action_verb: str = "edit",
                   *,
                   project_root: Path | None = None,
                   env: dict[str, str] | None = None) -> str:
    """Build the human-facing rejection text.

    ``action_verb`` lets the caller customise the first line ("edit" vs "write
    to" vs "modify") so the message reads naturally for the Bash hook too.
    ``project_root`` + ``env`` opt into the cross-project frame so the message
    references the OWNING project's roots/exts/lp-root rather than whatever
    CLAUDE_PROJECT_DIR happens to be set to in the agent's process.
    """
    base = project_root if project_root is not None else REPO_ROOT
    if env is not None:
        block_exts, tangled_roots, lp_root_rel, whitelist = _scoped_globals(env)
        tangle_target = env.get(
            "LITERATE_AGENT_TANGLE_MAKE_TARGET",
            os.environ.get("LITERATE_AGENT_TANGLE_MAKE_TARGET", "tangle"),
        )
        retangle_cmd_tmpl = env.get(
            "LITERATE_AGENT_TANGLE_RETANGLE_CMD",
            os.environ.get("LITERATE_AGENT_TANGLE_RETANGLE_CMD"),
        )
    else:
        block_exts, tangled_roots, lp_root_rel, whitelist = (
            BLOCK_EXTS, TANGLED_ROOTS, LP_ROOT_REL, WHITELIST_FRAGMENTS
        )
        tangle_target = os.environ.get("LITERATE_AGENT_TANGLE_MAKE_TARGET", "tangle")
        retangle_cmd_tmpl = os.environ.get("LITERATE_AGENT_TANGLE_RETANGLE_CMD")

    exts_pretty = " / ".join(sorted(block_exts))
    scope_clause = (
        f"under {', '.join(tangled_roots)} " if tangled_roots else ""
    )
    whitelist_clause = (
        f" (whitelist: {', '.join(whitelist)})" if whitelist else ""
    )
    project_clause = (
        f" (owning project: {base})" if project_root is not None else ""
    )
    lines = [
        f"Refusing to {action_verb} {file_path}: every {exts_pretty} {scope_clause}"
        f"in this project{whitelist_clause} is owned by a literate `.org` source"
        f"{project_clause}.",
        "",
    ]
    if exact_org:
        retangle_cmd = retangle_cmd_tmpl or f"make {tangle_target} FILE={exact_org}"
        lines += [
            f"This file is tangled FROM:  {exact_org}",
            "",
            "Edit the matching section there and re-tangle:",
            f"    {retangle_cmd}",
        ]
    elif lp_subdir is not None and (best_guess or others):
        try:
            rel_lp = lp_subdir.relative_to(base)
        except ValueError:
            rel_lp = lp_subdir
        lines.append(f"The matching org folder is: {rel_lp}/")
        if best_guess:
            try:
                rel_best = best_guess.relative_to(base)
            except ValueError:
                rel_best = best_guess
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
        sub = submodule_of(rel_path, tangled_roots=tangled_roots)
        if sub:
            lines += [
                f"No {lp_root_rel}/{sub}/ folder yet — this submodule has not",
                "been onboarded into LP. Bootstrap order:",
                f"  1. Create {lp_root_rel}/{sub}/_project.org as the overview.",
                f"  2. Add per-module {lp_root_rel}/{sub}/<x>.org files.",
                "Then re-tangle.",
            ]
        else:
            lines += [
                f"No matching .org found under {lp_root_rel}/.",
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


def reject_message_for(
    file_path: str,
    action_verb: str = "edit",
    *,
    project_root: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """Build the full rejection message for a path inside LP scope.

    Handles the self-heal-on-miss flow internally. Caller must have already
    confirmed ``is_in_block_scope(file_path, project_root=…, env=…)`` is True.

    ``project_root`` + ``env`` opt into the cross-project frame (see
    ``is_in_block_scope_anywhere`` for the discovery side).  When both are
    None, the message and lookups reference the process-wide
    ``CLAUDE_PROJECT_DIR`` exactly as before.
    """
    base = project_root if project_root is not None else REPO_ROOT
    _block_exts, tangled_roots, lp_root_rel, _whitelist = (
        _scoped_globals(env) if env is not None
        else (BLOCK_EXTS, TANGLED_ROOTS, LP_ROOT_REL, WHITELIST_FRAGMENTS)
    )

    rel_path = resolve_tangled_path(file_path, project_root=base)
    assert rel_path is not None, "caller must guarantee is_in_block_scope"
    sub = submodule_of(rel_path, tangled_roots=tangled_roots)

    mp = load_map()
    exact = mp.get(rel_path)
    if exact is None:
        mp = rebuild_map()
        exact = mp.get(rel_path)

    # Multi-submodule layout: lp_subdir is per-submodule.
    # Single-repo layout: lp_subdir is the project-wide LP root.
    if sub:
        lp_subdir = base / lp_root_rel / sub
    else:
        lp_subdir = base / lp_root_rel

    best, others = best_guess_org(rel_path, lp_subdir)
    return render_message(
        file_path, rel_path, exact, best, others, lp_subdir,
        action_verb=action_verb,
        project_root=project_root, env=env,
    )
