"""Backfill :CUSTOM_ID: anchors on multi-referenced sections.

Companion to `audit_anchor_coverage.py`. The audit identifies violations;
this script applies them. Pure mechanical fix — generates a kebab-case
slug from the heading text and inserts a `:PROPERTIES:` drawer with the
`:CUSTOM_ID:` line immediately after the heading.

Idempotent: if the heading already has a `:PROPERTIES:` drawer with
`:CUSTOM_ID:`, the script skips it. If the drawer exists without
`:CUSTOM_ID:`, the script adds the `:CUSTOM_ID:` line inside the existing
drawer.

Method:
  1. Take audit output (file:heading_text tuples) from stdin or
     re-run the audit internally.
  2. For each violation, derive slug from heading text.
  3. Open file, find the heading line, insert/update :PROPERTIES:.
  4. Report per-file changes.

CLI:
  python scripts/backfill_anchors.py <root> [--dry-run] [--verbose]

Exit code: 0 = success; 1 = at least one file failed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Re-use audit logic.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_anchor_coverage import audit  # noqa: E402

HEADING_RE = re.compile(r"^(\*+)\s+(.+?)\s*(?::[\w@:]+:)?$")
PROPERTIES_BEGIN = ":PROPERTIES:"
PROPERTIES_END = ":END:"
CUSTOM_ID_LINE = re.compile(r"^\s*:CUSTOM_ID:\s*(\S+)")


def slugify(text: str) -> str:
    """Convert heading text to a kebab-case anchor slug.

    Rules:
      - Lowercase.
      - Replace non-alphanumeric characters with hyphens.
      - Collapse multiple hyphens.
      - Strip leading/trailing hyphens.
      - Truncate to a reasonable length (60 chars).
    """
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    if len(s) > 60:
        s = s[:60].rstrip("-")
    return s


def patch_file(path: Path, target_heading: str, slug: str, dry_run: bool = False) -> str:
    """Insert or update :CUSTOM_ID: for target_heading in path.

    Returns: "added" | "updated" | "skipped-already-set" | "not-found".
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out_lines: list[str] = []
    i = 0
    n = len(lines)
    status = "not-found"
    while i < n:
        line = lines[i]
        m = HEADING_RE.match(line.rstrip("\n"))
        if m and m.group(2).strip() == target_heading:
            # Found the target heading at depth ≤ 2 only (concept-level).
            depth = len(m.group(1))
            if depth > 2:
                out_lines.append(line)
                i += 1
                continue
            out_lines.append(line)
            i += 1
            # Look ahead: is the next non-empty line `:PROPERTIES:`?
            scan = i
            blank_count = 0
            while scan < n and lines[scan].strip() == "":
                blank_count += 1
                scan += 1
            if scan < n and PROPERTIES_BEGIN in lines[scan]:
                # Existing drawer — look for :CUSTOM_ID: inside.
                end_idx = scan + 1
                while end_idx < n and PROPERTIES_END not in lines[end_idx]:
                    end_idx += 1
                drawer = lines[scan : end_idx + 1]
                has_id = any(CUSTOM_ID_LINE.match(d.rstrip("\n")) for d in drawer)
                if has_id:
                    # Already has :CUSTOM_ID: — skip.
                    out_lines.extend(lines[i:end_idx + 1])
                    i = end_idx + 1
                    status = "skipped-already-set"
                else:
                    # Add :CUSTOM_ID: as the first line inside drawer.
                    out_lines.extend(lines[i:scan + 1])  # blanks + :PROPERTIES:
                    out_lines.append(f":CUSTOM_ID: {slug}\n")
                    out_lines.extend(lines[scan + 1:end_idx + 1])
                    i = end_idx + 1
                    status = "updated"
            else:
                # No existing drawer — insert a new one after the heading.
                # Insert immediately after heading line (drop the blanks
                # accumulated by `scan`, they get re-added by remaining loop).
                out_lines.append(":PROPERTIES:\n")
                out_lines.append(f":CUSTOM_ID: {slug}\n")
                out_lines.append(":END:\n")
                status = "added"
            continue
        out_lines.append(line)
        i += 1

    if status in ("added", "updated") and not dry_run:
        path.write_text("".join(out_lines), encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory to scan + backfill")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Show what would change without writing files")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"error: not a directory: {args.root}", file=sys.stderr)
        return 2

    # Run audit to find violations.
    summary = audit(args.root, verbose=False)
    violations = summary["violations"]
    if not violations:
        print("No violations found. Nothing to do.")
        return 0

    print(f"Found {len(violations)} multi-referenced sections without :CUSTOM_ID:.")
    if args.dry_run:
        print("(DRY RUN — no files will be modified)\n")

    by_status = {"added": 0, "updated": 0, "skipped-already-set": 0, "not-found": 0}
    failures: list[tuple[Path, str]] = []
    for file, text, refs in violations:
        slug = slugify(text)
        if not slug:
            print(f"  SKIP (empty slug): {file} :: * {text}", file=sys.stderr)
            failures.append((file, text))
            continue
        status = patch_file(file, text, slug, dry_run=args.dry_run)
        by_status[status] += 1
        if args.verbose:
            rel = file.relative_to(args.root) if file.is_relative_to(args.root) else file
            print(f"  {status:25s} | refs={refs} | {rel}:* {text}  →  :CUSTOM_ID: {slug}")
        if status == "not-found":
            failures.append((file, text))

    print("\nResult:")
    for s, count in by_status.items():
        print(f"  {s}: {count}")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for file, text in failures:
            print(f"  {file}: * {text}")
        return 1

    if not args.dry_run:
        # Re-run audit to confirm.
        new_summary = audit(args.root, verbose=False)
        print(f"\nPost-backfill coverage: {new_summary['coverage_pct']:.1f}%")
        if new_summary["coverage_pct"] >= 95.0:
            print("  → healthy")
        else:
            print(f"  → still below 95% threshold ({new_summary['without_anchor']} sections remain without anchor)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
