"""Vulture whitelist for literate_python.

Vulture finds dead code by static AST scan; it cannot see consumers
that wire in via Python's import protocol, Flask's decorator-based
routing, multimethod dispatch, or pytest discovery. This file
pre-references every such symbol so vulture treats it as used.

Usage: `poetry run vulture literate_python/ vulture_whitelist.py`
or via the Makefile target `make check-dead-code`.

When you add a new such symbol (e.g. another Flask route, another
multimethod overload), add a line here. When you remove one, delete
its line. The file's churn rate is a good proxy for how often we add
"surface" code vs. internal code.

Each block names *why* the references exist — re-checking the rationale
when whitelisting is the discipline that prevents this file from
becoming a graveyard for genuine dead code.
"""

from literate_python import loader, reloader, server, inspector, sections

# ---------------------------------------------------------------------------
# Python import-system protocol on LiterateImporter
# ---------------------------------------------------------------------------
# `find_module(fullname, path=None)` and `load_module(fullname)` are called
# by CPython's import machinery via meta-path lookup; vulture sees no
# direct caller in our code.
loader.LiterateImporter.find_module
loader.LiterateImporter.load_module

# Module attributes set on the dynamically-created module objects. CPython
# expects these on every module; consumers are external.
# (Vulture flags these by name; we reference them as strings here.)
_MODULE_ATTRS = ("__loader__", "__path__", "__package__")

# Public API stubs — kept as the intended shape of the API even though
# they don't yet have callers in this repo. Removing them is a deliberate
# API decision, not a vulture cleanup.
loader.load_literate_modules_from_org_file
loader.load_literate_modules_from_org_node
loader.build_org_model_from_local_python_package

# `path` parameter is part of the import-protocol signature; can't be
# renamed away without breaking the contract.
# (Vulture also flags it; see import-protocol comment above.)

# ---------------------------------------------------------------------------
# multimethod dispatch on `_inspect`
# ---------------------------------------------------------------------------
# inspector.py uses `@_inspect.register` to register overloads; each
# overload is named `_` per multimethod convention. Vulture sees them
# as repeated unused functions. They are loaded by import-side effect
# the moment inspector is imported, and consumed by `_inspect(value)`.
inspector.trim_seq  # called inside one of the `_` overloads

# ---------------------------------------------------------------------------
# Flask route handlers (server.py)
# ---------------------------------------------------------------------------
# `@app.route(...)` registers each function with Flask's URL map; vulture
# can't see Flask as a caller.
server.register_router
server.execute
server.status

# ---------------------------------------------------------------------------
# ModuleReloader public API
# ---------------------------------------------------------------------------
# These methods are consumed by external clients (the Emacs side calls
# them through the JSON-RPC layer in /lpy/execute) and by future code
# in this repo. Keep on surface.
reloader.ModuleReloader.clear_stale_modules
reloader.ModuleReloader.get_import_info

# Internal state attributes on ModuleReloader. Vulture flags reads/writes
# inside the same class as "unused" when they're only set in __init__ and
# accessed via getattr/dict.
reloader.ModuleData  # the dataclass with last_modified / old_objects fields

# ---------------------------------------------------------------------------
# Test surfaces
# ---------------------------------------------------------------------------
# pytest auto-discovers `test_*` functions; vulture doesn't understand
# pytest. These are real tests, not dead code.
sections.test_optimal_clusters
# tests/test_server.py and tests/test_hot_reload.py use unittest.TestCase
# discovery — same pytest reasoning applies, but unittest also walks all
# `test_*` methods on TestCase subclasses.
