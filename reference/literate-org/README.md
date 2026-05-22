# literate_python

A Python runtime that imports modules from Org files. Code lives in
`literate-org.org` as `#+begin_src python` blocks; tangling produces
`literate_python/*.py` for downstream consumers; either path imports
through Python's normal `sys.meta_path` mechanism.

Optional Flask server (`make server`) exposes `/lpy/execute`,
`/lpy/register`, `/lpy/status` for editor-side clients (Emacs, Cursor,
…) — supports cross-module hot reload.

## Install

```bash
pip install literate_python
```

or for development:

```bash
git clone https://github.com/jingtaozf/literate-org
cd literate-org
poetry install
```

## Use

```python
from literate_python import server  # resolved via LiterateImporter
```

## Documentation

- [`README.org`](https://github.com/jingtaozf/literate-org/blob/main/README.org) — full project README (richer than this PyPI summary).
- [`AGENTS.md`](https://github.com/jingtaozf/literate-org/blob/main/AGENTS.md) — guidance for AI agents working in the repo.
- [`ARCHITECTURE.org`](https://github.com/jingtaozf/literate-org/blob/main/ARCHITECTURE.org) — invariants, trust boundaries, contracts.

## License

MIT. See [`LICENSE`](https://github.com/jingtaozf/literate-org/blob/main/LICENSE).
