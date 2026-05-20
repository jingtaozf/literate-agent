# Default preamble for `literate-agent/scripts/build_index.py`.
#
# The script inlines this file verbatim at the top of every generated
# INDEX.org. Override on a per-project basis by passing
# `--preamble <path>` to the script, pointing at the project's own
# preamble file.
#
# Lines starting with `#` are NOT stripped — they appear in the
# generated org file as-is. If you don't want this header, replace
# it with project-neutral org-mode prose.

This index is automatically generated from the project's literate
`.org` sources. Each row maps a tangled output module back to the
section of the owning `.org` file that defines it. Click any heading
to jump to the section at the right line.

If a row's expected module is missing, run the build_index step in
the project's Makefile and verify the `.org` source has a
`:tangle <path>` property the script can pick up.
