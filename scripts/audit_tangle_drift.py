"""Detect tangle drift — files in ``repos/<sub>/`` that diverge from their
owning ``lp/<sub>/<x>.org`` source.

What this catches
-----------------
Runs ``make tangle-repo`` for every LP-onboarded submodule, then
``git -C repos/<sub> diff --stat``. Any non-empty diff means one of:

  (a) An ``.org`` was edited but tangle was never rerun (benign — common
      while iterating; ``make tangle-all`` resolves).
  (b) A ``.py`` / ``.ts`` / ``.tsx`` / ``.rs`` / ``.tf`` under ``repos/<sub>/``
      was written DIRECTLY — either:
        - Edit / Write / MultiEdit (should have been blocked by
          ``.claude/hooks/block-tangled-edit.sh``), OR
        - Bash sed / awk / perl / tee / redirect / cp / mv (should have
          been blocked by ``.claude/hooks/block-bash-tangle-write.sh``).
      If either of those hooks let it through, this audit finds it.

The hooks are regex-driven; they will always have edge cases (see
Anthropic GH #29709, #31292). This audit is the post-hoc detection layer.
Run before commit, or wire into a pre-commit hook, to catch what the
PreToolUse hooks missed.

Usage
-----
  uv run python scripts/audit_tangle_drift.py            # every LP-onboarded sub
  uv run python scripts/audit_tangle_drift.py <sub> ...  # specific submodules
  uv run python scripts/audit_tangle_drift.py --no-tangle   # skip the tangle pass

Exit codes
----------
  0 — clean, no drift
  1 — drift detected (per-submodule diff printed)
  2 — pre-flight error (tangle command failed, missing repo, etc.)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def list_lp_onboarded_submodules() -> list[str]:
    """Submodules under ``repos/`` that have a matching ``lp/<sub>/`` folder
    containing at least one non-underscore ``.org`` file (i.e. real LP
    sources, not just templates)."""
    repos = REPO_ROOT / "repos"
    lp = REPO_ROOT / "lp"
    if not repos.is_dir() or not lp.is_dir():
        return []
    subs: list[str] = []
    for sub_dir in sorted(repos.iterdir()):
        if not sub_dir.is_dir():
            continue
        lp_dir = lp / sub_dir.name
        if not lp_dir.is_dir():
            continue
        # At least one non-template .org. _project.org / README.org count.
        if any(p.suffix == ".org" for p in lp_dir.iterdir()):
            subs.append(sub_dir.name)
    return subs


def tangle_repo(sub: str) -> tuple[int, str]:
    """Run ``make tangle-repo REPO=<sub>`` and return ``(rc, output)``."""
    proc = subprocess.run(
        ["make", "tangle-repo", f"REPO={sub}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def diff_stat(sub: str) -> str:
    """``git -C repos/<sub> diff --stat`` — empty string = clean."""
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT / "repos" / sub), "diff", "--stat"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Audit LP submodules for tangle drift",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage", 1)[1] if "Usage" in __doc__ else None,
    )
    p.add_argument(
        "submodules",
        nargs="*",
        help="Specific submodule names to audit; default = every LP-onboarded one.",
    )
    p.add_argument(
        "--no-tangle",
        action="store_true",
        help="Skip the tangle step; just check the current working-tree diff state.",
    )
    args = p.parse_args()

    targets = args.submodules or list_lp_onboarded_submodules()
    if not targets:
        print("audit_tangle_drift: no LP-onboarded submodules found", file=sys.stderr)
        return 0

    drift: dict[str, str] = {}
    print(f"auditing {len(targets)} submodule(s)...")
    for sub in targets:
        if not (REPO_ROOT / "repos" / sub).is_dir():
            print(f"  skip {sub}: not a submodule under repos/", file=sys.stderr)
            continue
        if not args.no_tangle:
            print(f"  tangling {sub}...", end=" ", flush=True)
            rc, out = tangle_repo(sub)
            if rc != 0:
                print("FAIL")
                print(out, file=sys.stderr)
                return 2
            print("OK")
        diff = diff_stat(sub)
        if diff:
            drift[sub] = diff

    if not drift:
        print(f"\n✓ no tangle drift across {len(targets)} submodule(s)")
        return 0

    print(
        f"\n✗ tangle drift in {len(drift)} of {len(targets)} submodule(s):",
        file=sys.stderr,
    )
    for sub, diff in drift.items():
        print(f"\n[repos/{sub}]", file=sys.stderr)
        for line in diff.splitlines():
            print(f"  {line}", file=sys.stderr)
    print(
        "\nWhat this means:\n"
        "  Each modified file = either (a) the .org changed but tangle was never\n"
        "  run, or (b) the file was written DIRECTLY (via Edit, or via Bash\n"
        "  sed/cp/redirect/etc.) bypassing the LP hooks.\n"
        "\nFix:\n"
        "  - For (a) — common while iterating:\n"
        "      git -C repos/<sub> diff       # inspect; if intended, commit\n"
        "  - For (b) — the bypassed write must be re-done through the owning .org:\n"
        "      inspect the diff to find the changed lines, locate the owning\n"
        "      section via .cache/tangle-map.tsv, port the change into prose +\n"
        "      src block, then re-tangle and verify diff is empty.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
