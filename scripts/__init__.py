"""literate-agent LP source-drift roundtrip toolkit.

Console-script entry points (pip install / pre-commit):
  lp-protocol-verify    — 6-invariant audit (V1-V6) for sync round-trip safety
  lp-sync-bootstrap     — stamp file-level SHA + per-block BLOCK_KIND
  lp-sync-engine        — 3-pass source-drift sync (Pass A modify / B add / C stale)
  lp-audit-metadata     — schema-invariant audit (subset of V1)
  lp-audit-anchors      — :CUSTOM_ID: coverage audit
  lp-backfill-anchors   — auto-stamp :CUSTOM_ID: on multi-ref sections

Modules can also be imported and called as libraries — each has a
`main()` returning int (POSIX exit code).
"""
