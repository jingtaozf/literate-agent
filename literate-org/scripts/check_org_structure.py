"""Structural lint for literate-org.org.

Enforces the rules in .claude/rules/literate-org-document-first.md that
can be checked mechanically:

  1. Section nesting depth ≤ MAX_DEPTH (currently 5).
  2. No grab-bag headings (Functions / Helpers / Utilities / Misc / Things / Stuff).
  3. Sections that tangle to a Python file open with prose, not a src block.

The depth check is a guardrail, not a target. The intent is to flag the
AI failure mode of drilling deeper because each individual addition feels
locally reasonable, while the global org layout decays. When this lint
fires, the right reaction is to look at the surrounding hierarchy —
not to raise the cap.

Exits non-zero on any violation. Designed to be invoked from `make
check-structure` and from CI.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TARGET = Path("literate-org.org")
MAX_DEPTH = 5
GRAB_BAG_RE = re.compile(
    r"^(Functions|Helpers|Utilities|Misc|Things|Stuff)\s*(?::[\w:]+:)?\s*$",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(\*+)\s+(.*?)\s*$")
TANGLE_PY_RE = re.compile(r":tangle\s+\S*literate_python/[^\s]+\.py")
SRC_BEGIN_RE = re.compile(r"^\s*#\+(?:BEGIN_SRC|begin_src)\b", re.IGNORECASE)


@dataclass
class Violation:
    line: int
    rule: str
    message: str

    def format(self, path: Path) -> str:
        return f"{path}:{self.line}: [{self.rule}] {self.message}"


def lint(path: Path) -> list[Violation]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[Violation] = []

    sections: list[tuple[int, int, str]] = []  # (lineno, depth, heading)
    for idx, line in enumerate(lines, start=1):
        m = HEADING_RE.match(line)
        if m:
            depth = len(m.group(1))
            heading = m.group(2)
            sections.append((idx, depth, heading))
            if depth > MAX_DEPTH:
                violations.append(
                    Violation(
                        idx,
                        f"depth>{MAX_DEPTH}",
                        f"section nesting depth is {depth}, max is {MAX_DEPTH}: {heading!r}",
                    )
                )
            stripped = re.sub(r"\s*:[\w:]+:\s*$", "", heading).strip()
            if GRAB_BAG_RE.match(stripped):
                violations.append(
                    Violation(
                        idx,
                        "grab-bag-heading",
                        f"forbidden grab-bag heading {stripped!r} — name the concept",
                    )
                )

    violations.extend(check_prose_before_src(lines))
    return violations


def check_prose_before_src(lines: list[str]) -> list[Violation]:
    """For every section that tangles to literate_python/*.py, the lines
    between its heading and the next heading or the end of file must
    contain at least one non-empty prose line *before* the first src block.
    """
    out: list[Violation] = []
    section_starts: list[tuple[int, int]] = []  # (lineno_idx_0based, depth)
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            section_starts.append((i, len(m.group(1))))
    section_starts.append((len(lines), 0))  # sentinel

    for s_idx in range(len(section_starts) - 1):
        start, _depth = section_starts[s_idx]
        end, _next_depth = section_starts[s_idx + 1]
        body = lines[start + 1 : end]
        body_text = "\n".join(body)
        if not TANGLE_PY_RE.search(body_text):
            continue

        first_src_offset = None
        for j, line in enumerate(body):
            if SRC_BEGIN_RE.match(line):
                first_src_offset = j
                break
        if first_src_offset is None:
            continue

        before_src = body[:first_src_offset]
        has_prose = any(
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith(":")
            and not stripped.startswith("*")
            for stripped in (line.strip() for line in before_src)
        )
        if not has_prose:
            heading_lineno = start + 1
            out.append(
                Violation(
                    heading_lineno,
                    "no-prose-before-src",
                    "section tangles to literate_python/*.py but has no prose before the first src block",
                )
            )
    return out


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else DEFAULT_TARGET
    if not target.exists():
        print(f"check-structure: {target} not found", file=sys.stderr)
        return 1
    violations = lint(target)
    for v in violations:
        print(v.format(target))
    if violations:
        print(
            f"\n{len(violations)} structural violation(s) in {target}", file=sys.stderr
        )
        return 1
    print(f"check-structure: {target} OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
