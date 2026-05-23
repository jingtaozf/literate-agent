"""LP sync engine — 3-pass roundtrip from source code to LP .org.

Per `rules/lp-resync-metadata.md` and `draft.org § 2026-05-22-lp-resync-
roundtrip` (v4), this module is the source-of-truth implementation of
the SHA-anchored, tree-sitter-bridged, metadata-driven sync.

Three passes per affected source file:

  Pass A — *modify*. Source def body changed; .org block owns the
           def via `:CONTAINS_DEFS:`. Engine replaces block body
           in-place; prose untouched.

  Pass B — *add*. Source has new def; no block owns it. Engine
           detects and reports; *does not auto-apply* in this S6
           version (insertion location heuristic deferred to S6-full
           — the per-language "where does this new def go" decision
           is genuinely hard and warrants human review).

  Pass C — *delete*. .org block owns a def that no longer exists in
           source. Engine tags the block with `:STALE:` (date +
           last-seen SHA). Never auto-removes.

Python is the only language extracted in this S5 version (uses
Python stdlib `ast` module — no tree-sitter binary needed).
TypeScript / Rust extractors land in S10.

Module structure:

  PythonDefExtractor — ast-based def extraction with FQN
  OrgFileParser — parse .org into headings/blocks/properties
  LpSyncEngine — 3-pass orchestrator
  main — CLI entry point

CLI:
  python3 scripts/lp_sync_engine.py <org-file> [--dry-run]
  python3 scripts/lp_sync_engine.py --all <lp-root> [--dry-run]
  python3 scripts/lp_sync_engine.py <org-file> --extract-defs <src.py>
       # debug: just show what defs are extracted

Exit code: 0 = synced cleanly (or no-op); 1 = errors / unresolved.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# Python def extractor (S5)
# ──────────────────────────────────────────────────────────────────

@dataclass
class DefInfo:
    fqn: str          # fully-qualified name (Foo.method_a, ClassName, etc.)
    kind: str         # 'function' | 'class' | 'method' | 'assignment' | 'annassign'
    body_text: str    # source text of the def (for replacement)
    body_hash: str    # sha256(body_text) for change detection
    start_line: int   # 1-based start line in source
    end_line: int


class PythonDefExtractor:
    """Extract top-level + class-method defs from Python source via ast.

    Returns {fqn → DefInfo}. Closures, nested functions, and statements
    inside if/try blocks are NOT extracted (they're not top-level).
    """

    def extract(self, source: str) -> dict[str, DefInfo]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}
        result: dict[str, DefInfo] = {}
        for node in ast.iter_child_nodes(tree):
            self._handle_top_node(node, source, result)
        return result

    def _handle_top_node(self, node: ast.AST, source: str,
                         result: dict[str, DefInfo]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._record_def(node, source, result, kind="function",
                             fqn_prefix=None)
        elif isinstance(node, ast.ClassDef):
            self._record_def(node, source, result, kind="class",
                             fqn_prefix=None)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._record_def(child, source, result, kind="method",
                                     fqn_prefix=node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    self._record_assign(node, tgt.id, source, result,
                                        kind="assignment")
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                self._record_assign(node, node.target.id, source, result,
                                    kind="annassign")

    def _record_def(self, node: ast.AST, source: str,
                    result: dict[str, DefInfo], kind: str,
                    fqn_prefix: str | None) -> None:
        name = getattr(node, "name", "<anon>")
        fqn = f"{fqn_prefix}.{name}" if fqn_prefix else name
        text = ast.get_source_segment(source, node, padded=True) or ""
        start = node.lineno
        end = getattr(node, "end_lineno", start) or start
        result[fqn] = DefInfo(fqn=fqn, kind=kind, body_text=text,
                              body_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
                              start_line=start, end_line=end)

    def _record_assign(self, node: ast.AST, name: str, source: str,
                       result: dict[str, DefInfo], kind: str) -> None:
        text = ast.get_source_segment(source, node, padded=True) or ""
        start = node.lineno
        end = getattr(node, "end_lineno", start) or start
        result[name] = DefInfo(fqn=name, kind=kind, body_text=text,
                               body_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
                               start_line=start, end_line=end)


# ──────────────────────────────────────────────────────────────────
# Tree-sitter-based extractors (TypeScript + Rust)
# ──────────────────────────────────────────────────────────────────
#
# Tree-sitter Python bindings load the language grammar as a native
# library at first use; we lazily import to keep cold-start fast and
# to avoid hard-failing if a language binding is missing.

class _TreeSitterExtractor:
    """Base class: AST walk via tree-sitter, dispatched on node-type
    via subclass-supplied label maps."""

    LANGUAGE_MODULE: str = ""   # e.g. "tree_sitter_typescript"
    LANGUAGE_ATTR: str = ""     # e.g. "language_typescript" or "language_tsx"
    DEFINITION_NODE_TYPES: dict[str, str] = {}
    # node.type → kind label

    # node-type → name-extraction strategy:
    #   "by-field:<field>"   — node.child_by_field_name(<field>).text
    #   "first-identifier"   — first descendant of type "identifier"
    #   "impl-rust"          — special Rust impl-block compound name
    NAME_STRATEGY: dict[str, str] = {}

    def __init__(self):
        self._parser = None  # lazy

    def _ensure_parser(self):
        if self._parser is not None:
            return
        try:
            import tree_sitter
            module = __import__(self.LANGUAGE_MODULE)
            language_callable = getattr(module, self.LANGUAGE_ATTR)
            lang = tree_sitter.Language(language_callable())
            self._parser = tree_sitter.Parser(lang)
        except Exception as exc:
            self._parser = exc  # sentinel: failed

    def extract(self, source: str) -> dict[str, DefInfo]:
        self._ensure_parser()
        if not isinstance(self._parser, object) or self._parser is None or isinstance(self._parser, Exception):
            return {}
        src_bytes = source.encode("utf-8")
        try:
            tree = self._parser.parse(src_bytes)
        except Exception:
            return {}
        result: dict[str, DefInfo] = {}
        for child in tree.root_node.children:
            self._handle_node(child, src_bytes, source, result)
        return result

    def _handle_node(self, node, src_bytes: bytes, source: str,
                     result: dict[str, DefInfo]) -> None:
        kind = self.DEFINITION_NODE_TYPES.get(node.type)
        if kind is None:
            # Unwrap export_statement / decorator wrappers
            unwrapped = self._unwrap(node)
            if unwrapped is None or unwrapped is node:
                return
            kind = self.DEFINITION_NODE_TYPES.get(unwrapped.type)
            if kind is None:
                return
            node = unwrapped
        name = self._extract_name(node, src_bytes)
        if not name:
            return
        body_text = src_bytes[node.start_byte:node.end_byte].decode(
            "utf-8", errors="replace")
        start = node.start_point[0] + 1
        end = node.end_point[0] + 1
        result[name] = DefInfo(
            fqn=name, kind=kind, body_text=body_text,
            body_hash=hashlib.sha256(body_text.encode()).hexdigest()[:16],
            start_line=start, end_line=end)

    def _unwrap(self, node):
        """Unwrap export-statement / similar wrappers around a real def."""
        # Subclass override if needed
        for child in node.children:
            if child.type in self.DEFINITION_NODE_TYPES:
                return child
        return None

    def _extract_name(self, node, src_bytes: bytes) -> str:
        strategy = self.NAME_STRATEGY.get(node.type, "by-field:name")
        if strategy.startswith("by-field:"):
            field = strategy.split(":", 1)[1]
            name_node = node.child_by_field_name(field)
            if name_node is None:
                return ""
            return src_bytes[name_node.start_byte:name_node.end_byte].decode(
                "utf-8", errors="replace")
        if strategy == "first-identifier":
            for c in node.children:
                if c.type in ("identifier", "type_identifier"):
                    return src_bytes[c.start_byte:c.end_byte].decode(
                        "utf-8", errors="replace")
            return ""
        if strategy == "impl-rust":
            return self._impl_name_rust(node, src_bytes)
        return ""

    def _impl_name_rust(self, node, src_bytes: bytes) -> str:
        # impl Trait for Type → "Trait_for_Type"; impl Type → "Type"
        trait_node = node.child_by_field_name("trait")
        type_node = node.child_by_field_name("type")
        trait = src_bytes[trait_node.start_byte:trait_node.end_byte].decode(
            "utf-8", errors="replace").strip() if trait_node else ""
        ty = src_bytes[type_node.start_byte:type_node.end_byte].decode(
            "utf-8", errors="replace").strip() if type_node else ""
        ty = re.sub(r"[<>,\s]+", "", ty)
        if trait:
            trait = re.sub(r"[<>,\s]+", "", trait)
            return f"{trait}_for_{ty}"
        return ty


class TypescriptDefExtractor(_TreeSitterExtractor):
    """Tree-sitter-based TS/TSX extractor (TypeScript grammar)."""

    LANGUAGE_MODULE = "tree_sitter_typescript"
    LANGUAGE_ATTR = "language_typescript"
    DEFINITION_NODE_TYPES = {
        "function_declaration":   "function",
        "class_declaration":      "class",
        "interface_declaration":  "interface",
        "enum_declaration":       "enum",
        "type_alias_declaration": "type",
        "lexical_declaration":    "variable",  # const/let
        "variable_declaration":   "variable",  # var
    }
    NAME_STRATEGY = {
        "function_declaration":   "by-field:name",
        "class_declaration":      "by-field:name",
        "interface_declaration":  "by-field:name",
        "enum_declaration":       "by-field:name",
        "type_alias_declaration": "by-field:name",
        # const/let/var: walk to first variable_declarator's name
        "lexical_declaration":    "first-declarator-name",
        "variable_declaration":   "first-declarator-name",
    }

    def _extract_name(self, node, src_bytes: bytes) -> str:
        strategy = self.NAME_STRATEGY.get(node.type)
        if strategy == "first-declarator-name":
            for c in node.children:
                if c.type == "variable_declarator":
                    nm = c.child_by_field_name("name")
                    if nm is None:
                        continue
                    # Skip destructuring patterns (object_pattern,
                    # array_pattern) — these aren't simple identifiers
                    # and produce noisy multi-name extractions.
                    if nm.type not in ("identifier", "type_identifier"):
                        return ""
                    return src_bytes[nm.start_byte:nm.end_byte].decode(
                        "utf-8", errors="replace")
            return ""
        return super()._extract_name(node, src_bytes)


class TsxDefExtractor(TypescriptDefExtractor):
    """TSX variant uses the same TS grammar but ts-tsx flavor."""
    LANGUAGE_ATTR = "language_tsx"


class RustDefExtractor(_TreeSitterExtractor):
    """Tree-sitter-based Rust extractor."""

    LANGUAGE_MODULE = "tree_sitter_rust"
    LANGUAGE_ATTR = "language"
    DEFINITION_NODE_TYPES = {
        "function_item":   "function",
        "struct_item":     "struct",
        "enum_item":       "enum",
        "trait_item":      "trait",
        "impl_item":       "impl",
        "const_item":      "const",
        "static_item":     "static",
        "type_item":       "type",
        "mod_item":        "mod",
        "union_item":      "union",
    }
    NAME_STRATEGY = {
        "function_item":   "by-field:name",
        "struct_item":     "by-field:name",
        "enum_item":       "by-field:name",
        "trait_item":      "by-field:name",
        "impl_item":       "impl-rust",
        "const_item":      "by-field:name",
        "static_item":     "by-field:name",
        "type_item":       "by-field:name",
        "mod_item":        "by-field:name",
        "union_item":      "by-field:name",
    }


# ──────────────────────────────────────────────────────────────────
# Language registry
# ──────────────────────────────────────────────────────────────────

LANGUAGE_EXTRACTORS = {
    "python":     PythonDefExtractor(),
    "py":         PythonDefExtractor(),
    "typescript": TypescriptDefExtractor(),
    "ts":         TypescriptDefExtractor(),
    "tsx":        TsxDefExtractor(),
    "rust":       RustDefExtractor(),
    "rs":         RustDefExtractor(),
}


def get_extractor(lang: str) -> object | None:
    return LANGUAGE_EXTRACTORS.get(lang.lower())


# ──────────────────────────────────────────────────────────────────
# Org file parser
# ──────────────────────────────────────────────────────────────────

HEADING_RE = re.compile(r"^(\*+)\s+(.+?)\s*(?::[\w@:]+:)?$")
PROP_FILE_RE = re.compile(r"^#\+PROPERTY:\s+(\S+)\s+(.*)$")
PROP_DRAWER_RE = re.compile(r"^\s*:([A-Z_][A-Z_0-9]*):\s*(.*?)\s*$")
TANGLE_RE = re.compile(r":tangle\s+([^\s]+)")
NOWEB_REF_RE = re.compile(r":noweb-ref\s+(\S+)")
NOWEB_YES_RE = re.compile(r":noweb\s+yes\b")
NOWEB_CHUNK_RE = re.compile(r"<<([^<>\n]+)>>")
SRC_BEGIN_RE = re.compile(r"^\s*#\+begin_src\b", re.IGNORECASE)
SRC_END_RE = re.compile(r"^\s*#\+end_src\b", re.IGNORECASE)


@dataclass
class OrgBlock:
    heading_line: int       # 1-based line number of the heading
    heading_text: str
    depth: int
    drawer_props: dict[str, str] = field(default_factory=dict)
    # Two separate header-args sources, distinguished for inheritance:
    # - drawer_header_args: from :PROPERTIES: drawer's :header-args: line.
    #   This is INHERITED by descendants (org-mode native behavior).
    # - block_header_args: from this block's own #+begin_src line.
    #   This is the block's OWN args (NOT inherited).
    drawer_header_args: str = ""
    block_header_args: str = ""
    # Legacy field kept for backward compat (no consumers depend on it
    # anymore, but tests might).
    header_args_text: str = ""
    src_begin_line: int = 0
    src_end_line: int = 0
    src_lang: str = ""
    tangle_path: str | None = None
    noweb_ref: str | None = None
    block_kind: str | None = None
    noweb_parent: str | None = None
    contains_defs: list[str] = field(default_factory=list)
    custom_id: str | None = None
    chunk_refs_in_body: list[str] = field(default_factory=list)


@dataclass
class OrgFile:
    path: Path
    raw_lines: list[str] = field(default_factory=list)
    file_props: dict[str, str] = field(default_factory=dict)
    blocks: list[OrgBlock] = field(default_factory=list)

    @property
    def source_sha(self) -> str | None:
        return self.file_props.get("LITERATE_ORG_SOURCE_SHA")

    def find_block_owning_def(self, fqn: str) -> OrgBlock | None:
        for b in self.blocks:
            if fqn in b.contains_defs:
                return b
        return None

    def custom_id_index(self) -> dict[str, OrgBlock]:
        return {b.custom_id: b for b in self.blocks if b.custom_id}


class OrgFileParser:
    """Parse a .org file into structured OrgFile with blocks."""

    def parse(self, path: Path) -> OrgFile:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=False)
        org = OrgFile(path=path, raw_lines=lines)

        # File-level properties
        for line in lines:
            if line.startswith("#+PROPERTY:"):
                m = PROP_FILE_RE.match(line)
                if m:
                    org.file_props[m.group(1)] = m.group(2).strip()
            elif not line.startswith("#") and line.strip():
                break  # past header

        # Walk for headings + drawer + src
        current_block: OrgBlock | None = None
        in_drawer = False
        in_src = False
        for idx, line in enumerate(lines):
            line_no = idx + 1

            # Heading
            m = HEADING_RE.match(line)
            if m and not in_src:
                # Include EVERY heading in org.blocks — even drawer-only
                # ones (no #+begin_src). Inheritance walk relies on the
                # full hierarchy to propagate :header-args from ancestor
                # to descendant. Consumers that only care about src-bearing
                # blocks can filter with `b.src_lang`.
                if current_block is not None:
                    org.blocks.append(current_block)
                depth = len(m.group(1))
                current_block = OrgBlock(
                    heading_line=line_no, heading_text=m.group(2).strip(),
                    depth=depth)
                in_drawer = False
                continue

            # Properties drawer
            if line.strip() == ":PROPERTIES:":
                in_drawer = True
                continue
            if line.strip() == ":END:":
                in_drawer = False
                continue
            if in_drawer and current_block is not None:
                pm = PROP_DRAWER_RE.match(line)
                if pm:
                    key = pm.group(1)
                    value = pm.group(2).strip()
                    current_block.drawer_props[key] = value
                    if key == "CUSTOM_ID":
                        current_block.custom_id = value
                    elif key == "LITERATE_ORG_BLOCK_KIND":
                        current_block.block_kind = value
                    elif key == "LITERATE_ORG_NOWEB_PARENT":
                        current_block.noweb_parent = value
                    elif key == "LITERATE_ORG_CONTAINS_DEFS":
                        current_block.contains_defs = value.split()
                # :header-args:* inside drawer → inheritance source
                if line.strip().lower().startswith(":header-args"):
                    current_block.drawer_header_args += " " + line.strip()
                    current_block.header_args_text += " " + line.strip()
                continue

            # Src block boundaries
            if SRC_BEGIN_RE.match(line):
                in_src = True
                if current_block is not None:
                    current_block.src_begin_line = line_no
                    parts = line.strip().split(None, 1)
                    if len(parts) >= 1:
                        rest = parts[0]  # "#+begin_src"
                        full = line.strip()[len(rest):].strip()
                        if full:
                            lang_match = re.match(r"^(\S+)", full)
                            if lang_match:
                                current_block.src_lang = lang_match.group(1)
                        current_block.block_header_args = line.strip()
                        current_block.header_args_text += " " + line.strip()
                    # tangle path — prefer block-own > drawer-inherited
                    tm = TANGLE_RE.search(current_block.block_header_args)
                    if tm and tm.group(1) != "no":
                        current_block.tangle_path = tm.group(1)
                    else:
                        tm = TANGLE_RE.search(current_block.drawer_header_args)
                        if tm and tm.group(1) != "no":
                            current_block.tangle_path = tm.group(1)
                    # noweb-ref — block-own first; :noweb-ref "" = opt-out
                    nm = NOWEB_REF_RE.search(current_block.block_header_args)
                    if nm:
                        if nm.group(1) != '""':
                            current_block.noweb_ref = nm.group(1)
                        # else: opt-out — leave noweb_ref None even if
                        # drawer-inherited would set it. The inheritance
                        # post-pass respects this.
                    elif (NOWEB_REF_RE.search(current_block.drawer_header_args)
                          and '""' not in current_block.block_header_args):
                        # No own :noweb-ref and no opt-out → inherit
                        m2 = NOWEB_REF_RE.search(current_block.drawer_header_args)
                        if m2 and m2.group(1) != '""':
                            current_block.noweb_ref = m2.group(1)
                continue
            if SRC_END_RE.match(line):
                in_src = False
                if current_block is not None:
                    current_block.src_end_line = line_no
                continue
            # Scan src-block body for <<chunk>> placeholders
            if in_src and current_block is not None:
                for cm in NOWEB_CHUNK_RE.finditer(line):
                    current_block.chunk_refs_in_body.append(cm.group(1))

        if current_block is not None:
            org.blocks.append(current_block)

        # Post-pass: propagate inherited :noweb-ref and :tangle path from
        # nearest ancestor heading whose drawer's :header-args declares
        # them. Org-mode applies this inheritance natively at tangle
        # time; the parser must mirror it for consumers (V3 noweb
        # integrity, sync engine block-owner lookup).
        self._propagate_header_args_inheritance(org)

        return org

    def _propagate_header_args_inheritance(self, org: 'OrgFile') -> None:
        """Propagate :header-args declared in ancestor headings' drawers
        to descendant blocks where the descendant didn't already have its
        own value. Mirrors org-mode's native header-args inheritance.

        Order:
          1. Block's own :noweb-ref (from #+begin_src line) — already
             set during parse; treated as authoritative.
          2. Block's own :noweb-ref "" — opt-out; do NOT inherit.
          3. Otherwise: inherit from nearest ancestor's :header-args
             drawer line.
        """
        # ancestor stack of (depth, drawer_header_args)
        ancestor_args: list[tuple[int, str]] = []
        for block in org.blocks:
            depth = block.depth
            while ancestor_args and ancestor_args[-1][0] >= depth:
                ancestor_args.pop()
            inherited_text = ancestor_args[-1][1] if ancestor_args else ""

            # noweb_ref inheritance: only if block lacks own AND didn't opt out
            if not block.noweb_ref and '""' not in block.block_header_args and inherited_text:
                m = NOWEB_REF_RE.search(inherited_text)
                if m and m.group(1) != '""':
                    block.noweb_ref = m.group(1)

            # tangle_path inheritance: only if block lacks own
            if not block.tangle_path and inherited_text:
                m = TANGLE_RE.search(inherited_text)
                if m and m.group(1) != "no":
                    block.tangle_path = m.group(1)

            # Push own drawer header-args onto ancestor stack
            if block.drawer_header_args:
                ancestor_args.append((depth, block.drawer_header_args))


# ──────────────────────────────────────────────────────────────────
# Block-content def extraction (parse a src block's body for defs)
# ──────────────────────────────────────────────────────────────────

class BlockDefExtractor:
    """Extract defs from an org src block's content via language-specific
    extractor. Languages without a registered extractor return [].
    """

    def extract_block_defs(self, org: OrgFile, block: OrgBlock) -> list[str]:
        extractor = get_extractor(block.src_lang or "")
        if extractor is None:
            return []
        body = self._extract_body(org, block)
        defs = extractor.extract(body)
        return sorted(defs.keys())

    def _extract_body(self, org: OrgFile, block: OrgBlock) -> str:
        """Get raw source text between #+begin_src and #+end_src."""
        if not block.src_begin_line or not block.src_end_line:
            return ""
        start = block.src_begin_line  # 0-indexed = src_begin_line (after begin_src line)
        end = block.src_end_line - 1  # 0-indexed = src_end_line - 1 (before end_src line)
        return "\n".join(org.raw_lines[start:end])


# ──────────────────────────────────────────────────────────────────
# Sync engine (S6)
# ──────────────────────────────────────────────────────────────────

class LpSyncEngine:
    """3-pass sync from source repo to .org file."""

    def __init__(self):
        self.parser = OrgFileParser()
        self.extractor = BlockDefExtractor()
        self.python = PythonDefExtractor()

    def sync_file(self, org_path: Path, source_repo: Path | None = None,
                  dry_run: bool = True) -> dict:
        """Sync one .org file. Returns summary dict."""
        org = self.parser.parse(org_path)
        old_sha = org.source_sha
        if not old_sha:
            return {"status": "skip-no-sha", "reason":
                    "missing LITERATE_ORG_SOURCE_SHA — run bootstrap first"}

        if source_repo is None:
            source_repo = self._resolve_source_repo(org)
        if source_repo is None:
            return {"status": "skip-no-source", "reason":
                    "could not resolve source repo from .org's :tangle paths"}

        new_sha = self._git_head(source_repo)
        if new_sha is None:
            return {"status": "skip-no-source", "reason":
                    f"git HEAD lookup failed in {source_repo}"}
        if new_sha == old_sha:
            return {"status": "no-op", "reason": "source SHA unchanged"}

        # Find affected source files
        affected = self._affected_files(source_repo, old_sha, new_sha,
                                        self._tangle_targets(org, source_repo))
        if not affected:
            # SHA bump only
            if not dry_run:
                self._update_sha(org_path, new_sha)
            return {"status": "bump-sha-only", "old_sha": old_sha[:12],
                    "new_sha": new_sha[:12]}

        # Per affected file: extract old + new defs; classify
        changes = []
        for rel in affected:
            old_text = self._git_show(source_repo, old_sha, rel)
            new_text = self._git_show(source_repo, new_sha, rel)
            if old_text is None:
                old_defs: dict[str, DefInfo] = {}
            else:
                old_defs = self.python.extract(old_text)
            if new_text is None:
                new_defs = {}
            else:
                new_defs = self.python.extract(new_text)
            classified = self._classify(old_defs, new_defs)
            changes.append({
                "file": rel,
                "modified": [d for d in classified["modified"]],
                "added": [d for d in classified["added"]],
                "removed": [d for d in classified["removed"]],
                "new_defs": new_defs,  # for Pass A body replacement
            })

        # Map source files to .org blocks (block.tangle_path → relative path
        # under source_repo). Block owns a def iff CONTAINS_DEFS lists it.
        passes = self._apply_passes(org, changes, source_repo, new_sha,
                                    dry_run=dry_run)
        passes["old_sha"] = old_sha[:12]
        passes["new_sha"] = new_sha[:12]
        passes["status"] = "synced"
        return passes

    # ── helpers ────────────────────────────────────────────────

    def _resolve_source_repo(self, org: OrgFile) -> Path | None:
        for b in org.blocks:
            if b.tangle_path and b.tangle_path != "no":
                target = (org.path.parent / b.tangle_path).resolve()
                cur = target.parent
                for _ in range(20):
                    if (cur / ".git").exists():
                        return cur
                    if cur.parent == cur:
                        return None
                    cur = cur.parent
        return None

    def _git_head(self, repo: Path) -> str | None:
        try:
            r = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5, check=True)
            return r.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return None

    def _tangle_targets(self, org: OrgFile, source_repo: Path) -> list[str]:
        """Return tangle targets relative to source_repo."""
        out: list[str] = []
        for b in org.blocks:
            if b.tangle_path and b.tangle_path != "no":
                abs_p = (org.path.parent / b.tangle_path).resolve()
                try:
                    rel = abs_p.relative_to(source_repo)
                    out.append(str(rel))
                except ValueError:
                    pass
        return list(set(out))

    def _affected_files(self, source_repo: Path, old_sha: str, new_sha: str,
                        paths: list[str]) -> list[str]:
        try:
            r = subprocess.run(
                ["git", "-C", str(source_repo), "diff", "--name-only",
                 f"{old_sha}..{new_sha}", "--"] + paths,
                capture_output=True, text=True, timeout=10, check=True)
            return [line for line in r.stdout.splitlines() if line.strip()]
        except (subprocess.SubprocessError, OSError):
            return []

    def _git_show(self, repo: Path, sha: str, rel: str) -> str | None:
        try:
            r = subprocess.run(
                ["git", "-C", str(repo), "show", f"{sha}:{rel}"],
                capture_output=True, text=True, timeout=10, check=False)
            if r.returncode != 0:
                return None
            return r.stdout
        except (subprocess.SubprocessError, OSError):
            return None

    def _classify(self, old_defs: dict[str, DefInfo],
                  new_defs: dict[str, DefInfo]) -> dict:
        modified: list[DefInfo] = []
        added: list[DefInfo] = []
        removed: list[DefInfo] = []
        for fqn, new_info in new_defs.items():
            if fqn in old_defs:
                if old_defs[fqn].body_hash != new_info.body_hash:
                    modified.append(new_info)
            else:
                added.append(new_info)
        for fqn, old_info in old_defs.items():
            if fqn not in new_defs:
                removed.append(old_info)
        return {"modified": modified, "added": added, "removed": removed}

    def _apply_passes(self, org: OrgFile, changes: list[dict],
                      source_repo: Path, new_sha: str,
                      dry_run: bool) -> dict:
        """Apply 3-pass. Returns counts + actions."""
        pass_a: list[dict] = []
        pass_b: list[dict] = []
        pass_c: list[dict] = []

        # Pass A: modify
        new_lines = list(org.raw_lines)
        line_shift = 0  # tracks insertion/replacement line count delta

        # Collect Pass A operations sorted by line (apply bottom-up to
        # keep line indices stable)
        operations: list[tuple[int, int, list[str], str]] = []
        # (src_begin_idx, src_end_idx, replacement_lines, log_msg)

        for change in changes:
            for mod_def in change["modified"]:
                block = org.find_block_owning_def(mod_def.fqn)
                if block is None:
                    pass_b.append({"file": change["file"], "fqn": mod_def.fqn,
                                   "reason": "modified-but-no-owner-block — "
                                             "rare; check CONTAINS_DEFS"})
                    continue
                if block.drawer_props.get("LITERATE_ORG_PIN") == "yes":
                    pass_a.append({"file": change["file"], "fqn": mod_def.fqn,
                                   "action": "SKIP-pinned",
                                   "block_line": block.heading_line})
                    continue
                # Compute body bounds in org file
                body_start_0 = block.src_begin_line  # 0-indexed start of body (after #+begin_src line)
                body_end_0 = block.src_end_line - 1  # 0-indexed line of #+end_src

                # If block owns multiple defs (atomic with several functions),
                # do targeted def replacement: find this specific def's line
                # range within the block's body, replace just that.
                # If block owns exactly one def, replace whole body.
                if len(block.contains_defs) <= 1:
                    replacement = mod_def.body_text.rstrip("\n").splitlines()
                    operations.append((body_start_0, body_end_0, replacement,
                                       f"Pass A modify {mod_def.fqn} (full-body)"))
                    pass_a.append({"file": change["file"], "fqn": mod_def.fqn,
                                   "action": "modify-full-body",
                                   "block_line": block.heading_line,
                                   "block_kind": block.block_kind})
                else:
                    # Parse block body to find def's relative line range
                    body_text = "\n".join(org.raw_lines[body_start_0:body_end_0])
                    block_defs = self.python.extract(body_text)
                    if mod_def.fqn not in block_defs:
                        pass_a.append({"file": change["file"],
                                       "fqn": mod_def.fqn,
                                       "action": "SKIP-not-found-in-block",
                                       "block_line": block.heading_line,
                                       "reason": "def listed in CONTAINS_DEFS "
                                                 "but tree-sitter parse of "
                                                 "block body did not find it; "
                                                 "metadata may be stale — "
                                                 "run --refresh-defs"})
                        continue
                    block_def_info = block_defs[mod_def.fqn]
                    # block_def_info.start_line / end_line are 1-based within body_text
                    def_start_in_block = block_def_info.start_line  # 1-based
                    def_end_in_block = block_def_info.end_line  # 1-based, inclusive
                    # Convert to org-file 0-indexed
                    abs_start = body_start_0 + (def_start_in_block - 1)
                    abs_end = body_start_0 + def_end_in_block  # exclusive end
                    replacement = mod_def.body_text.rstrip("\n").splitlines()
                    operations.append((abs_start, abs_end, replacement,
                                       f"Pass A modify {mod_def.fqn} (targeted)"))
                    pass_a.append({"file": change["file"], "fqn": mod_def.fqn,
                                   "action": "modify-targeted",
                                   "block_line": block.heading_line,
                                   "block_kind": block.block_kind,
                                   "def_range": [abs_start + 1, abs_end]})

            for add_def in change["added"]:
                # Pass B: report only in this S6 version
                pass_b.append({"file": change["file"], "fqn": add_def.fqn,
                               "kind": add_def.kind,
                               "action": "DEFER-add (insertion location "
                                         "requires human triage)"})

            for rem_def in change["removed"]:
                block = org.find_block_owning_def(rem_def.fqn)
                if block is None:
                    continue
                # Pass C: add :STALE: property
                stale_value = (f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
                               f" last-seen-at "
                               f"{changes[0].get('old_sha', '????')[:12] if changes else '????'}")
                pass_c.append({"file": change["file"], "fqn": rem_def.fqn,
                               "action": "tag-stale",
                               "block_line": block.heading_line,
                               "stale": stale_value})

        # Apply Pass A operations bottom-up
        operations.sort(key=lambda op: -op[0])
        for body_start_0, body_end_0, replacement, _ in operations:
            new_lines[body_start_0:body_end_0] = replacement

        # Apply Pass C: insert :STALE: into property drawer of each affected block
        # (also bottom-up so heading line indices stay valid)
        pass_c.sort(key=lambda p: -p["block_line"])
        for stale_op in pass_c:
            heading_idx = stale_op["block_line"] - 1
            # find :PROPERTIES: or insert after heading
            insert_idx = heading_idx + 1
            # skip blank
            while insert_idx < len(new_lines) and new_lines[insert_idx].strip() == "":
                insert_idx += 1
            if (insert_idx < len(new_lines) and
                new_lines[insert_idx].strip() == ":PROPERTIES:"):
                new_lines.insert(insert_idx + 1,
                                 f":STALE: {stale_op['stale']}")
            else:
                new_lines.insert(heading_idx + 1, ":PROPERTIES:")
                new_lines.insert(heading_idx + 2,
                                 f":STALE: {stale_op['stale']}")
                new_lines.insert(heading_idx + 3, ":END:")

        # Update SOURCE_SHA + SOURCE_SHA_DATE in file header
        new_sha_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i, line in enumerate(new_lines):
            if line.startswith("#+PROPERTY: LITERATE_ORG_SOURCE_SHA "):
                new_lines[i] = f"#+PROPERTY: LITERATE_ORG_SOURCE_SHA {new_sha}"
            elif line.startswith("#+PROPERTY: LITERATE_ORG_SOURCE_SHA_DATE "):
                new_lines[i] = (f"#+PROPERTY: LITERATE_ORG_SOURCE_SHA_DATE "
                                f"{new_sha_date}")

        if not dry_run and (operations or pass_c):
            org.path.write_text("\n".join(new_lines) + "\n",
                                encoding="utf-8")

        return {"pass_a": pass_a, "pass_b": pass_b, "pass_c": pass_c,
                "dry_run": dry_run}

    def _update_sha(self, org_path: Path, new_sha: str) -> None:
        text = org_path.read_text(encoding="utf-8")
        new_sha_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        text = re.sub(
            r"^#\+PROPERTY: LITERATE_ORG_SOURCE_SHA \S+",
            f"#+PROPERTY: LITERATE_ORG_SOURCE_SHA {new_sha}",
            text, count=1, flags=re.MULTILINE)
        text = re.sub(
            r"^#\+PROPERTY: LITERATE_ORG_SOURCE_SHA_DATE \S+",
            f"#+PROPERTY: LITERATE_ORG_SOURCE_SHA_DATE {new_sha_date}",
            text, count=1, flags=re.MULTILINE)
        org_path.write_text(text, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help=".org file or directory")
    parser.add_argument("--all", action="store_true",
                        help="recursively process all .org files")
    parser.add_argument("--dry-run", "-n", action="store_true", default=False,
                        help="show what would change without writing files")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--extract-defs", type=Path, default=None,
                        help="debug: extract defs from a .py file and exit")
    parser.add_argument("--refresh-defs", action="store_true",
                        help="recompute :LITERATE_ORG_CONTAINS_DEFS: from block "
                             "content via tree-sitter (no sync, no SHA change)")
    args = parser.parse_args()

    if args.refresh_defs:
        return _refresh_defs_main(args)

    if args.extract_defs:
        src = args.extract_defs.read_text(encoding="utf-8", errors="replace")
        ext_to_lang = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".rs": "rust",
        }
        lang = ext_to_lang.get(args.extract_defs.suffix.lower(), "python")
        extractor = get_extractor(lang)
        if extractor is None:
            print(f"No extractor for language {lang!r} (ext {args.extract_defs.suffix})")
            return 1
        defs = extractor.extract(src)
        print(f"Extracted {len(defs)} defs from {args.extract_defs} (lang={lang}):")
        for fqn in sorted(defs):
            d = defs[fqn]
            print(f"  {d.kind:11s} {fqn} (lines {d.start_line}-{d.end_line}, hash {d.body_hash})")
        return 0

    engine = LpSyncEngine()
    if args.all:
        if not args.target.is_dir():
            print(f"error: --all requires directory: {args.target}",
                  file=sys.stderr)
            return 2
        files = sorted(args.target.rglob("*.org"))
    else:
        if not args.target.is_file():
            print(f"error: not a file: {args.target}", file=sys.stderr)
            return 2
        files = [args.target]

    summary: dict[str, int] = {}
    for f in files:
        result = engine.sync_file(f, dry_run=args.dry_run)
        status = result.get("status", "unknown")
        summary[status] = summary.get(status, 0) + 1
        if args.verbose or status == "synced":
            print(f"\n{f}")
            for k, v in result.items():
                if isinstance(v, list):
                    print(f"  {k}: {len(v)} entries")
                    for item in v[:5]:
                        print(f"    - {item}")
                    if len(v) > 5:
                        print(f"    ... and {len(v) - 5} more")
                else:
                    print(f"  {k}: {v}")

    print(f"\nSummary ({len(files)} files):")
    for s, c in sorted(summary.items()):
        print(f"  {s}: {c}")
    return 0


def _slugify(text: str) -> str:
    """Kebab-case slug for use as :CUSTOM_ID:. Mirrors backfill_anchors.py."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    if len(s) > 60:
        s = s[:60].rstrip("-")
    return s


def _refresh_noweb_parents(org: 'OrgFile', new_lines: list[str]) -> tuple[list[str], int]:
    """Auto-infer :LITERATE_ORG_NOWEB_PARENT: for noweb-leaf blocks.

    Strategy:
      1. Build chunk-index: each skeleton block's chunk_refs_in_body
         (the <<chunk>> names referenced by skeleton's body) maps to
         the skeleton block.
      2. For each noweb-leaf with :noweb-ref X, find the skeleton
         whose body references <<X>>. Set :LITERATE_ORG_NOWEB_PARENT:
         to skeleton's :CUSTOM_ID: (generating one from heading text
         if absent).

    Returns (updated_lines, count_set). Edits skeleton blocks too if
    they need a new :CUSTOM_ID: anchor.
    """
    # Build chunk → skeleton anchor map
    chunk_to_skeleton: dict[str, 'OrgBlock'] = {}
    for b in org.blocks:
        if b.block_kind == "skeleton":
            for chunk_name in b.chunk_refs_in_body:
                chunk_to_skeleton.setdefault(chunk_name, b)

    set_count = 0
    # Plan edits bottom-up to keep line indices stable
    skeleton_anchor_inserts: list[tuple[int, str]] = []
    leaf_parent_inserts: list[tuple[int, str, OrgBlock]] = []

    for leaf in org.blocks:
        if leaf.block_kind != "noweb-leaf":
            continue
        if leaf.noweb_parent:
            continue  # already set
        chunk = leaf.noweb_ref
        if not chunk:
            continue
        skeleton = chunk_to_skeleton.get(chunk)
        if skeleton is None:
            continue
        # Ensure skeleton has a :CUSTOM_ID:
        if not skeleton.custom_id:
            skeleton.custom_id = _slugify(skeleton.heading_text)
            skeleton_anchor_inserts.append((skeleton.heading_line, skeleton.custom_id))
        leaf.noweb_parent = skeleton.custom_id
        leaf_parent_inserts.append((leaf.heading_line,
                                    skeleton.custom_id, leaf))
        set_count += 1

    # Sort bottom-up
    all_inserts = (
        [("anchor", hl, slug, None) for hl, slug in skeleton_anchor_inserts]
        + [("parent", hl, slug, leaf) for hl, slug, leaf in leaf_parent_inserts]
    )
    all_inserts.sort(key=lambda t: -t[1])

    for kind_op, heading_line, slug, _leaf in all_inserts:
        heading_idx = heading_line - 1
        # Find or create PROPERTIES drawer
        scan = heading_idx + 1
        while scan < len(new_lines) and new_lines[scan].strip() == "":
            scan += 1
        if (scan < len(new_lines) and
            new_lines[scan].strip() == ":PROPERTIES:"):
            # Find existing key
            end = scan + 1
            existing_idx = -1
            target_key = (":CUSTOM_ID:" if kind_op == "anchor"
                          else ":LITERATE_ORG_NOWEB_PARENT:")
            while end < len(new_lines) and new_lines[end].strip() != ":END:":
                if new_lines[end].strip().startswith(target_key):
                    existing_idx = end
                end += 1
            line_value = (f":CUSTOM_ID: {slug}" if kind_op == "anchor"
                          else f":LITERATE_ORG_NOWEB_PARENT: {slug}")
            if existing_idx >= 0:
                new_lines[existing_idx] = line_value
            else:
                new_lines.insert(scan + 1, line_value)
        else:
            line_value = (f":CUSTOM_ID: {slug}" if kind_op == "anchor"
                          else f":LITERATE_ORG_NOWEB_PARENT: {slug}")
            new_lines.insert(heading_idx + 1, ":PROPERTIES:")
            new_lines.insert(heading_idx + 2, line_value)
            new_lines.insert(heading_idx + 3, ":END:")

    return new_lines, set_count


def _refresh_defs_main(args) -> int:
    """Re-compute :LITERATE_ORG_CONTAINS_DEFS: on every tangle-bearing
    block of the target .org files via tree-sitter parse of block content.

    Also auto-infers :LITERATE_ORG_NOWEB_PARENT: for noweb-leaf blocks
    by matching :noweb-ref name against skeleton blocks' <<chunk>>
    placeholders. Stamps :CUSTOM_ID: on skeleton blocks that lack one.
    """
    extractor = BlockDefExtractor()
    org_parser = OrgFileParser()

    if args.all:
        if not args.target.is_dir():
            print(f"error: --all requires directory: {args.target}",
                  file=sys.stderr)
            return 2
        files = sorted(args.target.rglob("*.org"))
    else:
        if not args.target.is_file():
            print(f"error: not a file: {args.target}", file=sys.stderr)
            return 2
        files = [args.target]

    total_blocks_updated = 0
    total_files_updated = 0
    for f in files:
        org = org_parser.parse(f)
        if not org.blocks:
            continue
        # Build noweb-ref index: noweb_ref name → list of leaf blocks
        by_noweb_ref: dict[str, list[OrgBlock]] = {}
        for b in org.blocks:
            if b.noweb_ref:
                by_noweb_ref.setdefault(b.noweb_ref, []).append(b)

        updates: list[tuple[OrgBlock, list[str]]] = []
        for block in org.blocks:
            if block.block_kind == "prose-only":
                continue
            if not (block.tangle_path or block.noweb_ref):
                continue
            # Get effective body: for skeleton, expand <<chunks>>
            body = "\n".join(
                org.raw_lines[block.src_begin_line:block.src_end_line - 1])
            if block.block_kind == "skeleton":
                for chunk_name in block.chunk_refs_in_body:
                    leaves = by_noweb_ref.get(chunk_name, [])
                    for leaf in leaves:
                        leaf_body = "\n".join(
                            org.raw_lines[leaf.src_begin_line:leaf.src_end_line - 1])
                        body += "\n" + leaf_body
            # Parse defs via language registry
            extractor = get_extractor(block.src_lang or "")
            if extractor is not None:
                defs = sorted(extractor.extract(body).keys())
            else:
                defs = []
            if defs and defs != block.contains_defs:
                updates.append((block, defs))

        # Determine if NOWEB_PARENT inference has work to do
        leaves_needing_parent = [b for b in org.blocks
                                 if b.block_kind == "noweb-leaf"
                                 and not b.noweb_parent
                                 and b.noweb_ref]
        if not updates and not leaves_needing_parent:
            continue
        if not args.dry_run:
            # Apply updates: insert/update :LITERATE_ORG_CONTAINS_DEFS:
            new_lines = list(org.raw_lines)
            updates.sort(key=lambda u: -u[0].heading_line)  # bottom-up
            for block, defs in updates:
                defs_value = " ".join(sorted(defs))
                line_value = f":LITERATE_ORG_CONTAINS_DEFS: {defs_value}"
                heading_idx = block.heading_line - 1
                # find existing PROPERTIES drawer
                scan = heading_idx + 1
                while scan < len(new_lines) and new_lines[scan].strip() == "":
                    scan += 1
                if (scan < len(new_lines) and
                    new_lines[scan].strip() == ":PROPERTIES:"):
                    # find existing CONTAINS_DEFS in drawer
                    end = scan + 1
                    contains_idx = -1
                    while end < len(new_lines) and new_lines[end].strip() != ":END:":
                        if "LITERATE_ORG_CONTAINS_DEFS" in new_lines[end]:
                            contains_idx = end
                        end += 1
                    if contains_idx >= 0:
                        new_lines[contains_idx] = line_value
                    else:
                        new_lines.insert(scan + 1, line_value)
                else:
                    # no drawer — create one
                    new_lines.insert(heading_idx + 1, ":PROPERTIES:")
                    new_lines.insert(heading_idx + 2, line_value)
                    new_lines.insert(heading_idx + 3, ":END:")
            # Pass 2: NOWEB_PARENT inference (uses fresh org parse to keep
            # block line indices stable after CONTAINS_DEFS edits)
            f.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            re_org = org_parser.parse(f)
            re_lines = list(re_org.raw_lines)
            re_lines, parent_set = _refresh_noweb_parents(re_org, re_lines)
            if parent_set:
                f.write_text("\n".join(re_lines) + "\n", encoding="utf-8")
            total_files_updated += 1
            total_blocks_updated += len(updates) + parent_set
        else:
            total_files_updated += 1
            total_blocks_updated += (len(updates) + len(leaves_needing_parent))
        if args.verbose:
            rel = f.relative_to(args.target) if args.all else f
            print(f"  {rel}: {len(updates)} blocks updated")

    print(f"\nRefresh CONTAINS_DEFS:")
    print(f"  Files: {total_files_updated}")
    print(f"  Blocks updated: {total_blocks_updated}")
    if args.dry_run:
        print("(DRY RUN)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
