#!/usr/bin/env python3
"""Unit + integration tests for the cross-project owning-project detection.

The 2026-05-21 incident: a claude session whose ``CLAUDE_PROJECT_DIR`` was
``mind-ai/dev-agent`` directly edited multiple ``.py`` and ``.tf`` files
in ``mind-ai/edo-literate/repos/...`` because the block hook only checked
"is the file under CLAUDE_PROJECT_DIR" — cross-project absolute paths slipped
through.

The fix walks up from the file path to find the OWNING LP-managed project
(any dir containing ``.claude/hooks/_env.sh``) and evaluates scope using that
project's config.  These tests pin both the helper functions and the
end-to-end hook entry points so the bug can't silently regress.

Run from anywhere: ``python3 hooks/test_cross_project.py``
Exit 0 on all-pass, non-zero on any failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS_DIR))


def _make_fake_project(tmp: Path, name: str, env_lines: str) -> Path:
    """Create a fake LP-managed project under ``tmp/<name>/`` and return its
    path.  Writes ``.claude/hooks/_env.sh`` with the supplied env lines so
    the owning-project detection has a marker to find."""
    proj = tmp / name
    (proj / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    (proj / ".claude" / "hooks" / "_env.sh").write_text(env_lines)
    return proj


def _run_hook(hook_path: Path, payload: dict, claude_project_dir: Path) -> tuple[int, str]:
    """Invoke a hook script with a JSON payload on stdin.  Returns
    ``(exit_code, stderr)``.  Drops ``LITERATE_AGENT_*`` from the env so the
    test runner's process-wide settings don't leak into the hook — the only
    config the hook sees is whatever ``CLAUDE_PROJECT_DIR/.claude/hooks/_env.sh``
    OR the owning project's ``_env.sh`` provides."""
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("LITERATE_AGENT_")
    }
    env["CLAUDE_PROJECT_DIR"] = str(claude_project_dir)
    result = subprocess.run(
        ["python3", str(hook_path)],
        input=json.dumps(payload),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result.returncode, result.stderr


PASS = 0
FAIL = 0


def check(label: str, want: int, got: int, stderr: str = "") -> None:
    global PASS, FAIL
    if got == want:
        print(f"  ✓ {label:<55s}  exit={got}")
        PASS += 1
    else:
        print(f"  ✗ {label:<55s}  want=exit{want} got=exit{got}")
        if stderr:
            for line in stderr.splitlines()[:4]:
                print(f"      stderr: {line}")
        FAIL += 1


# ── helper-level tests (no hook invocation) ─────────────────────────────────


def test_find_owning_project() -> None:
    """``find_owning_project`` walks up to the nearest ``_env.sh`` marker."""
    from lib.tangle_lookup import find_owning_project

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj_a = _make_fake_project(tmp, "proj-a", "")
        # File directly under the project root
        f1 = proj_a / "src" / "module.py"
        f1.parent.mkdir(parents=True, exist_ok=True)
        f1.write_text("# stub")
        # File deep under the project root
        f2 = proj_a / "src" / "deep" / "nested" / "submodule.py"
        f2.parent.mkdir(parents=True, exist_ok=True)
        f2.write_text("# stub")
        # File outside any LP project
        f3 = tmp / "outside.py"
        f3.write_text("# stub")
        # Non-existent file under proj-a — should still resolve to proj-a
        f4 = proj_a / "new" / "future.py"

        expected = str(proj_a.resolve())
        # ``check`` compares ints; flatten the path equality into 0/1 so
        # the same harness works for both helper and exit-code tests.
        got = find_owning_project(str(f1))
        check(
            "find_owning_project: shallow file",
            1, int(got is not None and str(got.resolve()) == expected),
        )
        got = find_owning_project(str(f2))
        check(
            "find_owning_project: deep file",
            1, int(got is not None and str(got.resolve()) == expected),
        )
        # Outside any project → None
        check(
            "find_owning_project: outside any LP project",
            1, int(find_owning_project(str(f3)) is None),
        )
        got = find_owning_project(str(f4))
        check(
            "find_owning_project: non-existent path inside project",
            1, int(got is not None and str(got.resolve()) == expected),
        )


def test_load_project_env_sources_lp_vars_only() -> None:
    """``load_project_env`` returns ``LITERATE_AGENT_*`` exports and ignores
    every other env var the script might define."""
    from lib.tangle_lookup import load_project_env, _env_cache

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(
            tmp,
            "proj-env-test",
            textwrap.dedent("""\
                export LITERATE_AGENT_TANGLED_OUTPUT_EXTS=".py,.tf"
                export LITERATE_AGENT_TANGLED_ROOTS="repos/"
                export SOMETHING_UNRELATED="nope"
            """),
        )
        _env_cache.clear()  # ensure fresh sourcing for this test
        env = load_project_env(proj)
        check(
            "load_project_env: picks up LP vars",
            1,
            int(env.get("LITERATE_AGENT_TANGLED_OUTPUT_EXTS") == ".py,.tf"
                and env.get("LITERATE_AGENT_TANGLED_ROOTS") == "repos/"),
        )
        check(
            "load_project_env: ignores unrelated vars",
            1,
            int("SOMETHING_UNRELATED" not in env),
        )


def test_is_in_block_scope_anywhere_cross_project() -> None:
    """The classifier resolves the path's OWNING project, not the caller's."""
    from lib.tangle_lookup import is_in_block_scope_anywhere, _env_cache

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Owning project: blocks .py + .tf under repos/
        owning = _make_fake_project(
            tmp, "owning",
            textwrap.dedent("""\
                export LITERATE_AGENT_TANGLED_OUTPUT_EXTS=".py,.tf"
                export LITERATE_AGENT_TANGLED_ROOTS="repos/"
            """),
        )
        # Caller project: only .py, no TANGLED_ROOTS filter
        _make_fake_project(
            tmp, "caller",
            textwrap.dedent("""\
                export LITERATE_AGENT_TANGLED_OUTPUT_EXTS=".py"
                export LITERATE_AGENT_TANGLED_ROOTS=""
            """),
        )
        # .py file inside the owning project's repos/ → blocked using
        # owning's config (not caller's)
        py_target = owning / "repos" / "sub" / "main.py"
        py_target.parent.mkdir(parents=True, exist_ok=True)
        py_target.write_text("# stub")
        # .tf file — caller's config wouldn't block (.tf not in caller's
        # exts) but owning's config DOES.
        tf_target = owning / "repos" / "infra" / "main.tf"
        tf_target.parent.mkdir(parents=True, exist_ok=True)
        tf_target.write_text("# stub")
        # File under owning project but OUTSIDE its TANGLED_ROOTS → allowed
        script_target = owning / "scripts" / "build.py"
        script_target.parent.mkdir(parents=True, exist_ok=True)
        script_target.write_text("# stub")

        _env_cache.clear()
        blocked, project, env = is_in_block_scope_anywhere(str(py_target))
        check(
            "is_in_block_scope_anywhere: cross-project .py blocked",
            1, int(blocked and project == owning.resolve()),
        )
        blocked, project, env = is_in_block_scope_anywhere(str(tf_target))
        check(
            "is_in_block_scope_anywhere: cross-project .tf blocked via OWNING config",
            1, int(blocked and project == owning.resolve()),
        )
        blocked, project, env = is_in_block_scope_anywhere(str(script_target))
        check(
            "is_in_block_scope_anywhere: file outside TANGLED_ROOTS allowed",
            0, int(blocked),
        )


# ── end-to-end hook tests ───────────────────────────────────────────────────


def test_hook_cross_project_blocks() -> None:
    """Full hook script: cross-project Edit/Write blocked end-to-end."""
    hook = HOOKS_DIR / "block-tangled-edit.sh"

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Owning project blocks .py + .tf under repos/
        owning = _make_fake_project(
            tmp, "owning-e2e",
            textwrap.dedent("""\
                export LITERATE_AGENT_TANGLED_OUTPUT_EXTS=".py,.tf"
                export LITERATE_AGENT_TANGLED_ROOTS="repos/"
            """),
        )
        # Caller has no LP config at all (no _env.sh)
        caller = tmp / "caller-no-lp"
        caller.mkdir()

        py = owning / "repos" / "sub" / "stale.py"
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_text("# stub")
        tf = owning / "repos" / "infra" / "stale.tf"
        tf.parent.mkdir(parents=True, exist_ok=True)
        tf.write_text("# stub")
        random = tmp / "random.py"
        random.write_text("# stub")

        # Re-import the lib in a fresh subprocess each time (the hook runs
        # in a subprocess) so the cache between tests can't pollute results.

        rc, err = _run_hook(
            hook,
            {"tool_name": "Edit",
             "tool_input": {"file_path": str(py)}},
            claude_project_dir=caller,
        )
        check(
            "hook: cross-project .py edit blocked",
            2, rc, err,
        )

        rc, err = _run_hook(
            hook,
            {"tool_name": "Write",
             "tool_input": {"file_path": str(tf)}},
            claude_project_dir=caller,
        )
        check(
            "hook: cross-project .tf write blocked (owning ext list)",
            2, rc, err,
        )

        rc, err = _run_hook(
            hook,
            {"tool_name": "Edit",
             "tool_input": {"file_path": str(random)}},
            claude_project_dir=caller,
        )
        check(
            "hook: random /tmp file allowed (no owning LP project)",
            0, rc, err,
        )

        # File in owning project but outside its tangled root → allowed
        script = owning / "scripts" / "build.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# stub")
        rc, err = _run_hook(
            hook,
            {"tool_name": "Edit",
             "tool_input": {"file_path": str(script)}},
            claude_project_dir=caller,
        )
        check(
            "hook: file outside owning's TANGLED_ROOTS allowed",
            0, rc, err,
        )


def test_hook_same_project_still_works() -> None:
    """Back-compat: when CLAUDE_PROJECT_DIR IS the owning project, the
    pre-fix single-project path should produce the same outcome.  The
    owning-project walk just finds the same project the caller is in."""
    hook = HOOKS_DIR / "block-tangled-edit.sh"

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proj = _make_fake_project(
            tmp, "same-project",
            textwrap.dedent("""\
                export LITERATE_AGENT_TANGLED_OUTPUT_EXTS=".py"
                export LITERATE_AGENT_TANGLED_ROOTS=""
            """),
        )
        py = proj / "module.py"
        py.write_text("# stub")
        md = proj / "README.md"
        md.write_text("# stub")

        rc, err = _run_hook(
            hook,
            {"tool_name": "Edit",
             "tool_input": {"file_path": str(py)}},
            claude_project_dir=proj,
        )
        check("hook: same-project .py blocked", 2, rc, err)

        rc, err = _run_hook(
            hook,
            {"tool_name": "Edit",
             "tool_input": {"file_path": str(md)}},
            claude_project_dir=proj,
        )
        check("hook: same-project .md allowed", 0, rc, err)


def test_bash_hook_cross_project_blocks() -> None:
    """The Bash hook walks the same code path; verify the cross-project
    case also blocks ``sed -i`` against a file in the owning project."""
    hook = HOOKS_DIR / "block-bash-tangle-write.sh"

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        owning = _make_fake_project(
            tmp, "owning-bash",
            textwrap.dedent("""\
                export LITERATE_AGENT_TANGLED_OUTPUT_EXTS=".py"
                export LITERATE_AGENT_TANGLED_ROOTS=""
            """),
        )
        caller = tmp / "caller-bash-no-lp"
        caller.mkdir()

        py = owning / "target.py"
        py.write_text("# stub")

        rc, err = _run_hook(
            hook,
            {"tool_name": "Bash",
             "tool_input": {"command": f"sed -i 's/x/y/' {py}"}},
            claude_project_dir=caller,
        )
        check("bash-hook: cross-project sed -i blocked", 2, rc, err)


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    print("── helper-level tests ──")
    test_find_owning_project()
    test_load_project_env_sources_lp_vars_only()
    test_is_in_block_scope_anywhere_cross_project()

    print("── hook end-to-end tests ──")
    test_hook_cross_project_blocks()
    test_hook_same_project_still_works()
    test_bash_hook_cross_project_blocks()

    print()
    print("═" * 60)
    print(f" Summary: pass={PASS}  fail={FAIL}")
    print("═" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
