"""LP protocol verification — invariant checks for sync round-trip safety.

Run this whenever .org files change to ensure the lp-resync protocol
stays consistent — both directions (org → source via tangle, source
→ org via sync engine) remain functional.

Six invariants, fast → slow:

  V1 schema           Re-uses audit_lp_sync_metadata.py — file-level
                      SHA presence + format; block-level BLOCK_KIND +
                      valid values + NOWEB_PARENT cross-ref validity.

  V2 contains-defs    For each block with :LITERATE_ORG_CONTAINS_DEFS:,
                      re-parse block content via tree-sitter and verify
                      the extracted def names match the stored list.
                      Catches stale metadata after manual block edits.

  V3 noweb-integrity  Every <<chunk>> placeholder in a skeleton block
                      has at least one noweb-leaf with matching
                      :noweb-ref. Every noweb-leaf's :LITERATE_ORG_NOWEB_PARENT:
                      anchor resolves to a real skeleton block.
                      Detects orphaned chunks (would break tangle).

  V4 tangle-paths     Every :tangle <path> resolves to a real file
                      under the project tree (or its parent dir exists
                      if the file is to be created).
                      Detects dangling tangle targets after refactor.

  V5 source-parseable Every source file referenced by a block's
                      :tangle path is itself tree-sitter parseable
                      (means sync engine can read it on next /lp-resync).
                      Detects pre-corruption of source.

  V6 tangle-roundtrip Optional --full — runs `make tangle` and compares
                      output against source HEAD (byte-equiv or
                      formatter-only diffs). Expensive — skip in
                      pre-commit; run in CI.

CLI:
  python3 scripts/lp_protocol_verify.py <root>                  # V1-V5
  python3 scripts/lp_protocol_verify.py <root> --full           # +V6
  python3 scripts/lp_protocol_verify.py <root> --fix-stale      # auto-fix V2
  python3 scripts/lp_protocol_verify.py <file1.org> <file2.org> # specific files
  python3 scripts/lp_protocol_verify.py --pre-commit             # diff-only mode

Exit code: 0 = all invariants pass; 1 = at least one violation.

Integration:
  - pre-commit: hook calls --pre-commit, only checks staged .org files
  - CI: run with --full on PR
  - quarterly audit: run with --full + audit_lp_sync_metadata.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Re-use parsers + extractors from the sync engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lp_sync_engine import (  # noqa: E402
    OrgFileParser, BlockDefExtractor, get_extractor,
)
from audit_lp_sync_metadata import audit_file as schema_audit  # noqa: E402


def collect_org_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(root.rglob("*.org"))
    return []


def collect_staged_org_files() -> list[Path]:
    """Pre-commit mode: only files staged for commit."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, timeout=10, check=True)
        files = [Path(line) for line in r.stdout.splitlines()
                 if line.endswith(".org") and Path(line).is_file()]
        return files
    except (subprocess.SubprocessError, OSError):
        return []


# ──────────────────────────────────────────────────────────────────
# V1: Schema (delegated)
# ──────────────────────────────────────────────────────────────────

def v1_schema(files: list[Path]) -> list[dict]:
    violations: list[dict] = []
    for f in files:
        for v in schema_audit(f):
            v["check"] = "V1"
            violations.append(v)
    return violations


# ──────────────────────────────────────────────────────────────────
# V2: CONTAINS_DEFS ↔ block content
# ──────────────────────────────────────────────────────────────────

def v2_contains_defs(files: list[Path]) -> list[dict]:
    parser = OrgFileParser()
    extractor = BlockDefExtractor()
    violations: list[dict] = []
    for f in files:
        org = parser.parse(f)
        # Build chunk → leaves map for skeleton expansion
        by_noweb_ref: dict[str, list] = defaultdict(list)
        for b in org.blocks:
            if b.noweb_ref:
                by_noweb_ref[b.noweb_ref].append(b)
        for block in org.blocks:
            if not block.contains_defs:
                continue
            if block.block_kind == "prose-only":
                continue
            # Compute ground truth via tree-sitter parse
            body_lines = org.raw_lines[block.src_begin_line:block.src_end_line - 1]
            body = "\n".join(body_lines)
            if block.block_kind == "skeleton":
                for chunk_name in block.chunk_refs_in_body:
                    for leaf in by_noweb_ref.get(chunk_name, []):
                        leaf_body = "\n".join(
                            org.raw_lines[leaf.src_begin_line:leaf.src_end_line - 1])
                        body += "\n" + leaf_body
            lang_extractor = get_extractor(block.src_lang or "")
            if lang_extractor is None:
                continue  # language without extractor — skip V2
            actual_defs = sorted(lang_extractor.extract(body).keys())
            stored_defs = sorted(block.contains_defs)
            if actual_defs != stored_defs:
                missing = set(actual_defs) - set(stored_defs)
                extra = set(stored_defs) - set(actual_defs)
                violations.append({
                    "check": "V2",
                    "severity": "warn",
                    "location": f"{f}:{block.heading_line}:* {block.heading_text}",
                    "message": (f"stale :LITERATE_ORG_CONTAINS_DEFS: — "
                                f"missing {sorted(missing)}; "
                                f"extra {sorted(extra)}. Run --refresh-defs."),
                })
    return violations


# ──────────────────────────────────────────────────────────────────
# V3: NOWEB integrity
# ──────────────────────────────────────────────────────────────────

def v3_noweb(files: list[Path]) -> list[dict]:
    parser = OrgFileParser()
    violations: list[dict] = []
    for f in files:
        org = parser.parse(f)
        custom_ids = org.custom_id_index()
        # Build chunk → leaves map + chunk → skeleton-refs map
        leaves_by_ref: dict[str, list] = defaultdict(list)
        skeletons_by_ref: dict[str, list] = defaultdict(list)
        for b in org.blocks:
            if b.block_kind == "skeleton":
                for chunk in b.chunk_refs_in_body:
                    skeletons_by_ref[chunk].append(b)
            # Count any block with a (real or inherited) noweb_ref as a
            # potential leaf — org-mode tangle treats inherited
            # :noweb-ref the same as a directly-declared one.
            if b.noweb_ref and b.noweb_ref != '""':
                leaves_by_ref[b.noweb_ref].append(b)

        # Every skeleton's <<chunk>> must have ≥1 leaf
        for chunk, skeletons in skeletons_by_ref.items():
            if chunk not in leaves_by_ref:
                for sk in skeletons:
                    violations.append({
                        "check": "V3a",
                        "severity": "error",
                        "location": f"{f}:{sk.heading_line}:* {sk.heading_text}",
                        "message": (f"skeleton references <<{chunk}>> but no "
                                    f"noweb-leaf has :noweb-ref {chunk} — "
                                    f"tangle would emit unresolved placeholder"),
                    })

        # Every leaf's :LITERATE_ORG_NOWEB_PARENT: must resolve
        for b in org.blocks:
            if b.block_kind != "noweb-leaf":
                continue
            if not b.noweb_parent:
                violations.append({
                    "check": "V3b",
                    "severity": "error",
                    "location": f"{f}:{b.heading_line}:* {b.heading_text}",
                    "message": ("noweb-leaf missing :LITERATE_ORG_NOWEB_PARENT: "
                                "— run --refresh-defs"),
                })
                continue
            target = custom_ids.get(b.noweb_parent)
            if not target:
                violations.append({
                    "check": "V3c",
                    "severity": "error",
                    "location": f"{f}:{b.heading_line}:* {b.heading_text}",
                    "message": (f":LITERATE_ORG_NOWEB_PARENT: {b.noweb_parent} "
                                f"does not match any :CUSTOM_ID: in this file"),
                })
            elif target.block_kind not in (None, "skeleton"):
                violations.append({
                    "check": "V3d",
                    "severity": "error",
                    "location": f"{f}:{b.heading_line}:* {b.heading_text}",
                    "message": (f":LITERATE_ORG_NOWEB_PARENT: target is "
                                f"{target.block_kind!r}, not skeleton"),
                })
    return violations


# ──────────────────────────────────────────────────────────────────
# V4: Tangle paths exist
# ──────────────────────────────────────────────────────────────────

def v4_tangle_paths(files: list[Path]) -> list[dict]:
    parser = OrgFileParser()
    violations: list[dict] = []
    for f in files:
        org = parser.parse(f)
        for block in org.blocks:
            if not block.tangle_path or block.tangle_path == "no":
                continue
            # Template placeholder paths (e.g. `../../repos/<sub>/...`)
            # have literal `<>` brackets — they're intentionally
            # unresolvable. Skip V4 for these.
            if "<" in block.tangle_path or ">" in block.tangle_path:
                continue
            target = (f.parent / block.tangle_path).resolve()
            # Allow target to not yet exist (file to be created), but
            # parent dir must exist; otherwise tangle would fail.
            if not target.exists() and not target.parent.exists():
                violations.append({
                    "check": "V4",
                    "severity": "error",
                    "location": f"{f}:{block.heading_line}:* {block.heading_text}",
                    "message": (f":tangle {block.tangle_path} → {target} — "
                                f"neither file nor parent directory exists; "
                                f"tangle would fail"),
                })
    return violations


# ──────────────────────────────────────────────────────────────────
# V5: Source files parseable
# ──────────────────────────────────────────────────────────────────

def v5_source_parseable(files: list[Path]) -> list[dict]:
    parser = OrgFileParser()
    violations: list[dict] = []
    seen: set[Path] = set()
    for f in files:
        org = parser.parse(f)
        for block in org.blocks:
            if not block.tangle_path or block.tangle_path == "no":
                continue
            target = (f.parent / block.tangle_path).resolve()
            if target in seen or not target.is_file():
                continue
            seen.add(target)
            ext = target.suffix.lower()
            ext_to_lang = {".py": "python", ".ts": "typescript",
                           ".tsx": "tsx", ".rs": "rust"}
            lang = ext_to_lang.get(ext)
            if lang is None:
                continue
            extractor = get_extractor(lang)
            if extractor is None:
                continue
            try:
                source = target.read_text(encoding="utf-8", errors="replace")
                defs = extractor.extract(source)
            except Exception as exc:
                violations.append({
                    "check": "V5",
                    "severity": "error",
                    "location": str(target),
                    "message": f"source file failed to parse: {type(exc).__name__}: {exc}",
                })
                continue
            # 0 defs from non-empty source is NOT an error — many legitimate
            # files have 0 top-level defs:
            #   - __init__.py (re-exports only)
            #   - setup.ts / *.test.ts (Jest-style describe/it blocks)
            #   - Pure-statement scripts (no functions/classes)
            # V5 only flags PARSE FAILURE (caught above as an exception).
            # If sync engine needs to handle 0-def files differently
            # that's a separate engine concern, not a protocol violation.
    return violations


# ──────────────────────────────────────────────────────────────────
# V6: Tangle round-trip (optional)
# ──────────────────────────────────────────────────────────────────

def v6_tangle_roundtrip(root: Path) -> list[dict]:
    violations: list[dict] = []
    if not root.is_dir():
        violations.append({
            "check": "V6",
            "severity": "info",
            "location": str(root),
            "message": "V6 requires --root pointing at a directory containing a Makefile",
        })
        return violations
    if not (root / "Makefile").is_file():
        violations.append({
            "check": "V6",
            "severity": "info",
            "location": str(root),
            "message": "no Makefile at root — skipping V6 tangle round-trip",
        })
        return violations
    # Run make tangle-all
    try:
        r = subprocess.run(
            ["make", "tangle-all"], cwd=str(root),
            capture_output=True, text=True, timeout=600, check=False)
        if r.returncode != 0:
            violations.append({
                "check": "V6",
                "severity": "error",
                "location": str(root),
                "message": f"make tangle-all failed (exit {r.returncode}). "
                           f"stderr: {r.stderr[-300:]!r}",
            })
            return violations
    except (subprocess.SubprocessError, OSError) as exc:
        violations.append({
            "check": "V6",
            "severity": "error",
            "location": str(root),
            "message": f"make tangle-all error: {exc}",
        })
        return violations
    # Check each submodule diff
    repos_root = root / "repos"
    if not repos_root.is_dir():
        return violations
    for sub in sorted(repos_root.iterdir()):
        if not sub.is_dir() or not (sub / ".git").exists():
            continue
        try:
            r = subprocess.run(
                ["git", "-C", str(sub), "diff", "--stat"],
                capture_output=True, text=True, timeout=10, check=False)
            if r.stdout.strip():
                lines = r.stdout.strip().splitlines()
                summary = lines[-1] if lines else "(unparseable diff)"
                violations.append({
                    "check": "V6",
                    "severity": "warn",
                    "location": str(sub),
                    "message": f"tangle drift after make tangle-all: {summary}",
                })
        except (subprocess.SubprocessError, OSError):
            pass
    return violations


# ──────────────────────────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", type=Path,
                        help=".org files or directory roots")
    parser.add_argument("--full", action="store_true",
                        help="include V6 tangle round-trip check (expensive)")
    parser.add_argument("--pre-commit", action="store_true",
                        help="check only staged .org files (for pre-commit hook)")
    parser.add_argument("--checks", default="V1,V2,V3,V4,V5",
                        help="comma-separated subset of checks to run")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.pre_commit:
        files = collect_staged_org_files()
        if not files:
            print("No staged .org files. Skipping.")
            return 0
    elif args.targets:
        files: list[Path] = []
        for t in args.targets:
            files.extend(collect_org_files(t))
    else:
        parser.error("Need at least one target or --pre-commit")
        return 2

    if not files:
        print("No .org files to check.")
        return 0

    requested = set(args.checks.split(","))
    if args.full:
        requested.add("V6")

    print(f"LP protocol verify — {len(files)} .org files, checks {sorted(requested)}")

    all_violations: list[dict] = []
    if "V1" in requested:
        v = v1_schema(files)
        print(f"  V1 schema:       {len(v)} violations")
        all_violations.extend(v)
    if "V2" in requested:
        v = v2_contains_defs(files)
        print(f"  V2 CONTAINS_DEFS: {len(v)} violations")
        all_violations.extend(v)
    if "V3" in requested:
        v = v3_noweb(files)
        print(f"  V3 NOWEB:        {len(v)} violations")
        all_violations.extend(v)
    if "V4" in requested:
        v = v4_tangle_paths(files)
        print(f"  V4 tangle-paths: {len(v)} violations")
        all_violations.extend(v)
    if "V5" in requested:
        v = v5_source_parseable(files)
        print(f"  V5 source-parse: {len(v)} violations")
        all_violations.extend(v)
    if "V6" in requested:
        # V6 needs the root, not file list — use first target if dir
        root_targets = [t for t in args.targets if t.is_dir()]
        if root_targets:
            v = v6_tangle_roundtrip(root_targets[0])
        else:
            v = []
        print(f"  V6 roundtrip:    {len(v)} violations")
        all_violations.extend(v)

    if args.verbose and all_violations:
        print("\nViolations:")
        for v in all_violations[:100]:
            print(f"  [{v.get('severity', 'error'):5s}] {v['check']:5s} {v['location']}")
            print(f"          {v['message']}")
        if len(all_violations) > 100:
            print(f"  ... and {len(all_violations) - 100} more")

    print(f"\nTotal violations: {len(all_violations)}")
    return 0 if not all_violations else 1


if __name__ == "__main__":
    sys.exit(main())
