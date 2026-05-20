---
description: Elisp-specific literate-programming caveats — lexical-binding handling, macro re-expansion, reload discipline. Auto-activates when editing .el files or literate .org files with Elisp src blocks. Consult before adding lambdas in callbacks/timers, before changing macro definitions, or after editing a literate-elisp .org.
when_to_use: editing .el files; editing .org files containing #+BEGIN_SRC elisp blocks; user mentions literate-elisp, lexical-let, macro re-expansion, "reload after edit", or pcase string patterns.
disable-model-invocation: false
allowed-tools: Read Edit Write Grep
paths: "**/*.el"
---

# lp-hint-elisp — Elisp LP traps and conventions

Points at the canonical Elisp LP hint file:

    ~/projects/literate-agent/hints/elisp.org

## Top traps (read the file for context + workarounds)

1. **`lexical-binding: t` in `.org` headers is IGNORED** by
   literate-elisp. Closures crossing timer / process / callback
   boundaries must use `lexical-let` (from `cl-lib`) explicitly,
   not plain `let`.
2. **`pcase` string patterns compile differently** under dynamic
   binding. Use `cond` + `equal` for string dispatch instead.
3. **Macro re-expansion on reload**: when a macro definition
   changes, every module that USES that macro must also be
   reloaded — old function bodies still contain the old macro
   expansion.
4. **Always reload after `.org` edit**:
   `(literate-elisp-load "FILE.org")`. Saving the file does NOT
   update the running Emacs image.
5. **No `:noweb yes` in Elisp src blocks** — literate-elisp
   doesn't expand `<<chunk>>` references at load time. (Fine for
   Python / TS / Rust src blocks.)
6. **Never run long Elisp via the `evalElisp` MCP tool** — Emacs
   is single-threaded; the call blocks the editor.

## When this skill activates

- Editing any `.el` file (via the `paths: "**/*.el"` matcher).
- Reading or editing a literate `.org` file when Claude infers it
  contains Elisp src blocks (via the `description` + `when_to_use`
  fields).

## Procedure

1. Read `~/projects/literate-agent/hints/elisp.org` end-to-end on
   first activation in a session — the file is short (under 200
   lines).
2. Apply the relevant workaround for the trap that matches the
   user's current action.
3. After editing a literate `.org`, ensure the reload step lands
   in the verification gate.

## See also

- `~/projects/literate-agent/rules/literate-programming-document-first.md`
- `~/projects/literate-agent/rules/lp-comma-escape-leading-star.md`
