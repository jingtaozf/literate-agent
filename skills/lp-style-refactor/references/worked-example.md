# Worked example — one iteration on `validator.org` (PCR Stage 3)

Real iteration `c49f0f9` from the 10-iter cron run.

## Before — Audit findings (paraphrased)

```
File: lp/pcr-skill-networking/validator.org

[improvement] § "Observed NodeEdges" table mentions cp_S, cp_N, pr_S,
              pr_N without defining them. These appear in the P_R
              composite formula and are otherwise opaque.

[cleanup]     ValidatorProcessor docstring has a "Scoped validation"
              paragraph that duplicates the prose preamble added in the
              parent commit.
```

## Triage

- Improvement priority 2 ("Define a still-undefined jargon term in
  plain language") + cleanup priority 2 ("Drop a docstring sentence
  the surrounding prose now covers") — natural pairing.

## Apply — single Edit

**Improvement diff** (in `lp/pcr-skill-networking/wisdomgraph.org` § "Observed
NodeEdges"):

```diff
 Per wisdom, Stage 2 writes three edges with =source = "observed"=:

+First, the four scores Stage 1 attached to every =ParsedWisdom=
+(authoritative definitions live in =parser/prompt_builder.py= lines
+110-113 — what the LLM is *told* to estimate):
+
+| Stage-1 score | reads as           | plain-English meaning                                             |
+|---------------+--------------------+-------------------------------------------------------------------|
+| =cp_S=        | C→P Sufficiency    | "if these Context conditions hold, how likely is this Primary the right one?" |
+| =cp_N=        | C→P Necessity      | "if this Primary is the right action, how likely are exactly these Context conditions present?" |
+| =pr_S=        | P→R Sufficiency    | "if this Primary runs correctly, how likely is this Result?"      |
+| =pr_N=        | P→R Necessity      | "if this Result happened, how likely was this Primary required?"  |
+
+Stage 2 then writes three observed edges per wisdom with
+=source = "observed"=:
+
 | edge_type | S formula                  | N formula                       |
 |-----------+----------------------------+---------------------------------|
 | =P_C=     | =cp_S=                     | =cp_N=                          |
 | =C_R=     | from the C↔R pair scores   | from the C↔R pair scores        |
 | =P_R=     | =cp_S × pr_S=  (composite) | =min(cp_N, pr_N)=  (composite)  |
```

**Cleanup diff** (in `lp/pcr-skill-networking/validator.org`
`ValidatorProcessor` docstring):

```diff
   The LLM may also **discover** new edges between nodes it sees in the
   prompt's neighbor context.
-
-Scoped validation (for incremental updates):
-  When scope is set, only the affected wisdoms are sent to the LLM.
-  ALL edges are still passed so the LLM sees correct neighbor context.
-  _apply_verdicts passes through unscoped edges unchanged.
 """
```

## Verify

```
make tangle FILE=lp/pcr-skill-networking/wisdomgraph.org
make tangle FILE=lp/pcr-skill-networking/validator.org
git -C repos/pcr-skill-networking diff --stat
  src/pcr_skill_networking/validator/processor.py | 5 -----
  1 file changed, 5 deletions(-)
```

The wisdomgraph diff was empty (prose-only); the validator diff was
exactly 5 lines (the dropped "Scoped validation" docstring block) — as
intended. Validator unit tests ran:

```
27 passed
```

## Commit

Submodule first (code changed):

```
[jt f05daba] chore(lp): iter 1/10 cleanup — drop redundant Scoped-validation docstring
 1 file changed, 5 deletions(-)
```

Meta-repo second:

```
[jt c49f0f9] lp(pcr): readability iter 1/10 — define cp_*/pr_* scores + drop redundant docstring
 3 files changed, 26 insertions(+), 20 deletions(-)
```

## Total cost

- 1 audit (≤ 30s, script)
- 1 triage (≤ 2 min, Claude)
- 2 Edit ops (≤ 5 min, Claude)
- 2 tangle + 1 test run (≤ 1 min, scripts)
- 2 commits + 2 pushes (≤ 1 min)

**~10 min wall-clock per iteration.**

10 such iterations on the 3 PCR files yielded +1300 prose lines / -35
.py lines / 4 stable CUSTOM_ID anchors / 3 See-also navigation footers
/ 11+ cross-stage org links — all while preserving every src block
(24/19/116 before == after).

## Anti-pattern in the same iteration (corrected post-hoc)

The `,#+method:` line in the original worked example was an
accidental org-keyword-looking artifact. The fix during iter 1 was to
drop the comma and rewrite as plain prose:

```diff
-,#+method:  ingest-2026-04, llm=claude-sonnet-4.7
+method:                  "claude-sonnet-4.7"     ← who/what produced this triplet
```

Take-away: when writing illustrative org-mode artifacts in prose, avoid
patterns that look like real org-mode directives unless they are.
