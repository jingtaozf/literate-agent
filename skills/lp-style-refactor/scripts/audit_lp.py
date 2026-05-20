#!/usr/bin/env python3
"""Audit a single lp/<sub>/<file>.org for LP-style issues.

Pure static analysis — no LLM, no I/O beyond reading the .org and the
.cache/tangle-map.tsv. Designed to run in ≤ 1s on a 7000-line file.

Output is a markdown report that the lp-style-refactor skill consumes
to pick ONE improvement + ONE cleanup per iteration.

Usage:
    python3 audit_lp.py lp/<sub>/<file>.org
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Tunable thresholds (mirror lp-rubric.md)
# ---------------------------------------------------------------------------
MAX_HEADING_DEPTH = 5
# Mirror of scripts/check_org_structure.py RELAXED_FILES + RELAXED_DEPTH.
# Files whose path contains any of these substrings get a deeper cap
# because the surrounding code legitimately nests more (Next.js route
# groups, rust trait-impl-in-mod, etc.). Keep in sync with
# scripts/check_org_structure.py.
RELAXED_DEPTH = 9
RELAXED_FILES = (
    "lp/mega-code-web/",
    "lp/skill-encryption/",
    "lp/mega-ui/",
)
NOWEB_SPLIT_THRESHOLD = 80   # src block lines
NL_OUTLINE_THRESHOLD = 40    # python function lines
ANCHOR_REF_THRESHOLD = 2     # mentions before anchor recommended
AI_PROVENANCE_STALE_MONTHS = 6


def _max_depth_for(path: Path) -> int:
    p = str(path)
    if any(s in p for s in RELAXED_FILES):
        return RELAXED_DEPTH
    return MAX_HEADING_DEPTH

BANNED_GRAB_BAG = {
    "functions", "helpers", "utilities", "utility",
    "misc", "things", "stuff", "implementation",
    "code", "other",
}


# ---------------------------------------------------------------------------
# Parsing primitives
# ---------------------------------------------------------------------------
@dataclass
class Heading:
    depth: int       # number of leading asterisks
    title: str
    line: int        # 1-based
    custom_id: str | None = None


@dataclass
class SrcBlock:
    lang: str
    line_start: int  # 1-based, line of #+BEGIN_SRC
    line_end: int    # line of #+END_SRC
    has_noweb_ref: bool = False
    enclosing_heading: Heading | None = None

    @property
    def body_lines(self) -> int:
        return self.line_end - self.line_start - 1


HEADING_RE = re.compile(r"^(\*+)\s+(.*?)\s*$")
BEGIN_SRC_RE = re.compile(r"^#\+(?:BEGIN_SRC|begin_src)\s*(\S+)?(.*)$")
END_SRC_RE = re.compile(r"^#\+(?:END_SRC|end_src)\s*$")
CUSTOM_ID_RE = re.compile(r"^:CUSTOM_ID:\s+(\S+)\s*$")
PROPERTIES_RE = re.compile(r"^:PROPERTIES:\s*$")
END_DRAWER_RE = re.compile(r"^:END:\s*$")


def parse_org(path: Path) -> tuple[list[Heading], list[SrcBlock], list[str]]:
    """Parse headings + src blocks. Returns (headings, src_blocks, raw_lines)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    headings: list[Heading] = []
    blocks: list[SrcBlock] = []

    in_src = False
    src_start = 0
    src_lang = ""
    src_header_line = ""
    in_drawer = False
    pending_heading: Heading | None = None

    for i, line in enumerate(lines, start=1):
        if not in_src and PROPERTIES_RE.match(line):
            in_drawer = True
            continue
        if in_drawer:
            if END_DRAWER_RE.match(line):
                in_drawer = False
                continue
            m = CUSTOM_ID_RE.match(line)
            if m and pending_heading is not None:
                pending_heading.custom_id = m.group(1)
            continue

        if not in_src:
            m = HEADING_RE.match(line)
            if m:
                depth = len(m.group(1))
                title = m.group(2)
                h = Heading(depth=depth, title=title, line=i)
                headings.append(h)
                pending_heading = h
                continue

            m = BEGIN_SRC_RE.match(line)
            if m:
                in_src = True
                src_start = i
                src_lang = (m.group(1) or "").strip().lower()
                src_header_line = m.group(2) or ""
                continue
        else:
            if END_SRC_RE.match(line):
                # Find which heading this block sits under.
                encl = None
                for h in reversed(headings):
                    if h.line < src_start:
                        encl = h
                        break
                blocks.append(SrcBlock(
                    lang=src_lang,
                    line_start=src_start,
                    line_end=i,
                    has_noweb_ref=bool(re.search(r":noweb-ref\s+\S+", src_header_line)),
                    enclosing_heading=encl,
                ))
                in_src = False
                continue
    return headings, blocks, lines


# ---------------------------------------------------------------------------
# Audit rules
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    rule: str
    severity: str  # "warn" | "info" | "error"
    line: int | None
    message: str


@dataclass
class Report:
    file: Path
    findings: list[Finding] = field(default_factory=list)

    def add(self, **kw):
        self.findings.append(Finding(**kw))


def audit_heading_depth(report: Report, headings: list[Heading], path: Path) -> None:
    cap = _max_depth_for(path)
    for h in headings:
        if h.depth > cap:
            report.add(
                rule="heading-depth",
                severity="error",
                line=h.line,
                message=f"heading depth {h.depth} > {cap}: '{h.title}'",
            )


def audit_grab_bag(report: Report, headings: list[Heading]) -> None:
    for h in headings:
        tnorm = h.title.lower().strip().rstrip(".")
        if tnorm in BANNED_GRAB_BAG:
            report.add(
                rule="grab-bag-name",
                severity="warn",
                line=h.line,
                message=f"grab-bag heading name '{h.title}' — rename to describe the *concept*",
            )


def audit_prose_before_src(report: Report, headings: list[Heading], blocks: list[SrcBlock], raw: list[str]) -> None:
    # Per lp-module-section-hierarchy.md, only the *module-level* parent
    # (depth ≤ 2) is expected to carry prose-before-src. The *** children
    # (Docstring / Import / Function foo / Assignment x = y) wrap a single
    # src block and don't need prose; their parent ** section does.
    for b in blocks:
        h = b.enclosing_heading
        if h is None or h.depth > 2:
            continue
        # Gather lines between heading and block start (exclusive).
        between = raw[h.line:b.line_start - 1]  # 0-based slice
        # Strip property drawer + blanks
        prose_lines = []
        in_drawer = False
        for ln in between:
            s = ln.strip()
            if PROPERTIES_RE.match(s):
                in_drawer = True
                continue
            if in_drawer:
                if END_DRAWER_RE.match(s):
                    in_drawer = False
                continue
            if not s:
                continue
            if s.startswith(":") and s.endswith(":"):
                continue
            prose_lines.append(s)
        if not prose_lines:
            report.add(
                rule="prose-before-src",
                severity="warn",
                line=b.line_start,
                message=f"section '{h.title}' (line {h.line}) opens a #+begin_src with no prose preamble",
            )


def audit_big_src(report: Report, blocks: list[SrcBlock]) -> None:
    for b in blocks:
        if b.body_lines >= NOWEB_SPLIT_THRESHOLD and not b.has_noweb_ref and b.lang == "python":
            report.add(
                rule="big-src-block",
                severity="warn",
                line=b.line_start,
                message=f"src block {b.body_lines} lines ≥ {NOWEB_SPLIT_THRESHOLD} (lang={b.lang}) — noweb-split candidate",
            )


PY_FUNC_DEF_RE = re.compile(r"^(?:async\s+)?def\s+(\w+)\s*\(")


def audit_long_funcs_without_nl_outline(report: Report, blocks: list[SrcBlock], raw: list[str]) -> None:
    for b in blocks:
        if b.lang != "python":
            continue
        body = raw[b.line_start:b.line_end - 1]  # exclude both markers
        # Walk body, find functions, count their span
        i = 0
        while i < len(body):
            line = body[i]
            stripped = line.lstrip()
            m = PY_FUNC_DEF_RE.match(stripped)
            if not m:
                i += 1
                continue
            fname = m.group(1)
            base_indent = len(line) - len(stripped)
            # Find end of function: next non-empty line with indent ≤ base
            j = i + 1
            while j < len(body):
                ln = body[j]
                if ln.strip() and (len(ln) - len(ln.lstrip())) <= base_indent and not PY_FUNC_DEF_RE.match(ln.lstrip()):
                    # decorators on a sibling def? treat as end
                    break
                if PY_FUNC_DEF_RE.match(ln.lstrip()) and (len(ln) - len(ln.lstrip())) <= base_indent and j > i + 1:
                    break
                j += 1
            length = j - i
            if length >= NL_OUTLINE_THRESHOLD:
                # check for NL outline markers `# # ` (with the deliberate double-hash)
                outline_count = sum(1 for ln in body[i:j] if re.match(r"^\s*#\s+#\s", ln))
                if outline_count < 2:
                    abs_line = b.line_start + i + 1
                    report.add(
                        rule="long-func-no-nl-outline",
                        severity="warn",
                        line=abs_line,
                        message=f"function '{fname}' is {length} lines ≥ {NL_OUTLINE_THRESHOLD} but has {outline_count} NL-outline comments (≥ 2 expected)",
                    )
            i = max(i + 1, j)


def audit_bare_cross_file_refs(report: Report, raw: list[str]) -> None:
    # Look for `=...org=` outside of code blocks (we ignore inside #+begin_src)
    in_src = False
    for i, line in enumerate(raw, start=1):
        if BEGIN_SRC_RE.match(line):
            in_src = True
            continue
        if END_SRC_RE.match(line):
            in_src = False
            continue
        if in_src:
            continue
        # match `=anything.org=` but skip if it's inside an [[file:...]] link
        for m in re.finditer(r"=([a-z0-9_/\-]+\.org)=", line):
            target = m.group(1)
            # If the same line contains `[[file:...]` referencing same target, skip
            if f"file:{target.split('/')[-1]}" in line or f"file:{target}" in line:
                continue
            report.add(
                rule="bare-cross-file-ref",
                severity="info",
                line=i,
                message=f"bare ref =${target}= — convert to [[file:{target}::*Heading][readable text]]",
            )


def audit_repeated_section_refs(report: Report, headings: list[Heading], raw: list[str]) -> None:
    # For each heading WITHOUT a CUSTOM_ID, count `[[*<title-prefix>]]` mentions
    text = "\n".join(raw)
    for h in headings:
        if h.custom_id is not None:
            continue
        # Approx match: title's first 30 chars in heading-link form
        title_prefix = h.title.split("—")[0].strip()[:30]
        if len(title_prefix) < 5:
            continue
        pat = re.escape(title_prefix)
        count = len(re.findall(rf"\[\[(?:file:[^\]]+)?\*{pat}", text))
        if count >= ANCHOR_REF_THRESHOLD:
            report.add(
                rule="anchor-candidate",
                severity="info",
                line=h.line,
                message=f"section '{h.title}' referenced {count}× via heading text but lacks :CUSTOM_ID: — add stable anchor",
            )


PROVENANCE_DATE_RE = re.compile(r"Date range:\s*(\d{4})-(\d{2})\s*→\s*(\d{4})-(\d{2})")


def audit_stale_provenance(report: Report, raw: list[str]) -> None:
    now = datetime.now(timezone.utc)
    in_src = False
    for i, line in enumerate(raw, start=1):
        if BEGIN_SRC_RE.match(line):
            in_src = True
            continue
        if END_SRC_RE.match(line):
            in_src = False
            continue
        m = PROVENANCE_DATE_RE.search(line)
        if not m:
            continue
        _y0, _m0, y1, m1 = map(int, m.groups())
        end_date = datetime(y1, m1, 1, tzinfo=timezone.utc)
        months = (now.year - end_date.year) * 12 + (now.month - end_date.month)
        if months >= AI_PROVENANCE_STALE_MONTHS:
            report.add(
                rule="stale-ai-provenance",
                severity="info",
                line=i,
                message=f"AI-PROVENANCE date range ends {y1}-{m1:02d} ({months} mo old, ≥ {AI_PROVENANCE_STALE_MONTHS} threshold) — consider trimming or refreshing",
            )


# ---------------------------------------------------------------------------
# Top-level structural metrics (always shown)
# ---------------------------------------------------------------------------
@dataclass
class Metrics:
    total_lines: int
    n_headings: int
    n_src_blocks: int
    max_depth: int
    src_lang_counts: Counter
    src_size_p50: int
    src_size_p90: int
    src_size_max: int
    n_custom_ids: int


def metrics(raw: list[str], headings: list[Heading], blocks: list[SrcBlock]) -> Metrics:
    sizes = sorted(b.body_lines for b in blocks) or [0]
    p50 = sizes[len(sizes) // 2]
    p90 = sizes[min(len(sizes) - 1, int(len(sizes) * 0.9))]
    return Metrics(
        total_lines=len(raw),
        n_headings=len(headings),
        n_src_blocks=len(blocks),
        max_depth=max((h.depth for h in headings), default=0),
        src_lang_counts=Counter(b.lang for b in blocks),
        src_size_p50=p50,
        src_size_p90=p90,
        src_size_max=max(sizes),
        n_custom_ids=sum(1 for h in headings if h.custom_id),
    )


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------
def render(report: Report, m: Metrics) -> str:
    out = [f"# LP audit — `{report.file}`\n"]
    out.append("## File metrics\n")
    out.append(f"- Total lines: **{m.total_lines}**")
    out.append(f"- Headings: **{m.n_headings}** (max depth {m.max_depth})")
    out.append(f"- Src blocks: **{m.n_src_blocks}** ({dict(m.src_lang_counts)})")
    out.append(f"- Src block size — p50 {m.src_size_p50} / p90 {m.src_size_p90} / max **{m.src_size_max}**")
    out.append(f"- Stable anchors (:CUSTOM_ID:): **{m.n_custom_ids}**\n")

    if not report.findings:
        out.append("## Findings\n\n**No findings.** File is in good shape.")
        return "\n".join(out)

    by_rule = defaultdict(list)
    for f in report.findings:
        by_rule[f.rule].append(f)

    out.append(f"## Findings — **{len(report.findings)} total**\n")
    for rule in sorted(by_rule, key=lambda r: -len(by_rule[r])):
        items = by_rule[rule]
        sev = items[0].severity
        sev_icon = {"error": "🛑", "warn": "⚠️ ", "info": "ℹ️ "}.get(sev, "•")
        out.append(f"### {sev_icon}{rule} — {len(items)} occurrence(s)\n")
        for f in items[:5]:
            line = f"line {f.line}" if f.line else "—"
            out.append(f"- **{line}**: {f.message}")
        if len(items) > 5:
            out.append(f"- … and {len(items) - 5} more")
        out.append("")

    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} lp/<sub>/<file>.org", file=sys.stderr)
        return 2
    path = Path(argv[1]).resolve()
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    headings, blocks, raw = parse_org(path)
    report = Report(file=path)

    audit_heading_depth(report, headings, path)
    audit_grab_bag(report, headings)
    audit_prose_before_src(report, headings, blocks, raw)
    audit_big_src(report, blocks)
    audit_long_funcs_without_nl_outline(report, blocks, raw)
    audit_bare_cross_file_refs(report, raw)
    audit_repeated_section_refs(report, headings, raw)
    audit_stale_provenance(report, raw)

    m = metrics(raw, headings, blocks)
    print(render(report, m))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
