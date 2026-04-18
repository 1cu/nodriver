# Repository guide

## Layout
- `nodriver/core/` is handwritten runtime; `nodriver/__init__.py` re-exports the public API (`start`, `Browser`, `Tab`, `Config`, `Element`).
- `nodriver/cdp/` is generated CDP code; do not hand-edit it. Regenerate from `generate_cdp.py`, which reads `third_party/devtools-protocol/{browser_protocol.json,js_protocol.json}`.
- `tests/` contains unit tests and browser integration tests; `example/` is runnable demos, not tests.
- `docs/` is Sphinx docs. `docs/_build/html` and `docs/_build/markdown` are checked in on purpose.

## Commands
- Use PDM, not tox.
- `pdm install -G build -G lint -G test -G docs`
- `pdm run lint`
- `pdm run pytest -q tests/test_config.py` for one unit test file, or append `::test_name` for a single test.
- `pdm run pytest -q -m integration tests/test_browser_integration.py` for browser-backed tests.
- `pdm run build`
- `pdm run docs-html` / `pdm run docs-markdown`

## Browser / integration tests
- Browser tests need a Chromium/Chrome executable; set `NODRIVER_BROWSER_EXECUTABLE` if auto-discovery does not find one.
- On headless Linux, reproduction may need `xvfb-run`, matching CI.

## Generated / vendored inputs
- If you refresh CDP, update the vendored protocol JSONs together and keep their README/license and pinned SHA in sync.
- Do not edit generated docs under `docs/_build` by hand.
- `black`/`isort` checks are scoped to `nodriver/core`; do not reformat generated files unless regenerating them.
