"""Audit LP sync metadata for consistency.

Per `rules/lp-resync-metadata.md`, verifies the schema invariants
that don't require tree-sitter (those defer to S5+S6 work).

Invariants checked in this S4-lite version:
  - I1  SHA presence: every .org with :tangle has LITERATE_ORG_SOURCE_SHA
  - I3  block-kind / noweb link: every block with kind=noweb-leaf has
         a :LITERATE_ORG_NOWEB_PARENT: pointing to an existing :CUSTOM_ID:
         in the same file with kind=skeleton
  - F1  format: SHA matches /^[a-f0-9]{7,40}$/
  - F2  format: SHA_DATE parses as ISO8601
  - F3  format: BLOCK_KIND value is one of {atomic, skeleton, noweb-leaf, prose-only}

Invariants deferred to S5+S6 (require tree-sitter):
  - I2 tangle round-trip (checked by `make check-tangle-drift`)
  - I4 CONTAINS_DEFS ↔ block content (needs tree-sitter)
  - I5 no duplicate CONTAINS_DEFS (needs tree-sitter)
  - I6 EXCLUDED_DEFS ↔ source (needs source-tree walk + tree-sitter)

CLI:
  python3 scripts/audit_lp_sync_metadata.py <root>
  python3 scripts/audit_lp_sync_metadata.py <root> --verbose
  python3 scripts/audit_lp_sync_metadata.py <root> --check-presence
        # only I1 (presence-of-SHA);
        # used by /lp-resync Phase A pre-flight

Exit code: 0 = all invariants pass; 1 = at least one violation.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HEADING_RE = re.compile(r"^(\*+)\s+(.+?)\s*(?::[\w@:]+:)?$")
PROP_FILE_RE = re.compile(r"^#\+PROPERTY:\s+(\S+)\s+(.*)$")
PROP_DRAWER_LINE_RE = re.compile(r"^\s*:([A-Z_][A-Z_0-9]*):\s*(.*?)\s*$")
TANGLE_RE = re.compile(r":tangle\s+([^\s]+)")
SHA_RE = re.compile(r"^[a-f0-9]{7,40}$")
VALID_KINDS = {"atomic", "skeleton", "noweb-leaf", "prose-only"}


def parse_iso8601(s: str) -> bool:
    """Best-effort ISO8601 parse — accept several common shapes."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def has_tangle(text: str) -> bool:
    """Check whether file contains at least one real :tangle target
    (excluding :tangle no AND template placeholders).

    Scans only CONTEXTS where :tangle is meaningful (#+begin_src lines,
    :header-args inside drawer, #+PROPERTY: header-args), ignoring
    prose mentions like `the =:tangle <path>= header...` or ASCII
    diagram annotations.

    Template files like _template.org have tangle paths with literal
    `<sub>` / `<placeholder>` brackets — these are intentionally
    unresolvable and the file should NOT require a SOURCE_SHA stamp.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not (line.lower().startswith("#+begin_src")
                or stripped.startswith(":header-args")
                or (line.startswith("#+PROPERTY:") and ":tangle" in line)):
            continue
        for m in TANGLE_RE.finditer(line):
            path = m.group(1)
            if path == "no":
                continue
            # Template placeholder — skip
            if "<" in path or ">" in path:
                continue
            return True
    return False


def parse_file(org_file: Path) -> dict:
    """Walk file once, collect everything the audit needs."""
    text = org_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    file_props: dict[str, str] = {}
    headings: list[dict] = []  # [{depth, text, line, props, custom_id, has_tangle}]
    current_heading: dict | None = None
    in_drawer = False
    in_src = False

    for idx, raw in enumerate(lines):
        line = raw

        # File-level #+PROPERTY:
        if not headings and (line.startswith("#+PROPERTY:") or line.startswith("#+property:")):
            m = PROP_FILE_RE.match(line)
            if m:
                file_props[m.group(1)] = m.group(2).strip()
            continue

        # Heading
        m = HEADING_RE.match(line)
        if m and not in_src:
            current_heading = {
                "depth": len(m.group(1)),
                "text": m.group(2).strip(),
                "line": idx + 1,
                "props": {},
                "custom_id": None,
                "has_tangle": False,
                "block_kind": None,
                "noweb_parent": None,
            }
            headings.append(current_heading)
            in_drawer = False
            continue

        # PROPERTIES drawer
        if line.strip() == ":PROPERTIES:":
            in_drawer = True
            continue
        if line.strip() == ":END:":
            in_drawer = False
            continue
        if in_drawer and current_heading is not None:
            pm = PROP_DRAWER_LINE_RE.match(line)
            if pm:
                key = pm.group(1)
                value = pm.group(2).strip()
                current_heading["props"][key] = value
                if key == "CUSTOM_ID":
                    current_heading["custom_id"] = value
                elif key == "LITERATE_ORG_BLOCK_KIND":
                    current_heading["block_kind"] = value
                elif key == "LITERATE_ORG_NOWEB_PARENT":
                    current_heading["noweb_parent"] = value
            continue

        # src block start/end
        if line.lower().startswith("#+begin_src"):
            in_src = True
            if current_heading is not None and TANGLE_RE.search(line):
                # heading owns at least one :tangle src
                t = TANGLE_RE.search(line)
                if t and t.group(1) != "no":
                    current_heading["has_tangle"] = True
            continue
        if line.lower().startswith("#+end_src"):
            in_src = False
            continue

    # Build CUSTOM_ID index for cross-reference check
    custom_ids: dict[str, dict] = {}
    for h in headings:
        if h["custom_id"]:
            custom_ids[h["custom_id"]] = h

    return {
        "file_props": file_props,
        "headings": headings,
        "custom_ids": custom_ids,
        "has_tangle_anywhere": has_tangle(text),
    }


def audit_file(org_file: Path, check_presence_only: bool = False) -> list[dict]:
    """Return list of violation dicts: {invariant, severity, location, message}."""
    data = parse_file(org_file)
    violations: list[dict] = []

    if not data["has_tangle_anywhere"]:
        # No tangle target — schema doesn't apply
        return violations

    # I1: SHA presence
    sha = data["file_props"].get("LITERATE_ORG_SOURCE_SHA")
    if not sha:
        violations.append({
            "invariant": "I1",
            "severity": "error",
            "location": f"{org_file}:0",
            "message": "missing LITERATE_ORG_SOURCE_SHA file-level property",
        })
    elif not check_presence_only:
        # F1: SHA format
        if not SHA_RE.match(sha):
            violations.append({
                "invariant": "F1",
                "severity": "error",
                "location": f"{org_file}:0",
                "message": f"LITERATE_ORG_SOURCE_SHA '{sha}' does not match hex SHA format",
            })

    if check_presence_only:
        return violations

    # F2: SHA_DATE format
    sha_date = data["file_props"].get("LITERATE_ORG_SOURCE_SHA_DATE")
    if sha and not sha_date:
        violations.append({
            "invariant": "F2",
            "severity": "warn",
            "location": f"{org_file}:0",
            "message": "LITERATE_ORG_SOURCE_SHA present but SHA_DATE missing",
        })
    elif sha_date and not parse_iso8601(sha_date):
        violations.append({
            "invariant": "F2",
            "severity": "warn",
            "location": f"{org_file}:0",
            "message": f"LITERATE_ORG_SOURCE_SHA_DATE '{sha_date}' is not ISO8601",
        })

    for h in data["headings"]:
        loc = f"{org_file}:{h['line']}:* {h['text']}"

        # Headings with tangle should have BLOCK_KIND
        if h["has_tangle"] and not h["block_kind"]:
            violations.append({
                "invariant": "I3a",
                "severity": "error",
                "location": loc,
                "message": "tangle-bearing heading missing :LITERATE_ORG_BLOCK_KIND:",
            })

        # F3: BLOCK_KIND value validity
        if h["block_kind"] and h["block_kind"] not in VALID_KINDS:
            violations.append({
                "invariant": "F3",
                "severity": "error",
                "location": loc,
                "message": f"invalid :LITERATE_ORG_BLOCK_KIND: '{h['block_kind']}'; "
                           f"expected one of {sorted(VALID_KINDS)}",
            })

        # I3: noweb-leaf must have NOWEB_PARENT pointing at valid skeleton
        if h["block_kind"] == "noweb-leaf":
            parent = h["noweb_parent"]
            if not parent:
                violations.append({
                    "invariant": "I3b",
                    "severity": "error",
                    "location": loc,
                    "message": "noweb-leaf without :LITERATE_ORG_NOWEB_PARENT:",
                })
            else:
                target = data["custom_ids"].get(parent)
                if not target:
                    violations.append({
                        "invariant": "I3c",
                        "severity": "error",
                        "location": loc,
                        "message": f"NOWEB_PARENT '{parent}' does not match any "
                                   f":CUSTOM_ID: in this file",
                    })
                elif target.get("block_kind") not in (None, "skeleton"):
                    violations.append({
                        "invariant": "I3d",
                        "severity": "error",
                        "location": loc,
                        "message": f"NOWEB_PARENT '{parent}' targets a "
                                   f"{target.get('block_kind')!r} block, not skeleton",
                    })

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="file or directory to audit")
    parser.add_argument("--check-presence", action="store_true",
                        help="only check I1 (SHA presence); used by /lp-resync Phase A")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.root.is_file():
        files = [args.root]
    elif args.root.is_dir():
        files = sorted(args.root.rglob("*.org"))
    else:
        print(f"error: not a file or directory: {args.root}", file=sys.stderr)
        return 2

    all_violations: list[dict] = []
    by_invariant: dict[str, int] = defaultdict(int)
    files_with_violations = 0
    for f in files:
        v = audit_file(f, check_presence_only=args.check_presence)
        if v:
            files_with_violations += 1
            all_violations.extend(v)
            for vi in v:
                by_invariant[vi["invariant"]] += 1

    print(f"Audit {args.root} ({len(files)} .org files)")
    print(f"  Files with violations: {files_with_violations}")
    print(f"  Total violations: {len(all_violations)}")
    if by_invariant:
        print(f"  By invariant:")
        for k, c in sorted(by_invariant.items()):
            print(f"    {k}: {c}")

    if args.verbose and all_violations:
        print("\nViolations:")
        for v in all_violations[:100]:
            print(f"  [{v['severity']:5s}] {v['invariant']:4s} {v['location']}")
            print(f"          {v['message']}")
        if len(all_violations) > 100:
            print(f"  ... and {len(all_violations) - 100} more")

    return 0 if not all_violations else 1


if __name__ == "__main__":
    sys.exit(main())
