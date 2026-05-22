# Lessons

Append-only log of mistakes the agent (or maintainer) made and the rule
that prevents them next time. Two-tier promotion contract:

1. *Every* user correction → a new entry below.
2. After **≥3 entries of the same kind**, promote the corrective rule
   into `.claude/rules/<topic>.md` (or, if it's a top-level project
   constraint, into `CLAUDE.md` with `IMPORTANT/ALWAYS/NEVER` emphasis).
3. Promotion deletes the lessons entries that motivated it (so this
   file stays small) and adds a `Promoted: <date> → <rule path>` note
   in their place.

## Format

```
### YYYY-MM-DD — <one-line summary>

- *Mistake type:* <e.g. depth-cap drilling, .py edit attempt, missing prose>
- *Context:* <what was being done; which file; which session>
- *Correction:* <what the user said>
- *Rule for next time:* <one sentence the agent can act on>
```

Entries newest-on-top.

## Decisions considered and skipped

These are not lessons in the "I made a mistake" sense — they're
considered uplifts that were *consciously deferred*, captured here so
future-you (or another agent) doesn't re-spend the analysis.

### 2026-04-30 — Generated-by trailer + prompt hash for line-level provenance

- *Source:* Lens #9 (Telemetry / trace) of the AI-codebase-mastery
  research. Generated-by + prompt hash gives forensic value without
  leaking raw prompt; tools include git-ai, frontmatter-skill, Codex
  commit_attribution.
- *Decision:* skip for now. Three reasons:
  1. Solo project, n=1 contributor — commit messages already say
     who/when. The audit-trail need is structurally absent.
  2. The trailer ecosystem is still maturing in 2026; vendor lock-in
     risk is real.
  3. The strict-LP discipline already gives per-section attribution
     (the org prose explains *why* each module is shaped that way),
     which is richer than per-line provenance for the kinds of
     questions we'd want to answer.
- *Reconsider when:* project becomes multi-contributor, OR the trailer
  ecosystem stabilises around one open standard, OR a real audit
  question comes up that the LP prose can't answer.
- *Aligns with:* user's global "no Co-Authored-By" rule — the rejection
  of a coarse trailer doesn't preclude a finer one later.

## Entries

(none yet — will accumulate as we go)

## Promoted entries (history)

(none yet)
