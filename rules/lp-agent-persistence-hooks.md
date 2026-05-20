# Provide Persistence Hooks for Agent Readers

> *Last-validated*: 2026-05-20
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: research finding (transfer-gradient observation #1 —
> *cross-session state persistence is the universal transfer-break
> boundary*; direction I); the principle generalises beyond claude-agent.

The single largest source of HI-to-AI-agent transfer breaks identified
by the research is *cross-session state persistence*. Human readers
naturally accrue mental models, partial schemas, and saturated samples
across sessions. AI agents start each conversation with no memory of
prior encounters.

LP documents that assume "the reader remembers" what they read last
month silently fail for agent readers. The mitigation is *external
persistence infrastructure* the agent can re-find on a cold start.

## Required persistence hooks

For any LP module whose load-bearing context cannot fit in a single
section's prose:

1. **Stable identifiers in file naming**. The file name itself is the
   anchor an agent re-finds on a cold start. Concept-named files
   (`claude-agent-backend.org`, `lp-noweb-for-big-blocks.md`) survive
   reorganisation; date-named or session-named files don't. Renames
   break every cross-reference; do them sparingly and through `git mv`.
2. **Stable cross-reference anchors**. `:CUSTOM_ID:` on every
   ≥2-referenced section (see `lp-stable-anchors-for-multi-referenced-
   sections.md`). The agent quoting a section from memory has nothing
   to retrieve; the agent quoting `[[file:X.org::#stable-anchor]]`
   resolves on every cold start.
3. **Explicit summaries at module overview**. The first 1-3 sentences
   of `* Overview` answer "what does this module own, what invariant
   does it protect" — the durable trail of intent. A reader (human
   or agent) hitting this file fresh recovers the role of the file
   in one read. Without a summary, the agent reverse-engineers from
   code on every cold start.
4. **Append-only decisions log**. `RATIONALE.md` / `lp/decisions-log.org`
   recording "we did X because Y" survives every session. New
   contributors (human or agent) learn the codebase history without
   needing to re-derive it.
5. **Cite commits, not "recently"**. `"per commit abc123"` is a
   stable anchor; `"as discussed yesterday"` is unrecoverable.
   Cross-link to a specific commit, PR number, or tagged release.

## What NOT to rely on

- *"The reader will remember from last session"* — false for agents
  by construction; weak for humans (decay + turnover).
- *Implicit context from chat history* — agents may have been
  compacted, branched, or restarted. Anything load-bearing must
  also live in the file.
- *Tribal knowledge that "everyone knows"* — write it down at the
  module overview.

## Layered defence

LP infrastructure provides multiple persistence layers; combine them:

| Layer | Persistence horizon | Example |
|-------|---------------------|---------|
| Tool output (Bash log) | Single message | `make test` result |
| Conversation context | Single session | Recent chat |
| File contents | Forever (until edit) | `module.org` body |
| Cross-file anchors | Forever (until rename) | `[[file:other.org::#anchor]]` |
| Commit history | Forever | `git log -p` |
| Decision log | Forever (append-only) | `RATIONALE.md` |

A claim that cannot be re-derived from the bottom three layers is
*not yet documented* — even if it appears in the top three. Move it
down before declaring done.

## Why this is research-backed and not just convention

The research identifies four canonical HI findings (B *cognitive load
schema construction*, E *mental models accretion*, G *expert
recognition payoff*, I *berry-picking saturated sampling*) that each
require the reader to carry durable state across sessions. All four
have human-stable substrate (inter-session consolidation via sleep,
re-exposure, episodic memory) and *no equivalent in the agent's
stateless cold-start architecture*. Retrieval-augmented generation,
fine-tuning, and explicit memory are architectural workarounds — not
"natural" agent behaviour. The mitigation is external infrastructure
on the LP document side.

## See also

- `rules/lp-stable-anchors-for-multi-referenced-sections.md` — the
  mechanical foundation of stable cross-references.
- `rules/design-stays-in-org.md` — decision history lives in the LP
  file, never in `docs/`.
- `rules/literate-programming-document-first.md` *Overview* section —
  why every module opens with a motivation + invariant paragraph.
