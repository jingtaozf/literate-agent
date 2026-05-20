"""Build .cache/tangle-map.tsv — a reverse map from tangled-file path to
the lp/<sub>/<x>.org file that owns it.

Format: TSV, one ``<tangled-rel>\\t<org-rel>`` pair per line, sorted by
tangled-rel. Both paths are project-root-relative.

Why a *map* and not just an *allowlist*: the PreToolUse hook uses
this to look up the *exact owning .org* for any blocked .py / .ts /
.tsx edit, so the rejection message can point the agent at the right
place to edit instead of the generic ``lp/<sub>/`` folder hint.

The hook self-heals by re-running this script on a miss
(content-edited .org may not have refreshed the cache yet); see
``.claude/hooks/block-tangled-edit.sh``.

CLI:
  python scripts/build_tangle_map.py            # scan all lp/**/*.org
  python scripts/build_tangle_map.py file1.org  # scan only the listed files
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Run from the consuming project's root. Honour CLAUDE_PROJECT_DIR when
# set (Claude Code sets this), else assume CWD is project root.
PROJECT_ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())).resolve()
CACHE_FILE = PROJECT_ROOT / ".cache" / "tangle-map.tsv"

# Where literate .org sources live (override with LITERATE_AGENT_LP_ROOT).
LP_ROOT_NAME = os.environ.get("LITERATE_AGENT_LP_ROOT", "lp")

TANGLE_RE = re.compile(r":tangle\s+([^\s:]+)")


def iter_org_files(args: list[str]) -> list[Path]:
    if args:
        return [Path(a).resolve() for a in args]
    lp = PROJECT_ROOT / LP_ROOT_NAME
    # If LP_ROOT exists, scan it; otherwise fall back to scanning the
    # whole project root for top-level .org files (single-repo layout).
    if lp.is_dir():
        return sorted(p for p in lp.rglob("*.org") if not p.name.startswith("_"))
    return sorted(p for p in PROJECT_ROOT.glob("*.org") if not p.name.startswith("_"))


def extract_tangle_targets(org_path: Path) -> set[Path]:
    base = org_path.parent
    targets: set[Path] = set()
    text = org_path.read_text()
    for m in TANGLE_RE.finditer(text):
        token = m.group(1)
        if token in ("no", '""', "yes"):
            continue
        # Reject template placeholders (e.g. ``:tangle <path>``,
        # ``:tangle path/to/{file}.py``) that appear inside prose
        # examples. These would generate spurious cache entries.
        if any(c in token for c in "<>{}*?$"):
            continue
        targets.add((base / token).resolve())
    return targets


def to_project_relative(target: Path) -> str | None:
    try:
        return str(target.relative_to(PROJECT_ROOT))
    except ValueError:
        return None


def main(argv: list[str]) -> int:
    org_files = iter_org_files(argv[1:])

    pairs: dict[str, str] = {}
    conflicts: list[tuple[str, str, str]] = []
    for org in org_files:
        org_rel = to_project_relative(org)
        if org_rel is None:
            continue
        for target in extract_tangle_targets(org):
            tang_rel = to_project_relative(target)
            if tang_rel is None:
                continue
            if tang_rel in pairs and pairs[tang_rel] != org_rel:
                conflicts.append((tang_rel, pairs[tang_rel], org_rel))
                if org_rel < pairs[tang_rel]:
                    pairs[tang_rel] = org_rel
            else:
                pairs[tang_rel] = org_rel

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}\t{v}" for k, v in sorted(pairs.items()))
    CACHE_FILE.write_text(body + ("\n" if body else ""))
    print(
        f"wrote {len(pairs)} mapping(s) to "
        f"{CACHE_FILE.relative_to(PROJECT_ROOT)}"
    )

    if conflicts:
        print(
            f"WARN: {len(conflicts)} tangle target(s) claimed by multiple .org "
            f"files; kept the lexicographically earlier owner.",
            file=sys.stderr,
        )
        for tang, kept, dropped in conflicts[:10]:
            print(f"  {tang}: kept {kept!r}, also in {dropped!r}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
