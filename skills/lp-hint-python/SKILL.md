---
description: Python-specific literate-programming traps — tangle path resolution, ruff formatter file-local-var, noweb refs for big classes, byte-equivalence gate, bare-* parser trap. Auto-activates when editing .py files or literate .org files with Python src blocks. Consult before renaming .org files (tangle paths break), before adding new tangle targets, or after editing a literate-python .org.
when_to_use: editing .py files; editing .org files containing #+BEGIN_SRC python blocks; user mentions tangle, ruff formatter, noweb, byte-equivalence, or "edited the wrong .py".
disable-model-invocation: false
allowed-tools: Read Edit Write Grep
paths: "**/*.py"
---

# lp-hint-python — Python LP traps and conventions

Points at the canonical Python LP hint file:

    ~/projects/literate-agent/hints/python.org

## Top traps (read the file for context + workarounds)

1. **NEVER edit the tangled `.py` directly** — it's a generated
   artefact. Edit the owning `.org` section. The PreToolUse hook
   `block-tangled-edit.sh` enforces this and points at the owning
   `.org` via `.cache/tangle-map.tsv`.
2. **Required file-local-vars line** for poly-org users:
   `# -*- Mode: POLY-ORG; indent-tabs-mode: nil; literate-org-py-formatter: ruff; -*- ---`
   Without it, tangle output drifts vs. canonical formatter format.
3. **`:tangle` path resolves relative to the `.org` file's
   directory**, NOT the project root. A `git mv` of the `.org`
   silently breaks tangling.
4. **Comma-escape `* ` at column 0** inside `#+BEGIN_SRC python`
   blocks — even inside docstrings. Org parses bare `*` as a
   headline and silently terminates the src block.
5. **Use `:noweb yes` to split big classes** — see
   `rules/lp-noweb-for-big-blocks.md` for the canonical pattern.
6. **Byte-equivalence gate**: after `make tangle`,
   `git diff --stat python/` MUST be empty (or match your intent).
   Non-empty for untouched modules = drift; investigate.

## When this skill activates

- Editing any `.py` file (via the `paths: "**/*.py"` matcher) —
  including blocked tangle outputs, where the hint reinforces "go
  edit the .org instead."
- Reading or editing a literate `.org` file when Claude infers it
  contains Python src blocks.

## Procedure

1. Read `~/projects/literate-agent/hints/python.org` end-to-end on
   first activation in a session.
2. Apply the relevant workaround.
3. For tangle-related actions, also consult
   `docs/tangle-map-schema.org` for the reverse-lookup mechanism.

## See also

- `~/projects/literate-agent/rules/python-literate-programming.md`
- `~/projects/literate-agent/rules/lp-noweb-for-big-blocks.md`
- `~/projects/literate-agent/rules/lp-comma-escape-leading-star.md`
- `~/projects/literate-agent/docs/tangle-map-schema.org`
