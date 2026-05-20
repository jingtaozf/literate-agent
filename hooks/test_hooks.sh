#!/usr/bin/env bash
# Regression suite for the LP-tangle PreToolUse hooks.
#
# Run from anywhere:  .claude/hooks/test_hooks.sh
# Exit code: 0 if every case passes the expectation, non-zero otherwise.
#
# Covers two hooks:
#   - block-tangled-edit.sh       (matcher: Edit / Write / MultiEdit)
#   - block-bash-tangle-write.sh  (matcher: Bash)

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK_EDIT="$ROOT/.claude/hooks/block-tangled-edit.sh"
HOOK_BASH="$ROOT/.claude/hooks/block-bash-tangle-write.sh"

PASS=0
FAIL=0

# run_edit <label> <tool> <abs_file_path> <want=PASS|REJECT>
run_edit() {
  local label=$1 tool=$2 fp=$3 want=$4
  local out rc got
  out=$(command printf '{"tool_name":"%s","tool_input":{"file_path":"%s"}}' "$tool" "$fp" \
        | CLAUDE_PROJECT_DIR="$ROOT" python3 "$HOOK_EDIT" 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then got=PASS; else got=REJECT; fi
  if [ "$got" = "$want" ]; then
    command printf "  ✓ %-32s  %s\n" "$label" "$got"
    PASS=$((PASS+1))
  else
    command printf "  ✗ %-32s  want=%s got=%s rc=%d\n" "$label" "$want" "$got" "$rc"
    FAIL=$((FAIL+1))
  fi
}

# run_bash <label> <cmd> <want=PASS|REJECT>
run_bash() {
  local label=$1 cmd=$2 want=$3
  local out rc got
  out=$(command printf '{"tool_name":"Bash","tool_input":{"command":%s}}' \
        "$(command python3 -c "import json,sys;print(json.dumps(sys.argv[1]))" "$cmd")" \
        | CLAUDE_PROJECT_DIR="$ROOT" python3 "$HOOK_BASH" 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then got=PASS; else got=REJECT; fi
  if [ "$got" = "$want" ]; then
    command printf "  ✓ %-32s  %s\n" "$label" "$got"
    PASS=$((PASS+1))
  else
    command printf "  ✗ %-32s  want=%s got=%s\n" "$label" "$want" "$got"
    FAIL=$((FAIL+1))
  fi
}

# Pick stable fixture paths from the repo.
ASM_PY="$ROOT/repos/automated-skill-management/src/automated_skill_management/__init__.py"
INFRA_TF="$ROOT/repos/mega-code-infra/acm.tf"
WEB_TSX="$ROOT/repos/mega-code-web/src/app/(admin)/api-keys/components/api-keys-table.tsx"
ALEMBIC_PY="$ROOT/repos/skill-enhance-server/alembic/versions/20260511_0001_prebuilt_skills.py"
TFVARS="$ROOT/repos/mega-code-infra/dev/terraform.tfvars"
README_MD="$ROOT/repos/mega-code-oss/README.md"
META_SCRIPT="$ROOT/scripts/build_tangle_map.py"

echo "════════════════════════════════════════════════════════════════"
echo " block-tangled-edit.sh — Edit / Write / MultiEdit matcher"
echo "════════════════════════════════════════════════════════════════"
echo "── Negative (PASS) ──"
run_edit "outside-repos-script"  Edit   "$META_SCRIPT"   PASS
run_edit "alembic-whitelist"     Edit   "$ALEMBIC_PY"    PASS
run_edit "wrong-tool-Read"       Read   "$ASM_PY"        PASS
echo "── Positive (REJECT, exact-org expected) ──"
run_edit "edit-py-tangled"       Edit       "$ASM_PY"    REJECT
run_edit "write-tf-tangled"      Write      "$INFRA_TF"  REJECT
run_edit "multiedit-tsx-tangled" MultiEdit  "$WEB_TSX"   REJECT

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " block-bash-tangle-write.sh — Bash matcher"
echo "════════════════════════════════════════════════════════════════"
echo "── Negative (PASS) ──"
run_bash "ls-la"              'ls -la'                                                  PASS
run_bash "grep-noop"          'cat foo.py | grep bar'                                   PASS
run_bash "write-outside"      'sed -i s/x/y/ /tmp/foo.py'                               PASS
run_bash "echo-outside"       'echo "x" > /tmp/foo.py'                                  PASS
run_bash "tfvars-not-blocked" 'sed -i s/x/y/ repos/mega-code-infra/dev/terraform.tfvars' PASS
run_bash "md-not-blocked"     'echo x > repos/mega-code-oss/README.md'                  PASS
run_bash "alembic-whitelist"  'sed -i s/x/y/ repos/skill-enhance-server/alembic/versions/x.py' PASS
run_bash "find-no-exec"       'find repos/ -name "*.py"'                                PASS
run_bash "find-name-list"     'find repos/mega-code-infra -name "*.tf"'                 PASS
run_bash "find-exec-rm-OK"    'find /tmp -name "*.tmp" -exec rm {} ;'                   PASS
run_bash "make-tangle"        'make tangle FILE=lp/mega-code-infra/foundation.org'      PASS

echo "── Positive: write to LP-managed path (REJECT) ──"
run_bash "sed-i"              "sed -i s/x/y/ $ASM_PY"                                                REJECT
run_bash "echo-redirect"      "echo \"x\" > $ASM_PY"                                                 REJECT
run_bash "cat-redirect"       "cat foo > $INFRA_TF"                                                  REJECT
run_bash "append-redirect"    "echo y >> $INFRA_TF"                                                  REJECT
run_bash "tee-write"          "echo x | tee $INFRA_TF"                                               REJECT
run_bash "cp-overwrite"       "cp /tmp/foo.py $ASM_PY"                                               REJECT
run_bash "mv-overwrite"       "mv /tmp/foo.py $ASM_PY"                                               REJECT
run_bash "awk-inplace"        "awk -i inplace 'NR==1' $INFRA_TF"                                     REJECT
run_bash "perl-i"             "perl -i -pe 's/x/y/' $INFRA_TF"                                       REJECT

echo "── Compound ──"
run_bash "compound-&&"        "ls && sed -i s/x/y/ $INFRA_TF"                                        REJECT
run_bash "compound-;"         "echo x ; cat foo > $INFRA_TF"                                         REJECT
run_bash "compound-||"        "true || sed -i s/x/y/ $INFRA_TF"                                      REJECT
run_bash "pipeline-tee"       "cat foo | tee $INFRA_TF"                                              REJECT
run_bash "subshell-doll"      "true; X=\$(sed -i s/x/y/ $INFRA_TF)"                                  REJECT

echo "── Opaque fail-closed ──"
run_bash "eval-write"         "eval \"echo x > $INFRA_TF\""                                          REJECT
run_bash "python-c-write"     "python3 -c 'open(\"repos/foo/bar.py\",\"w\").write(\"x\")'"           REJECT
run_bash "bash-c-nest"        "bash -c \"sed -i s/x/y/ $INFRA_TF\""                                  REJECT
run_bash "xargs-write"        "echo foo | xargs -I {} cp {} $INFRA_TF"                               REJECT
run_bash "find-exec-sed-i"    'find repos/mega-code-infra -name "*.tf" -exec sed -i "s/x/y/" {} ;'   REJECT
run_bash "find-exec-cp"       'find /tmp -name "*.py" -exec cp {} repos/mega-code-infra/acm.tf ;'    REJECT
run_bash "find-execdir-sed"   'find repos/mega-code-infra -name "*.tf" -execdir sed -i "x" {} ;'     REJECT

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " Summary:  pass=$PASS  fail=$FAIL"
echo "════════════════════════════════════════════════════════════════"
exit $FAIL
