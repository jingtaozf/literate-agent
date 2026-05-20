"""Lint lp/**/*.org for the LP structural rules.

Three checks (inherited and generalised from skill-scout-server's
`scripts/check_org_structure.py`):

  1. Heading depth ≤ 5. The cap is a guardrail: when it fires, the fix
     is almost always a missing sibling layer or a grab-bag parent.
  2. No grab-bag headings: titles matching ^(Functions|Helpers|
     Utilities|Misc|Things|Stuff)\\s*$ are rejected.
  3. Prose before src: a section that declares a :tangle target must
     have at least one non-empty, non-properties prose line between
     the heading and its first #+begin_src block.

Generalised vs. skill-scout: the third check no longer special-cases
`./skill_scout/` — any section with any non-`:tangle no` :tangle target
must have prose-before-src. This makes the lint work uniformly for
every submodule under repos/.

CLI:
  python scripts/check_org_structure.py [file1.org file2.org ...]

Exit code: 0 = clean; 1 = at least one violation.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())).resolve()
LP_ROOT_NAME = os.environ.get("LITERATE_AGENT_LP_ROOT", "lp")

HEADING_RE = re.compile(r"^(\*+)\s+(.*?)\s*(?::[\w@:]+:)?$")
GRAB_BAG_RE = re.compile(r"^(Functions|Helpers|Utilities|Misc|Things|Stuff)\s*$", re.I)
TANGLE_REAL_RE = re.compile(r":tangle\s+([^\s:]+)")
SRC_BEGIN_RE = re.compile(r"^\s*#\+begin_src\b", re.I)
DRAWER_BEGIN = ":PROPERTIES:"
DRAWER_END = ":END:"
KEYWORD_LINE_RE = re.compile(r"^\s*#\+\w")
COMMENT_LINE_RE = re.compile(r"^\s*#\s")

# Prose-before-src check applies only to sections that tangle to a "code"
# extension. Test-fixture artefacts (.approved.txt, .json, .yaml) don't
# need a prose preamble. Override via env var (comma-separated extensions
# with leading dot):
#
#   LITERATE_AGENT_PROSE_BEFORE_SRC_EXTS=".py,.ts,.tsx,.rs,.tf,.el,.clj"
_DEFAULT_CODE_EXTS = ".py,.ts,.tsx,.rs,.tf,.el,.clj,.go,.rb,.js,.jsx,.java,.kt,.swift,.cpp,.c,.h,.hpp,.cs"
PROSE_BEFORE_SRC_EXTS = tuple(
    s.strip().lower() for s in os.environ.get(
        "LITERATE_AGENT_PROSE_BEFORE_SRC_EXTS", _DEFAULT_CODE_EXTS
    ).split(",") if s.strip()
)

# Default cap is 5 (per literate-programming-document-first.md guardrail).
# Some projects (TS Next.js with parenthesised route groups + nested
# dynamic [slug] segments; deeply nested test fixtures) legitimately
# need a higher cap on specific files. Override via env var:
#
#   LITERATE_AGENT_MAX_DEPTH=5
#   LITERATE_AGENT_RELAXED_DEPTH=9
#   LITERATE_AGENT_RELAXED_FILES="lp/mega-code-web/,lp/skill-encryption/"
#
# Files whose path *contains* any of the colon-separated fragments get
# the relaxed cap.
MAX_DEPTH = int(os.environ.get("LITERATE_AGENT_MAX_DEPTH", "5"))
RELAXED_DEPTH = int(os.environ.get("LITERATE_AGENT_RELAXED_DEPTH", "9"))
RELAXED_FILES = tuple(
    s.strip() for s in os.environ.get("LITERATE_AGENT_RELAXED_FILES", "").split(",")
    if s.strip()
)


@dataclass
class Section:
    file: Path
    line_no: int
    depth: int
    title: str
    tangle_target: str | None  # the path token, or "no" / None
    body_lines: list[tuple[int, str]]  # (line_no, raw line) AFTER drawer/keywords

    @property
    def has_real_tangle(self) -> bool:
        return self.tangle_target not in (None, "no", '""')


def parse(file: Path) -> list[Section]:
    sections: list[Section] = []
    in_drawer = False
    cur_drawer_text = ""
    cur: Section | None = None
    text = file.read_text()
    for n, raw in enumerate(text.splitlines(), 1):
        m = HEADING_RE.match(raw)
        if m:
            if cur is not None:
                # finalise previous section's tangle from its drawer text
                if cur.tangle_target is None:
                    tm = TANGLE_REAL_RE.search(cur_drawer_text)
                    cur.tangle_target = tm.group(1) if tm else None
                sections.append(cur)
            cur = Section(file=file, line_no=n, depth=len(m.group(1)),
                          title=m.group(2), tangle_target=None, body_lines=[])
            in_drawer = False
            cur_drawer_text = ""
            continue
        if cur is None:
            continue
        if raw.strip() == DRAWER_BEGIN:
            in_drawer = True
            continue
        if raw.strip() == DRAWER_END:
            in_drawer = False
            continue
        if in_drawer:
            cur_drawer_text += raw + "\n"
            continue
        cur.body_lines.append((n, raw))
    if cur is not None:
        if cur.tangle_target is None:
            tm = TANGLE_REAL_RE.search(cur_drawer_text)
            cur.tangle_target = tm.group(1) if tm else None
        sections.append(cur)
    return sections


def _cap_for(file: Path) -> int:
    path_str = str(file)
    if any(p in path_str for p in RELAXED_FILES):
        return RELAXED_DEPTH
    return MAX_DEPTH


def violations_depth(secs: list[Section]) -> list[str]:
    out: list[str] = []
    for s in secs:
        cap = _cap_for(s.file)
        if s.depth > cap:
            out.append(
                f"{s.file}:{s.line_no}: heading depth {s.depth} exceeds cap {cap} — "
                f"look for a missing sibling or a grab-bag parent: {s.title!r}"
            )
    return out


def violations_grab_bag(secs: list[Section]) -> list[str]:
    out: list[str] = []
    for s in secs:
        if GRAB_BAG_RE.match(s.title):
            out.append(
                f"{s.file}:{s.line_no}: grab-bag heading {s.title!r} — "
                f"name the concept, not the phase"
            )
    return out


def _tangle_is_code(tangle: str) -> bool:
    """True if the tangle path's extension is a code language (subject
    to prose-before-src) vs fixture data (.txt/.json/.yaml)."""
    lower = tangle.lower()
    return any(lower.endswith(ext) for ext in PROSE_BEFORE_SRC_EXTS)


def violations_prose_before_src(secs: list[Section]) -> list[str]:
    out: list[str] = []
    for s in secs:
        if not s.has_real_tangle:
            continue
        if not _tangle_is_code(s.tangle_target or ""):
            continue
        prose_seen = False
        for line_no, raw in s.body_lines:
            stripped = raw.strip()
            if not stripped:
                continue
            if SRC_BEGIN_RE.match(raw):
                if not prose_seen:
                    out.append(
                        f"{s.file}:{line_no}: section {s.title!r} opens "
                        f"with #+begin_src — needs at least one prose line first"
                    )
                break
            if KEYWORD_LINE_RE.match(raw) or COMMENT_LINE_RE.match(raw):
                continue
            prose_seen = True
    return out


def discover_files() -> list[Path]:
    """Auto-detect: LP_ROOT_NAME subdirectory if it exists (multi-submodule),
    else top-level *.org under project root (single-file LP project)."""
    lp = PROJECT_ROOT / LP_ROOT_NAME
    if lp.is_dir():
        return sorted(p for p in lp.rglob("*.org") if not p.name.startswith("_"))
    return sorted(p for p in PROJECT_ROOT.glob("*.org") if not p.name.startswith("_"))


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv[1:]] if len(argv) > 1 else discover_files()
    if not files:
        print("check_org_structure: no .org files to check; nothing to do.")
        return 0

    all_violations: list[str] = []
    for f in files:
        secs = parse(f)
        all_violations.extend(violations_depth(secs))
        all_violations.extend(violations_grab_bag(secs))
        all_violations.extend(violations_prose_before_src(secs))

    if all_violations:
        for v in all_violations:
            print(v)
        print(f"\n{len(all_violations)} structural violation(s).", file=sys.stderr)
        return 1
    print(f"check_org_structure: {len(files)} file(s) clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
