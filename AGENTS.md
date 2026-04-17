# Repository guide

## Layout
- `nodriver/core/` is the handwritten runtime; public entrypoints are re-exported from `nodriver/__init__.py` (`start`, `Browser`, `Tab`, `Config`, `Element`).
- `nodriver/cdp/` is generated CDP code. Do not edit those files by hand; regenerate from the CDP spec via `generate_cdp.py` / PyCDP.
- `third_party/devtools-protocol/` contains vendored CDP protocol snapshots used by `generate_cdp.py`; update those JSON files together with any generator changes, and keep the vendored license/README (including the pinned upstream commit SHA) in sync.
- `example/` holds runnable demos, not tests.
- `docs/` is Sphinx docs; build outputs under `docs/_build/html` and `docs/_build/markdown` are intentionally kept in the repo.

## Contribution policy
- Upstream does not accept issues or pull requests, so we never contribute local changes upstream.
- Make changes only in non-generated code files; do not modify generated files directly.
- Third-party vendored protocol snapshots are an exception to the generated-code rule: edit them only when intentionally refreshing the pinned CDP source, and treat them as source inputs rather than hand-maintained library code.

## Git workflow
- Use conventional commits for commit messages, e.g. `fix: ...`, `feat: ...`, `docs: ...`.
- Name branches clearly and consistently, using a short lowercase slash-separated format such as `fix/…`, `feat/…`, or `docs/…`.
- Keep pull requests concise but well structured: include a short summary, key changes, and any verification performed.

## Commands
- Build docs from `docs/` with `make html` or `make markdown`.
- Package check/build with `python -m build`.
- Repo formatting is the black/isort combo used in the helper script: `black nodriver/core/*.py` and `isort nodriver/core`.

## Gotchas
- Chrome/Chromium must be installed locally; on headless Linux, use headless mode or Xvfb.
- There is no active repo test suite (`tox.ini` is a commented sample, and there is no `tests/` tree), so do not waste time searching for a pytest target.
- Regenerating CDP code should use the vendored protocol snapshots; do not rely on live `master` fetches unless you are explicitly refreshing those inputs.
