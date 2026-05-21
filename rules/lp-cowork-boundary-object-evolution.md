# Cowork: Boundary-Object Discipline for Plugin Evolution

> *Last-validated*: 2026-05-21
> *Review cadence*: quarterly — drop if 6 months without a triggering incident
> *Origin*: cowork research loop direction J — Star & Griesemer
> 1989's boundary-object framework applied to `literate-agent`
> itself as a cross-project artefact. Codified the day a real
> boundary-violation incident shipped a fix to
> `hooks/lib/tangle_lookup.py`.
> *Triggering incident*: 2026-05-21 — a claude session whose
> `CLAUDE_PROJECT_DIR` was `mind-ai/dev-agent` directly edited
> `mind-ai/edo-literate/repos/mega-code/mega_code/config.py` and
> several sibling files. The block-tangled-edit hook fell out of
> scope because the file path was outside the session's
> `CLAUDE_PROJECT_DIR`. The fix added `find_owning_project` +
> `load_project_env` to `hooks/lib/tangle_lookup.py` — boundary-
> detection logic that walks up from the file path looking for a
> `.claude/hooks/_env.sh` marker.

`literate-agent` is a *boundary object* (Star & Griesemer 1989)
serving multiple consumer projects — claude-agent, edo-literate,
and future consumers each interpret the plugin's doctrine locally
through `_env.sh` overrides, project-specific `@`-import subsets,
optional skill/hook adoption, and Makefile customisation. The
plugin's value depends on preserving this dual nature: *robust*
enough to maintain a coherent shared doctrine across consumers,
*flexible* enough that each consumer can adapt without forking.

Every addition to `literate-agent` is a boundary-object evolution
event. The discipline that keeps the object alive is the topic of
this rule.

## The empirical anchor

Star & Griesemer 1989 (=Social Studies of Science 19(3)=) studied
the Berkeley Museum of Vertebrate Zoology 1907-1939 and showed
that scientific specimens served amateur trappers, professional
taxonomists, museum administrators, and university biologists
*simultaneously without single interpretation*. The mechanism is
the artefact's dual nature: it is *robust* (each community
recognises the same physical object) AND *flexible* (each
community gives it locally appropriate meaning).

Star 2010 revisited the concept and tightened the design
constraint: under-structuring kills the boundary object (becomes
too fluid to coordinate); over-structuring kills it (becomes too
rigid to adapt). The robust + flexible balance is the design
target.

## Two constraints every addition must satisfy

1. *Doctrine preservation*. The general claim survives across all
   consumers. A new rule must read clean to a consumer that has
   never seen the project that motivated it. Project-specific
   examples are fine as illustration; project-specific *claims*
   in the rule body are not.
2. *Override capacity preservation*. The consumer must be able to
   adapt or disable the addition without forking `literate-agent`.
   Mechanisms: env vars in `_env.sh`, per-project `@`-import
   scoping, optional skill activation via `--plugin-dir`, optional
   hook adoption via `hooks.json` discovery.

If your proposed change violates either, it does not belong in
`literate-agent`. It belongs in the consumer project that needs
it.

## Pre-flight checklist before adding to literate-agent

Before merging a new rule / hook / skill / script / command:

- [ ] *Multi-consumer evidence*. Cite at least 2 consumer
      projects (or 1 consumer + 1 strong theoretical case) where
      this would land cleanly.
- [ ] *Override path*. Document how a consumer disables or
      adapts this — env var, `@`-import scope, alternative
      template, etc. If there's no override, document why
      override is unnecessary (rare).
- [ ] *No hard-coded consumer state*. Paths use
      `${CLAUDE_PROJECT_DIR}` (consumer-local) or
      `${CLAUDE_PLUGIN_ROOT}` (plugin-local), never absolute paths
      to specific consumer projects.
- [ ] *Terminology portability*. The rule's vocabulary survives
      consumer-project terminology drift. One consumer uses
      `lp/<sub>/` layout, another uses `src/`; the rule's text
      should not embed either assumption as primary.

## Cross-project guard for hooks specifically

The 2026-05-21 incident exposed a separate boundary-object
failure mode: hooks tied to `CLAUDE_PROJECT_DIR` silently fall out
of scope when the file path is *outside* the session's project.
The fix (committed to `hooks/lib/tangle_lookup.py`) walks up from
the file path looking for `.claude/hooks/_env.sh` as a marker
that "this is an LP-managed project," then evaluates LP scope in
*that* project's frame regardless of session origin.

The general lesson: *every hook must detect the owning project
from the artefact, not the session*. Hard-coding the session's
project as the only scope is a boundary-object failure — it
treats the plugin's view as more authoritative than the
artefact's actual owning project.

## Worked example: `LITERATE_AGENT_TANGLE_MAKE_TARGET`

The env var was added because claude-agent uses `make tangle-python`
(single Python tangle entry point) while edo uses `make tangle
FILE=...` (per-file invocation). Boundary-object design check:

- *Doctrine preservation*: ✓ The general claim ("hooks run a
  make target to re-tangle") survives. Both consumers re-tangle
  via make; only the target name differs.
- *Override capacity*: ✓ Each consumer's `_env.sh` exports its
  preferred target. Default is `tangle` (most projects use it),
  override is one line.
- *No hard-coded state*: ✓ The hook reads
  `${LITERATE_AGENT_TANGLE_MAKE_TARGET:-tangle}`, never
  references `tangle-python` directly.
- *Terminology portability*: ✓ `make` is universal vocabulary;
  works for any consumer with a Makefile.

This is the template every future env-overridable knob should
follow.

## Anti-patterns

1. *Hard-coded consumer paths in literate-agent code or docs.* A
   rule that references `claude-agent-python.org` by name (rather
   than as an example) bakes one consumer's vocabulary into the
   plugin. Use `<project>-python.org` or similar placeholder.
2. *Zero override capacity.* A new rule with no escape hatch
   forces every consumer to adopt it or fork. Always provide an
   env var, `@`-import scope, or opt-in skill mechanism.
3. *Override-without-default.* A new env var that's *required*
   for the hook to work breaks every existing consumer the moment
   it ships. Defaults must keep existing consumers running.
4. *Session-scope assumption in hooks*. Treating
   `CLAUDE_PROJECT_DIR` as the only authority on "which project
   does this file belong to" — the 2026-05-21 incident's root
   cause. Walk up from the artefact instead.

## When a change should NOT go into literate-agent

A change belongs in the consumer project (not the plugin) when:

- It encodes one consumer's *specific* convention that other
  consumers shouldn't be expected to adopt.
- The override would have to be "disable this entirely," which
  means the addition didn't earn its place in the plugin.
- The triggering incident was a one-off pattern unlikely to
  recur across other consumers.

The consumer's `.claude/rules/` is the right home for these. The
plugin's `rules/` is for cross-consumer doctrine.

## Self-test: is `literate-agent` itself a healthy boundary object?

Periodically (quarterly?) audit:

- *Does every consumer's `_env.sh` override at least one
  variable?* If two consumers use literally identical settings,
  one of them probably doesn't need its `_env.sh` — or the
  default needs to change.
- *Does any rule body contain a consumer's exact project name
  outside of an "Origin" line?* If so, that's potential
  hard-coding to clean up.
- *Have any consumers had to fork a rule because they couldn't
  override it?* If yes, that rule's override capacity is broken.

## See also

- `docs/cowork-research.org` — direction J synthesis + 2026-05-21
  incident traced as a real boundary-object violation.
- `hooks/lib/tangle_lookup.py` — implements the cross-project
  owning-project detection that fixes the 2026-05-21 incident.
- `rules/lp-load-bearing-affordances-structural.md` — the
  reader-side equivalent (within-project boundary object: same
  file serving human + agent readers).
