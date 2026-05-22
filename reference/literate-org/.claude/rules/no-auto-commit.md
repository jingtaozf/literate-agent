# No Auto Commit or Push

Adapted from `~/projects/mind-ai/agents/mega/pcr_skill_networking/.claude/rules/no-auto-commit.md`.
Reinforces the user-level rule
`/Users/jingtao/.claude/CLAUDE.md` "Don't git commit or push unless user
explicitly asks". Project-level repetition is intentional — new
collaborators see this in `.claude/rules/` first.

Never run `git commit` or `git push` unless the user explicitly asks in
the current message. Do not infer commit/push intent from context like
"let's tangle this" or "fix this section".

Only commit when the user says words like "commit", "push", "git commit".

For literate-org specifically: tangling is *not* committing. After
re-tangle, the working tree may have updated `literate_python/*.py`;
leave them in the working tree and let the user decide when to commit.
