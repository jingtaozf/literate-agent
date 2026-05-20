---
description: Insert a four-part literate-programming section (heading + CUSTOM_ID + prose preamble + src block) at point in an .org file. User-invocable via `/lp-section <heading>`.
when_to_use: invoke as `/lp-section <heading-name>` when the user is in an .org file and wants to start a new LP-conforming section. Typical triggers: "scaffold a new section", "insert a new LP section called X", "add a section for X".
disable-model-invocation: true
user-invocable: true
argument-hint: <heading-text>
allowed-tools: Read Edit Write Grep
paths: "**/*.org"
---

# /lp-section — scaffold a four-part LP section

Generates the canonical four-part section shape documented in
`~/projects/literate-agent/rules/org-mode-docs-first.md`:

1. **Heading** naming a *concept* (not "Functions" / "Helpers")
2. **`:CUSTOM_ID:`** drawer with a stable kebab-case anchor
3. **1-3 sentence prose preamble** placeholder (you fill it)
4. **`#+BEGIN_SRC` block** placeholder (you fill it)

## Argument

`$ARGUMENTS` is the heading text. The skill derives:

- `:CUSTOM_ID:` slug: kebab-case of the heading
- Default language for the src block: inferred from file extension
  context (Elisp for `.org` near `.el`, Python for `.org` near
  `.py`, leave generic otherwise)

## Output template (depth 2)

```
,** $ARGUMENTS
:PROPERTIES:
:CUSTOM_ID: <kebab-case-of-arguments>
:END:

<TODO: 1-3 sentence prose preamble — name the WHY, the trade-off,
or the rejected alternative. If this section has no design tension,
ask whether it earns its own section at all.>

,#+BEGIN_SRC <lang>
<TODO: code body — one meaningful step, not a grab bag>
,#+END_SRC
```

## Procedure

1. Find the insertion point — typically at the end of the current
   sibling group, or at `(point)` if inside a section.
2. Insert the template with `:CUSTOM_ID:` filled.
3. Leave both TODO placeholders for the user to fill — do NOT
   guess the prose or the code body.
4. Return cursor to the prose placeholder (the *why* comes first).

## Anti-patterns to refuse

If `$ARGUMENTS` is one of these, push back instead of scaffolding:

- `Functions`, `Helpers`, `Utilities`, `Implementation`, `Misc`,
  `Code`, `Stuff` — these name a *category*, not a *concept*.
  Ask the user to name the role.
- A heading > 60 chars — that's not a heading, it's a sentence.
  Ask the user to shorten.

## See also

- `~/projects/literate-agent/rules/literate-programming-document-first.md` — the why
- `~/projects/literate-agent/rules/org-mode-docs-first.md` — the four-part shape canon
- `~/projects/literate-agent/rules/lp-prose-no-self-narration.md` — what makes the prose preamble useful vs filler
