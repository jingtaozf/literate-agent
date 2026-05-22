"""NL Outline lint for tangled Python.

Implements the rule from .claude/rules/literate-org-document-first.md:
functions whose body is ≥ 40 lines must contain inline natural-language
outline comments of the form ``# # <summary>`` (literate-programming
markdown style: a single ``#`` Python comment followed by another ``#``
that signals "this is an NL outline entry, not a regular comment").

Each NL summary must cover ≥ 3 lines of source. Decorative one-liner
sums  ("# # next we ...") are explicitly rejected by the source paper
(arXiv:2408.04820, Shi et al., FSE'25).

Why a literal ``# # `` marker rather than reusing docstrings or regular
comments: the marker is unambiguous, easy to grep, and survives
formatters (black does not touch comment content). Existing comments
are not retroactively reinterpreted as NL outlines.

Runs over the *tangled* ``.py`` files under literate_python/, not over
the org file directly — Python parsing is more reliable on flat .py
than on extracted org chunks. The rule still applies to the org source;
this lint just checks the artefact.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LONG_FUNCTION_MIN_LINES = 40
MIN_LINES_PER_NL_STATEMENT = 3
NL_OUTLINE_MARKER_RE = re.compile(r"^\s*#\s+#\s+\S")
DEFAULT_ROOT = Path("literate_python")


@dataclass
class Violation:
    file: Path
    line: int
    func: str
    rule: str
    message: str

    def format(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule}] {self.func}(): {self.message}"


def function_body_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return the count of source lines in the function body, excluding
    the ``def`` header line. ``end_lineno`` is set on Python 3.8+."""
    if not node.body:
        return 0
    first = node.body[0].lineno
    last = node.body[-1].end_lineno or node.body[-1].lineno
    return last - first + 1


def find_nl_outline_lines(src_lines: list[str], start: int, end: int) -> list[int]:
    """Return 1-based source line numbers in [start, end] that match the
    NL outline marker ``# # ...``."""
    out: list[int] = []
    for lineno in range(start, end + 1):
        if 1 <= lineno <= len(src_lines):
            if NL_OUTLINE_MARKER_RE.match(src_lines[lineno - 1]):
                out.append(lineno)
    return out


def lint_file(path: Path) -> list[Violation]:
    text = path.read_text(encoding="utf-8")
    src_lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [Violation(path, exc.lineno or 0, "<module>", "syntax-error", str(exc))]

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_lines = function_body_lines(node)
        if body_lines < LONG_FUNCTION_MIN_LINES:
            continue

        body_start = node.body[0].lineno
        body_end = node.body[-1].end_lineno or node.body[-1].lineno
        nl_lines = find_nl_outline_lines(src_lines, body_start, body_end)

        if not nl_lines:
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    node.name,
                    "missing-nl-outline",
                    f"function body is {body_lines} lines (≥ {LONG_FUNCTION_MIN_LINES}) "
                    f"but has no `# # ` outline comments",
                )
            )
            continue

        # Each NL statement should cover at least MIN_LINES_PER_NL_STATEMENT
        # lines of source — if two markers appear within < MIN apart, the
        # outline is too granular (decorative).
        boundaries = nl_lines + [body_end + 1]
        for i in range(len(boundaries) - 1):
            span = boundaries[i + 1] - boundaries[i]
            if span < MIN_LINES_PER_NL_STATEMENT:
                violations.append(
                    Violation(
                        path,
                        boundaries[i],
                        node.name,
                        "nl-outline-too-granular",
                        f"NL outline statement covers only {span} line(s); "
                        f"each must cover ≥ {MIN_LINES_PER_NL_STATEMENT}",
                    )
                )
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else DEFAULT_ROOT
    if not root.exists():
        print(f"check-nl-outline: {root} not found", file=sys.stderr)
        return 1
    files = sorted(root.rglob("*.py"))
    files = [f for f in files if "__pycache__" not in f.parts]
    violations: list[Violation] = []
    for f in files:
        violations.extend(lint_file(f))
    for v in violations:
        print(v.format())
    if violations:
        print(
            f"\n{len(violations)} NL-outline violation(s) across {len(files)} file(s)",
            file=sys.stderr,
        )
        return 1
    print(f"check-nl-outline: {len(files)} file(s) OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
