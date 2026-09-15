# REL Crawlee integration

Use Crawlee's request queue, retries, router, and datasets with Chromium sessions
owned by REL. See the [Crawlee guide](../docs/CRAWLEE.md) for installation,
examples, supported behavior, and verification.

```sh
# From the rel-tools repository root:
python3 -m venv .venv
.venv/bin/python -m pip install -e playwright -e crawlee
.venv/bin/python crawlee/examples/basic.py
```

This package pins Crawlee 1.10.0 and requires the cancellation-safe
`rel-playwright` 0.1.1 or later. It uses no Playwright browser installation.

Opt into reuse with `RelCrawler(session_pool_size=2)`; fresh sessions remain the
default. `crawler.metrics` exposes immutable per-run timing and lifecycle totals.
The [benchmark example](examples/benchmark.py) compares both modes with a saved
Profile and writes results to a new directory.
