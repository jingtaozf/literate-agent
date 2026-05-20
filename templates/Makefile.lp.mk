# literate-agent Makefile fragment — LP build / lint targets.
#
# Drop this into your project as `Makefile.lp.mk` and include it
# from the top-level Makefile:
#
#     include Makefile.lp.mk
#
# The hooks shipped in `~/projects/literate-agent/hooks/` expect a
# few of these targets to exist:
#
#   - tangle       — invoked by tangle-org-buffer.sh as the batch
#                    fallback when emacsclient isn't available.
#   - tangle-all   — re-tangle every .org in the project.
#   - check-structure — depth ≤ 5, prose-before-src, no grab-bag
#                    headings; invoked by /lp-check.
#   - build-tangle-map — refresh .cache/tangle-map.tsv; invoked by
#                    block-tangled-edit.sh on cache miss.
#
# Override LP_ROOT below if your literate sources don't live under
# ./lp/. The default matches edo-literate's multi-submodule layout.

LITERATE_AGENT_HOME ?= $(HOME)/projects/literate-agent
LP_ROOT ?= lp

# ── tangle ────────────────────────────────────────────────────────────────

# Re-tangle a single .org file. Used by the auto-tangle PostToolUse hook.
# Usage: make tangle FILE=lp/foo/bar.org
tangle:
	emacs --batch \
	  --eval "(require 'org)" \
	  --eval "(org-babel-tangle-file \"$(FILE)\")"

# Re-tangle every .org under LP_ROOT.
tangle-all:
	find $(LP_ROOT) -name "*.org" ! -name "_*" -print0 \
	  | xargs -0 -I {} $(MAKE) tangle FILE={}

# ── structure check ───────────────────────────────────────────────────────

# Static lint of LP structural rules: depth ≤ 5, no grab-bag headings,
# prose-before-src on any section that tangles. Used by /lp-check.
check-structure:
	python3 $(LITERATE_AGENT_HOME)/scripts/check_org_structure.py

# ── cache refresh ─────────────────────────────────────────────────────────

# Refresh the reverse-lookup cache that block-tangled-edit.sh uses
# to point edits at the owning .org. Run after any :tangle path change.
build-tangle-map:
	python3 $(LITERATE_AGENT_HOME)/scripts/build_tangle_map.py

# ── nav index + readmes ───────────────────────────────────────────────────

# Regenerate INDEX.org from literate .org sources.
#
# Multi-submodule (edo-style) — auto-detects lp/, groups by submodule:
#     make build-index
#
# Single-file (claude-agent-style) — explicit file + narrow filter +
# custom output name:
#     make build-index BUILD_INDEX_ARGS="--output INDEX-python.org \
#         --filter 'python/.*\\.py$$' claude-agent-python.org"
build-index:
	python3 $(LITERATE_AGENT_HOME)/scripts/build_index.py $(BUILD_INDEX_ARGS)

# Regenerate root README + per-submodule READMEs from .org metadata.
build-readme:
	python3 $(LITERATE_AGENT_HOME)/scripts/build_readme.py

# ── drift audit ───────────────────────────────────────────────────────────

# Re-tangle every submodule, then `git -C repos/<sub> diff --stat`.
# Non-empty diff = either an .org edit that didn't re-tangle, OR a
# direct .py edit that slipped past the PreToolUse hook.
check-tangle-drift:
	python3 $(LITERATE_AGENT_HOME)/scripts/audit_tangle_drift.py

# ── docs-first measurement ────────────────────────────────────────────────

# One-shot measurement of prose-density across the .org tree.
measure-docs-first:
	$(LITERATE_AGENT_HOME)/scripts/measure-docs-first.sh

.PHONY: tangle tangle-all check-structure build-tangle-map \
        build-index build-readme check-tangle-drift measure-docs-first
