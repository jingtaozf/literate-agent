"""Audit :CUSTOM_ID: coverage on multi-referenced sections.

Per `rules/lp-stable-anchors-for-multi-referenced-sections.md`, sections
referenced ≥ 2 times need a `:CUSTOM_ID:` anchor; single-reference
sections may rely on heading text. The raw heading-count metric used in
the Q2 2026 audit (93-98% "missing :CUSTOM_ID:") was misleading because
it counted single-reference sections. This script computes the
*load-bearing* metric: anchor coverage on the multi-referenced subset.

Method:
  1. Walk all .org files in the target tree.
  2. Parse every heading + its :CUSTOM_ID: drawer (if present).
  3. Parse every cross-reference: ``[[*Heading]]``, ``[[#anchor]]``,
     ``[[file:other.org::*Heading]]``, ``[[file:other.org::#anchor]]``.
  4. Count references per heading-text and per anchor.
  5. Emit:
     - Total headings.
     - Total cross-referenced (any).
     - Multi-referenced (≥ 2 refs) without :CUSTOM_ID: → VIOLATIONS.
     - Coverage % on multi-referenced subset.
  6. Threshold per the rule: ≥ 95% healthy, < 90% needs backfill work.

CLI:
  python scripts/audit_anchor_coverage.py <root>
  python scripts/audit_anchor_coverage.py <root> --verbose

Exit code: 0 = healthy (≥ 95%), 1 = backfill needed (< 95%).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

HEADING_RE = re.compile(r"^(\*+)\s+(.+?)\s*(?::[\w@:]+:)?$")
CUSTOM_ID_RE = re.compile(r"^\s*:CUSTOM_ID:\s*(\S+)")
PROPERTIES_BEGIN = ":PROPERTIES:"
PROPERTIES_END = ":END:"

# Link patterns. Org link grammar admits both [[*Heading]] and [[#anchor]]
# in-file, plus [[file:other.org::*Heading]] / [[file:other.org::#anchor]]
# cross-file. We do NOT distinguish in-file vs cross-file refs because
# the rule's "≥ 2 references" counts both.
LINK_HEADING_RE = re.compile(r"\[\[(?:file:[^:\]]+::)?\*([^\]\[]+?)\](?:\[[^\]]*\])?\]")
LINK_ANCHOR_RE = re.compile(r"\[\[(?:file:[^:\]]+::)?#([^\]\[]+?)\](?:\[[^\]]*\])?\]")


def collect_headings(path: Path) -> list[tuple[str, str | None]]:
    """Return [(heading_text, anchor_or_None), ...] for one .org file.

    Concept-level only (depth ≤ 2). Deeper headings exist for
    literate-org-import statement-per-heading style and are not the
    anchor-coverage rule's load-bearing targets.
    """
    headings: list[tuple[str, str | None]] = []
    pending_heading: str | None = None
    in_props = False
    pending_anchor: str | None = None

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = HEADING_RE.match(line)
            if m:
                # Flush previous pending heading.
                if pending_heading is not None:
                    headings.append((pending_heading, pending_anchor))
                depth = len(m.group(1))
                if depth <= 2:
                    pending_heading = m.group(2).strip()
                    pending_anchor = None
                else:
                    pending_heading = None
                    pending_anchor = None
                in_props = False
                continue
            if pending_heading is None:
                continue
            if PROPERTIES_BEGIN in line:
                in_props = True
                continue
            if in_props and PROPERTIES_END in line:
                in_props = False
                continue
            if in_props:
                m_id = CUSTOM_ID_RE.match(line)
                if m_id:
                    pending_anchor = m_id.group(1).strip()
    if pending_heading is not None:
        headings.append((pending_heading, pending_anchor))
    return headings


def collect_refs(path: Path) -> tuple[list[str], list[str]]:
    """Return (heading_text_refs, anchor_refs) found anywhere in the
    file's prose (cross-references TO other sections, in-file or
    cross-file)."""
    heading_refs: list[str] = []
    anchor_refs: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for m in LINK_HEADING_RE.finditer(line):
                heading_refs.append(m.group(1).strip())
            for m in LINK_ANCHOR_RE.finditer(line):
                anchor_refs.append(m.group(1).strip())
    return heading_refs, anchor_refs


def audit(root: Path, verbose: bool = False) -> dict:
    """Run the audit across all .org files under root. Returns a dict
    summary; emits per-violation lines when verbose."""
    org_files = list(root.rglob("*.org"))
    # Index headings: heading_text -> [(file, anchor)]
    headings_by_text: dict[str, list[tuple[Path, str | None]]] = defaultdict(list)
    headings_by_anchor: dict[str, list[Path]] = defaultdict(list)
    for f in org_files:
        for text, anchor in collect_headings(f):
            headings_by_text[text].append((f, anchor))
            if anchor:
                headings_by_anchor[anchor].append(f)

    # Count refs across all files. A ref to "Heading" counts toward
    # every section that has that heading text; ref to "#anchor" counts
    # toward every section with that anchor.
    ref_count_by_text: dict[str, int] = defaultdict(int)
    ref_count_by_anchor: dict[str, int] = defaultdict(int)
    for f in org_files:
        heading_refs, anchor_refs = collect_refs(f)
        for r in heading_refs:
            ref_count_by_text[r] += 1
        for r in anchor_refs:
            ref_count_by_anchor[r] += 1

    # For each concept-level heading, compute its effective ref count:
    # ref-by-text + ref-by-anchor (if it has an anchor).
    multi_ref_total = 0
    multi_ref_with_anchor = 0
    violations: list[tuple[Path, str, int]] = []
    for text, locations in headings_by_text.items():
        for (file, anchor) in locations:
            refs = ref_count_by_text.get(text, 0)
            if anchor:
                refs += ref_count_by_anchor.get(anchor, 0)
            if refs >= 2:
                multi_ref_total += 1
                if anchor:
                    multi_ref_with_anchor += 1
                else:
                    violations.append((file, text, refs))

    total_headings = sum(len(v) for v in headings_by_text.values())
    coverage_pct = (
        100 * multi_ref_with_anchor / multi_ref_total if multi_ref_total else 100.0
    )

    summary = {
        "total_files": len(org_files),
        "total_concept_headings": total_headings,
        "multi_referenced_sections": multi_ref_total,
        "with_anchor": multi_ref_with_anchor,
        "without_anchor": multi_ref_total - multi_ref_with_anchor,
        "coverage_pct": coverage_pct,
        "violations": violations,
    }

    if verbose and violations:
        print(f"\nViolations ({len(violations)} multi-referenced sections without :CUSTOM_ID:):")
        for f, text, refs in sorted(violations, key=lambda v: -v[2])[:50]:
            rel = f.relative_to(root) if f.is_relative_to(root) else f
            print(f"  {refs} refs | {rel}:* {text}")
        if len(violations) > 50:
            print(f"  ... and {len(violations) - 50} more")

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory to scan recursively")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--threshold",
        type=float,
        default=95.0,
        help="Healthy coverage threshold; below = exit 1 (default 95)",
    )
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"error: not a directory: {args.root}", file=sys.stderr)
        return 2

    summary = audit(args.root, verbose=args.verbose)
    print(f"Scanned {summary['total_files']} .org files under {args.root}")
    print(f"  Concept-level headings (depth ≤ 2): {summary['total_concept_headings']}")
    print(f"  Multi-referenced sections (≥ 2 refs): {summary['multi_referenced_sections']}")
    print(f"  With :CUSTOM_ID: anchor: {summary['with_anchor']}")
    print(f"  Without :CUSTOM_ID: anchor: {summary['without_anchor']}")
    print(f"  Coverage: {summary['coverage_pct']:.1f}% (threshold {args.threshold:.0f}%)")

    if summary["multi_referenced_sections"] == 0:
        print("  (no multi-referenced sections found — coverage metric n/a)")
        return 0
    if summary["coverage_pct"] >= args.threshold:
        print("  → healthy")
        return 0
    print(f"  → backfill needed (below {args.threshold:.0f}% threshold)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
