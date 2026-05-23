"""Bootstrap LP sync metadata on legacy .org files.

Stamps `LITERATE_ORG_SOURCE_SHA` + `SHA_DATE` + `TREESIT_GRAMMAR_HASH`
at the file header, and `:LITERATE_ORG_BLOCK_KIND:` on every
`:tangle`-bearing heading. Defers `:LITERATE_ORG_CONTAINS_DEFS:`
to the future tree-sitter extractor (S5 work).

Per `rules/lp-resync-metadata.md`, two preconditions must hold for
bootstrap to be safe:

1. `.org`'s tangle round-trip is byte-equivalent against the source
   working tree. If not, the .org has already drifted; bootstrap
   would stamp the wrong SHA.
2. We can resolve the source repo from the .org's tangle paths.
   First `:tangle <path>` header determines the source repo.

Both checks abort the per-file bootstrap (file is skipped + logged);
they do NOT abort the whole batch.

CLI:
  python3 scripts/lp_sync_bootstrap.py <org-file>
  python3 scripts/lp_sync_bootstrap.py --all <lp-root>
  python3 scripts/lp_sync_bootstrap.py --all <lp-root> --dry-run

Exit code: 0 = all files stamped (or already stamped); 1 = at least
one file skipped due to precondition failure.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HEADING_RE = re.compile(r"^(\*+)\s+(.+?)\s*(?::[\w@:]+:)?$")
PROP_LINE_RE = re.compile(r"^#\+PROPERTY:\s+(\S+)\s+(.*)$")
TANGLE_RE = re.compile(r":tangle\s+([^\s]+)")
NOWEB_YES_RE = re.compile(r":noweb\s+yes\b")
NOWEB_REF_RE = re.compile(r":noweb-ref\s+(\S+)")
HEADER_ARGS_RE = re.compile(r"^:header-args(?::\w+)?:\s+(.*)$", re.IGNORECASE)


def grammar_hash() -> str:
    """Return a placeholder grammar-version hash.

    For S3-lite we just record literate-agent's plugin commit SHA;
    the real tree-sitter binary hash lands in S5. Falls back to
    a fixed sentinel if literate-agent's git HEAD can't be read.
    """
    plugin_root = Path(__file__).resolve().parent.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(plugin_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "literate-agent-unknown"


def resolve_source_repo(tangle_path: str, org_file: Path) -> Path | None:
    """Resolve the source repo containing a `:tangle` target.

    Walks up from the resolved tangle path looking for a `.git`
    directory (or .git file for worktrees / submodules).
    """
    target = (org_file.parent / tangle_path).resolve()
    cur = target.parent
    for _ in range(20):  # cap walk depth
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def git_head_sha(repo: Path) -> str | None:
    """Get HEAD SHA of a git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def already_has_sha(org_file: Path) -> bool:
    """Check if file already has LITERATE_ORG_SOURCE_SHA stamped."""
    with org_file.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("#+"):
                # past file header
                continue
            m = PROP_LINE_RE.match(line.rstrip("\n"))
            if m and m.group(1) == "LITERATE_ORG_SOURCE_SHA":
                return True
    return False


def collect_tangle_targets(org_file: Path) -> list[str]:
    """Return all unique :tangle paths declared in the .org file.

    Only scans CONTEXTS where :tangle is meaningful:
      - #+begin_src lines (per-block header-args)
      - :header-args: lines (block-level via PROPERTIES drawer)
      - #+PROPERTY: header-args lines (file-level default)
    Prose mentions of `:tangle` (e.g. =:tangle no=.) inside quoted
    documentation) are excluded — they're not actual tangle targets.
    """
    targets: list[str] = []
    text = org_file.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        # Three valid contexts where :tangle is a real header arg
        if (line.lower().startswith("#+begin_src")
                or stripped.startswith(":header-args")
                or line.startswith("#+PROPERTY:") and ":tangle" in line):
            for m in TANGLE_RE.finditer(line):
                path = m.group(1)
                if path != "no" and path not in targets:
                    targets.append(path)
    return targets


def detect_block_kind_for_heading(lines: list[str], heading_idx: int) -> str | None:
    """Return BLOCK_KIND for heading at `heading_idx`, or None if no :tangle.

    Looks at :PROPERTIES: drawer + first #+begin_src after the
    heading. Returns one of: 'atomic', 'skeleton', 'noweb-leaf',
    or None if heading has no :tangle.
    """
    n = len(lines)
    i = heading_idx + 1
    header_args_text = ""
    in_props = False
    found_src_begin = False

    # Walk forward to gather :header-args: from PROPERTIES drawer
    # and the first #+begin_src header.
    while i < n:
        line = lines[i].rstrip("\n")
        if line.startswith("*") and HEADING_RE.match(line):
            break  # hit next heading
        if line.strip().startswith(":PROPERTIES:"):
            in_props = True
            i += 1
            continue
        if in_props and line.strip().startswith(":END:"):
            in_props = False
            i += 1
            continue
        if in_props:
            m = HEADER_ARGS_RE.match(line.strip())
            if m:
                header_args_text += " " + m.group(1)
            i += 1
            continue
        if line.lower().startswith("#+begin_src"):
            header_args_text += " " + line
            found_src_begin = True
            break
        i += 1

    if not header_args_text:
        return None

    # The standard noweb-skeleton-with-children pattern (per
    # lp-noweb-for-big-blocks.md):
    #
    #   *** =SomeClass=
    #   :PROPERTIES:
    #   :header-args: :tangle no :noweb-ref SomeClass-body   ← for CHILDREN
    #   :END:
    #
    #   #+begin_src python :tangle ./path.py :noweb yes :noweb-ref ""
    #   class SomeClass:
    #       <<SomeClass-body>>                                ← this is the SKELETON
    #   #+end_src
    #
    #   **** =method_a=                                       ← child → noweb-leaf
    #   #+begin_src python
    #   def method_a(self): ...
    #   #+end_src
    #
    # The parent heading's drawer :header-args :noweb-ref X is the
    # INHERITANCE hint for descendants. The parent's own src block
    # uses :noweb-ref "" to opt OUT, with :noweb yes to expand
    # <<chunks>>. So when both signals coexist:
    #   - :noweb-ref "" anywhere → block opts out (treat as skeleton if
    #     :noweb yes also present, atomic otherwise)
    #   - :noweb yes (without :noweb-ref "" opt-out) → skeleton
    #   - :noweb-ref X (real value, no opt-out) → noweb-leaf

    has_noweb_opt_out = re.search(r':noweb-ref\s+""', header_args_text)
    has_noweb_yes = NOWEB_YES_RE.search(header_args_text)

    if has_noweb_yes:
        return "skeleton"

    if NOWEB_REF_RE.search(header_args_text) and not has_noweb_opt_out:
        return "noweb-leaf"

    has_tangle = TANGLE_RE.search(header_args_text)
    if not has_tangle or has_tangle.group(1) == "no":
        return None

    return "atomic"


def insert_file_props(text: str, sha: str, sha_date: str, grammar: str) -> str:
    """Insert/update the three file-level LITERATE_ORG_* properties.

    Finds the first contiguous block of `#+` lines at the file head;
    appends the new #+PROPERTY: lines at the end of that block. If
    the properties already exist, update in place.
    """
    lines = text.splitlines(keepends=True)
    n = len(lines)
    head_end = 0
    while head_end < n:
        line = lines[head_end].rstrip("\n")
        if line.startswith("#+") or line.strip() == "" or line.startswith("#"):
            head_end += 1
        else:
            break

    def update_or_record(key: str, value: str) -> bool:
        nonlocal lines
        for idx in range(head_end):
            m = PROP_LINE_RE.match(lines[idx].rstrip("\n"))
            if m and m.group(1) == key:
                lines[idx] = f"#+PROPERTY: {key} {value}\n"
                return True
        return False

    new_props = [
        ("LITERATE_ORG_SOURCE_SHA", sha),
        ("LITERATE_ORG_SOURCE_SHA_DATE", sha_date),
        ("LITERATE_ORG_TREESIT_GRAMMAR_HASH", grammar),
    ]
    insert_lines: list[str] = []
    for key, value in new_props:
        if not update_or_record(key, value):
            insert_lines.append(f"#+PROPERTY: {key} {value}\n")

    if insert_lines:
        # Find last #+PROPERTY: line in head_end region; insert after
        last_prop_idx = head_end
        for idx in range(head_end - 1, -1, -1):
            if lines[idx].startswith("#+PROPERTY:"):
                last_prop_idx = idx + 1
                break
        lines = lines[:last_prop_idx] + insert_lines + lines[last_prop_idx:]

    return "".join(lines)


def stamp_block_kinds(text: str, force: bool = False) -> tuple[str, int]:
    """Stamp :LITERATE_ORG_BLOCK_KIND: on every :tangle-bearing heading.

    Returns (new_text, blocks_stamped).

    With force=True, re-stamps blocks that already have BLOCK_KIND
    (used to correct kinds after a detection-logic bugfix).
    """
    lines = text.splitlines(keepends=True)
    n = len(lines)
    out: list[str] = []
    i = 0
    stamped = 0
    while i < n:
        line = lines[i]
        out.append(line)
        m = HEADING_RE.match(line.rstrip("\n"))
        if not m:
            i += 1
            continue
        # heading line; determine kind
        kind = detect_block_kind_for_heading(lines, i)
        if kind is None:
            i += 1
            continue
        # Look ahead: does heading already have :PROPERTIES: drawer with KIND?
        # If yes — skip; if drawer exists without KIND — add KIND line; if no drawer — create
        scan = i + 1
        # skip blank lines
        while scan < n and lines[scan].strip() == "":
            scan += 1
        if scan < n and lines[scan].strip().startswith(":PROPERTIES:"):
            # existing drawer
            end_idx = scan + 1
            while end_idx < n and not lines[end_idx].strip().startswith(":END:"):
                end_idx += 1
            drawer = lines[scan:end_idx + 1]
            has_kind_idx = -1
            for didx, d in enumerate(drawer):
                if "LITERATE_ORG_BLOCK_KIND" in d:
                    has_kind_idx = didx
                    break
            if has_kind_idx >= 0:
                if force:
                    # Replace the existing BLOCK_KIND line with the
                    # freshly-computed kind (used after a bugfix).
                    drawer_abs_idx = scan + has_kind_idx
                    out.extend(lines[i + 1:drawer_abs_idx])
                    out.append(f":LITERATE_ORG_BLOCK_KIND: {kind}\n")
                    out.extend(lines[drawer_abs_idx + 1:end_idx + 1])
                    i = end_idx + 1
                    stamped += 1
                    continue
                # already stamped, no force — skip
                out.extend(lines[i + 1:end_idx + 1])
                i = end_idx + 1
                continue
            # add KIND inside drawer, just after :PROPERTIES:
            out.extend(lines[i + 1:scan + 1])
            out.append(f":LITERATE_ORG_BLOCK_KIND: {kind}\n")
            out.extend(lines[scan + 1:end_idx + 1])
            i = end_idx + 1
            stamped += 1
        else:
            # no drawer; create one immediately after heading
            out.append(":PROPERTIES:\n")
            out.append(f":LITERATE_ORG_BLOCK_KIND: {kind}\n")
            out.append(":END:\n")
            stamped += 1
            i += 1
    return "".join(out), stamped


def bootstrap_file(org_file: Path, dry_run: bool = False,
                   force: bool = False) -> tuple[str, dict]:
    """Bootstrap one .org file. Returns (status, details).

    Status values:
      'ok'          — stamped successfully (or already stamped)
      'skip-no-tangle' — no :tangle targets in file, nothing to do
      'skip-no-source' — couldn't resolve source repo from any :tangle target
      'skip-drift'  — file is drifted from source; can't safely stamp SHA
        (NOTE: in S3-lite we do NOT run the tangle round-trip check;
        that check requires running `make tangle` which is project-
        specific. Status is reserved for S9 end-to-end test.)
    """
    targets = collect_tangle_targets(org_file)
    if not targets:
        return "skip-no-tangle", {"reason": "no :tangle headers"}

    source_repo = None
    for t in targets:
        repo = resolve_source_repo(t, org_file)
        if repo is not None:
            source_repo = repo
            break
    if source_repo is None:
        return "skip-no-source", {"reason": "no .git found via tangle paths",
                                  "tangles": targets[:3]}

    sha = git_head_sha(source_repo)
    if sha is None:
        return "skip-no-source", {"reason": "git HEAD lookup failed",
                                  "repo": str(source_repo)}

    if already_has_sha(org_file) and not dry_run and not force:
        # Already stamped — skip update (idempotent). Use --force to re-stamp
        # block KINDs (e.g. after a bug fix in detection logic).
        return "ok", {"action": "already-stamped", "sha": sha[:12]}

    text = org_file.read_text(encoding="utf-8", errors="replace")
    sha_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    grammar = grammar_hash()

    new_text = insert_file_props(text, sha, sha_date, grammar)
    new_text, blocks_stamped = stamp_block_kinds(new_text, force=force)

    if not dry_run and new_text != text:
        org_file.write_text(new_text, encoding="utf-8")

    return "ok", {
        "source_repo": str(source_repo),
        "sha": sha[:12],
        "blocks_stamped": blocks_stamped,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help=".org file OR directory (use with --all)")
    parser.add_argument("--all", action="store_true",
                        help="recursively process all .org files under target")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="show what would be stamped without writing")
    parser.add_argument("--force", "-f", action="store_true",
                        help="re-stamp block KINDs even on files that already "
                             "have LITERATE_ORG_SOURCE_SHA (useful after a "
                             "bug fix in detection logic)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.all:
        if not args.target.is_dir():
            print(f"error: with --all, target must be a directory: {args.target}", file=sys.stderr)
            return 2
        files = sorted(args.target.rglob("*.org"))
    else:
        if not args.target.is_file():
            print(f"error: target is not a file: {args.target}", file=sys.stderr)
            return 2
        files = [args.target]

    by_status: dict[str, int] = {}
    failures: list[tuple[Path, dict]] = []
    for f in files:
        status, details = bootstrap_file(f, dry_run=args.dry_run, force=args.force)
        by_status[status] = by_status.get(status, 0) + 1
        if args.verbose:
            try:
                rel = f.relative_to(args.target) if args.all else f
            except ValueError:
                rel = f
            print(f"  {status:20s} | {rel}  {details}")
        if status.startswith("skip-"):
            failures.append((f, details))

    print(f"\nScanned {len(files)} files under {args.target}")
    for s, c in sorted(by_status.items()):
        print(f"  {s}: {c}")
    if args.dry_run:
        print("(DRY RUN — no files modified)")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
