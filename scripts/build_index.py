#!/usr/bin/env python3
"""Generate INDEX.org — section-level navigation across LP .org sources.

Unified design (claude-agent base + edo's grouping shell):

  - Scan one OR many .org files.
  - For each file, walk every heading; record sections that have a
    :tangle target. Track per-section :LITERATE_ORG_MODULE: +
    :CUSTOM_ID: properties + heading line number.
  - Emit ONE org table per group, with clickable jump links into the
    owning .org file at the exact line.
  - Optionally include a top-level preamble + per-group elevator
    pitches loaded from external config files.

Layout detection:

  - Multi-file (lp/<sub>/*.org or other grouped layout): one section
    per group, one table per group.
  - Single-file (top-level *.org): one _root group, one table.

Defaults for preamble + groups config live in literate-agent's
templates/ folder. Projects override via CLI flags when they have
their own.

CLI:
    build_index.py [--output PATH]
                   [--preamble PATH]
                   [--groups-config PATH]
                   [--group-by lp|src|none]
                   [file1.org file2.org ...]

If no files are given:
  - If LP_ROOT (default "lp") exists → scan LP_ROOT/**/*.org
  - Else → scan project root for top-level *.org
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# ── configurable roots ─────────────────────────────────────────────────────

PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())).resolve()
LITERATE_AGENT_HOME = Path(
    os.environ.get(
        "LITERATE_AGENT_HOME",
        Path.home() / "projects" / "literate-agent",
    )
).resolve()
LP_ROOT_NAME = os.environ.get("LITERATE_AGENT_LP_ROOT", "lp")

DEFAULT_PREAMBLE = LITERATE_AGENT_HOME / "templates" / "build_index_preamble.md"
DEFAULT_GROUPS_CONFIG = LITERATE_AGENT_HOME / "templates" / "build_index_groups.toml"

# ── parser primitives ──────────────────────────────────────────────────────

HEADING_RE = re.compile(r"^(\*+)\s+(.*?)\s*$")
TANGLE_RE = re.compile(r":tangle\s+(\S+)")
MODULE_RE = re.compile(r":LITERATE_ORG_MODULE:\s+(\S+)")
CUSTOM_ID_RE = re.compile(r":CUSTOM_ID:\s+(\S+)")
TITLE_RE = re.compile(r"^#\+TITLE:\s*(.+?)\s*$", re.I | re.M)


@dataclass
class Entry:
    """One tangled section in a literate .org file."""
    module: str        # :LITERATE_ORG_MODULE: value or derived from tangle path
    source: str        # .org file path, project-relative
    heading: str       # section heading text
    line: int          # 1-based line number in the .org file
    tangle: str        # :tangle target path
    custom_id: str     # :CUSTOM_ID: value or empty


# ── scanning ───────────────────────────────────────────────────────────────

_TANGLE_NEGATIVE = {"no", "yes", '""', "''"}


def scan_org(path: Path, project_root: Path) -> list[Entry]:
    """Walk one .org file; return all tangled sections.

    A section is recorded iff:
    - it has a :tangle target in its own :PROPERTIES: drawer, OR
    - a #+begin_src block inside it has a :tangle target,
    AND
    - the tangle value is not one of {no, yes, '""', "''"}.

    File-level #+PROPERTY: header-args :tangle is NOT inherited as a
    section's own tangle — sections that pure-prose-inside-a-tangling-
    file should not show up as "tangled sections."
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    entries: list[Entry] = []

    rel_source = str(path.resolve().relative_to(project_root))

    current_heading = ""
    current_heading_line = 0
    current_tangle = ""
    current_module = ""
    current_custom_id = ""
    in_properties = False

    def flush():
        if current_tangle and current_tangle not in _TANGLE_NEGATIVE:
            module = current_module or _tangle_to_module(current_tangle)
            entries.append(
                Entry(
                    module=module,
                    source=rel_source,
                    heading=current_heading,
                    line=current_heading_line,
                    tangle=current_tangle,
                    custom_id=current_custom_id,
                )
            )

    for idx, line in enumerate(lines, start=1):
        hm = HEADING_RE.match(line)
        if hm:
            flush()
            current_heading = hm.group(2).strip()
            current_heading_line = idx
            current_tangle = ""
            current_module = ""
            current_custom_id = ""
            in_properties = False
            continue

        if ":PROPERTIES:" in line:
            in_properties = True
            continue
        if ":END:" in line:
            in_properties = False
            continue

        if in_properties:
            tm = TANGLE_RE.search(line)
            if tm:
                current_tangle = tm.group(1)
            mm = MODULE_RE.search(line)
            if mm:
                current_module = mm.group(1)
            cm = CUSTOM_ID_RE.search(line)
            if cm:
                current_custom_id = cm.group(1)

        # Per-block #+BEGIN_SRC ... :tangle target — also valid
        lstripped = line.lstrip()
        if lstripped.startswith("#+BEGIN_SRC") or lstripped.startswith("#+begin_src"):
            tm = TANGLE_RE.search(line)
            if tm:
                current_tangle = tm.group(1)

    flush()
    return entries


def _tangle_to_module(tangle: str) -> str:
    """Derive a module name from a tangle path. Strip leading ./ and
    extension; convert / to .. Works for ./python/pkg/foo.py →
    python.pkg.foo, ./src/lib/bar.ts → src.lib.bar."""
    s = tangle.lstrip("./").rsplit(".", 1)[0]
    return s.replace("/", ".")


# ── grouping ───────────────────────────────────────────────────────────────

def group_key(entry: Entry, mode: str, lp_root: str) -> str:
    """Return group name for an entry. Modes:
      - 'lp': group by directory directly under LP_ROOT (edo-style)
      - 'src': group by tangle path's first directory (claude-agent's
        python/<pkg>/foo.py → pkg)
      - 'none': all entries in '_root'
    """
    if mode == "none":
        return "_root"
    if mode == "lp":
        parts = entry.source.split("/")
        if len(parts) > 2 and parts[0] == lp_root:
            return parts[1]
        return "_root"
    if mode == "src":
        parts = entry.tangle.lstrip("./").split("/")
        if len(parts) > 2:
            return parts[1]  # python/<pkg>/... → pkg
        return "_root"
    return "_root"


def auto_detect_mode(files: list[Path], lp_root: str, project_root: Path) -> str:
    """Pick a sensible default --group-by based on the file layout."""
    lp_path = project_root / lp_root
    if lp_path.is_dir() and any(f.is_relative_to(lp_path) for f in files):
        return "lp"
    return "none"


# ── optional config ────────────────────────────────────────────────────────

def load_preamble(path: Path | None) -> str:
    """Load a preamble file. Strips the leading contiguous block of
    `#`-comment lines (instructional comments for the file's editor)
    so they don't leak into the rendered INDEX.org."""
    if not path or not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    # Skip leading comment block: lines that are blank, or start with
    # '#' followed by space/end (instructional commentary).
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s == "" or s.startswith("# ") or s == "#":
            i += 1
            continue
        break
    body = "\n".join(lines[i:]).strip()
    return body + "\n\n" if body else ""


def load_groups_config(path: Path | None) -> dict[str, str]:
    """Return {group_name: elevator_pitch}. Empty dict if no config."""
    if not path or not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"build_index: warning — could not parse {path}: {e}", file=sys.stderr)
        return {}
    return data.get("groups", {}) if isinstance(data.get("groups"), dict) else {}


# ── rendering ──────────────────────────────────────────────────────────────

def render_index(entries: list[Entry], *, mode: str, lp_root: str,
                 preamble: str, group_pitches: dict[str, str],
                 title: str) -> str:
    grouped: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        grouped[group_key(e, mode, lp_root)].append(e)

    out = [
        f"#+TITLE: {title}",
        "#+OPTIONS: toc:nil num:nil",
        "",
    ]
    if preamble:
        out.append(preamble.rstrip())
        out.append("")

    out.append("Generated by =literate-agent/scripts/build_index.py= — do not edit by hand.")
    out.append("")

    # _root group renders without a heading; everything else gets a heading.
    has_root = "_root" in grouped
    other_groups = sorted(g for g in grouped if g != "_root")

    if has_root and not other_groups:
        # Pure single-file / no groups: just emit one flat table.
        out.append(_render_table(grouped["_root"]))
    else:
        if has_root:
            out.append("* Top-level")
            out.append("")
            out.append(_render_table(grouped["_root"]))
            out.append("")
        for grp in other_groups:
            heading = f"* {grp}"
            pitch = group_pitches.get(grp)
            if pitch:
                heading += f" — {pitch}"
            out.append(heading)
            out.append("")
            out.append(_render_table(grouped[grp]))
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def _render_table(entries: list[Entry]) -> str:
    lines = [
        "| Module | Source | Heading | Line | Tangle | CUSTOM_ID |",
        "|--------+--------+---------+------+--------+-----------|",
    ]
    for e in sorted(entries, key=lambda x: x.module):
        heading_link = f"[[file:{e.source}::{e.line}][={e.heading}=]]"
        custom_id = f"={e.custom_id}=" if e.custom_id else ""
        lines.append(
            f"| ={e.module}= | ={e.source}= | {heading_link} | {e.line} | ={e.tangle}= | {custom_id} |"
        )
    return "\n".join(lines)


# ── main ───────────────────────────────────────────────────────────────────

def discover_org_files(args_files: list[str]) -> list[Path]:
    if args_files:
        return sorted(Path(a).resolve() for a in args_files)
    lp = PROJECT_ROOT / LP_ROOT_NAME
    if lp.is_dir():
        return sorted(
            p for p in lp.rglob("*.org")
            if not p.name.startswith("_") and p.name != "INDEX.org"
        )
    # Fallback: top-level .org in project root (single-repo Python LP).
    return sorted(
        p for p in PROJECT_ROOT.glob("*.org")
        if not p.name.startswith("_") and p.name != "INDEX.org"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*",
                        help=".org files to scan (default: auto-discover)")
    parser.add_argument("--output", default="INDEX.org",
                        help="Output file path (default: INDEX.org)")
    parser.add_argument("--preamble",
                        default=str(DEFAULT_PREAMBLE),
                        help=f"Preamble file (default: {DEFAULT_PREAMBLE})")
    parser.add_argument("--groups-config",
                        default=str(DEFAULT_GROUPS_CONFIG),
                        help=f"Groups TOML config (default: {DEFAULT_GROUPS_CONFIG})")
    parser.add_argument("--group-by", choices=["lp", "src", "none", "auto"],
                        default="auto",
                        help="Grouping strategy (default: auto-detect)")
    parser.add_argument("--title", default=None,
                        help="Index title (default: derived from project root)")
    parser.add_argument("--filter", default=None,
                        help="Only include sections whose tangle path matches "
                             "this regex (e.g. 'python/claude_agent/.*\\.py$')")
    args = parser.parse_args(argv[1:])

    files = discover_org_files(args.files)
    if not files:
        print("build_index: no .org files to scan", file=sys.stderr)
        return 1

    mode = args.group_by
    if mode == "auto":
        mode = auto_detect_mode(files, LP_ROOT_NAME, PROJECT_ROOT)

    all_entries: list[Entry] = []
    for f in files:
        if not f.exists():
            print(f"build_index: {f} not found", file=sys.stderr)
            return 1
        all_entries.extend(scan_org(f, PROJECT_ROOT))

    if args.filter:
        filter_re = re.compile(args.filter)
        all_entries = [e for e in all_entries if filter_re.search(e.tangle)]

    preamble = load_preamble(Path(args.preamble))
    group_pitches = load_groups_config(Path(args.groups_config))

    title = args.title or f"{PROJECT_ROOT.name} — module index"

    output = render_index(
        all_entries,
        mode=mode,
        lp_root=LP_ROOT_NAME,
        preamble=preamble,
        group_pitches=group_pitches,
        title=title,
    )

    out_arg = Path(args.output)
    out_path = out_arg if out_arg.is_absolute() else (PROJECT_ROOT / out_arg).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    n_groups = len({group_key(e, mode, LP_ROOT_NAME) for e in all_entries}) or 1
    try:
        display_out = out_path.relative_to(PROJECT_ROOT)
    except ValueError:
        display_out = out_path
    print(f"build_index: wrote {display_out} ({len(all_entries)} sections in {n_groups} group(s), mode={mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
