# REL tools

Open-source command-line, MCP, and Rust clients for
[REL](https://rel.me), plus the public contract for its local versioned API.

REL is not an open-source product. This repository intentionally contains only
clients and documentation for integrating with the proprietary macOS app. It
does not contain REL.app, the local agent implementation, Chromium integration,
session storage, proxy credentials, or internal service code.

## What is here

- [`rel-cli`](crates/rel-cli): the `rel` command and standalone `rel-mcp` stdio
  adapter.
- [`rel-client`](crates/rel-client): a typed synchronous Rust client for RPC v1.
- [`rel-crawler`](crawler): a restartable Python crawler that preserves REL
  sessions and browser history while capturing rendered pages and metadata.
- [`rel-playwright`](playwright): a Playwright-shaped sync and async Python
  scraping API backed by REL Profiles and Sessions.
- [`plugins/rel`](plugins/rel): the shared REL plugin for Codex and Claude Code,
  distributed through this repository's marketplaces.
- [`docs`](docs): the canonical Actions, CLI, MCP, RPC, and Rust SDK
  documentation that powers [docs.rel.me](https://docs.rel.me).

All clients require REL.app in `/Applications`; they connect only to its
loopback API. Download the app from [REL.me](https://rel.me).

## Install the CLI

The app's **Settings → General → Install Command Line** task installs the
bundled, matching CLI into a writable directory already in `PATH`. To build the
public client independently:

```sh
cargo install --git https://github.com/rel-me/rel-tools \
  --tag v0.1.1 \
  --package rel-cli
```

Then try:

```sh
rel health
rel https://rel.me
```

Capture writes page data to standard output and events to standard error. Use
`rel navigate`, `rel perform`, and argument-free `rel capture` for a stateful
page workflow. Use `rel session` to manage persistent browser sessions.
See the [Actions reference](docs/ACTIONS.md) for every supported browser
interaction and its JSON shape.

## Install the agent plugins

The repository is also a Codex plugin marketplace. Add it once, then install
the REL plugin:

```sh
codex plugin marketplace add https://github.com/rel-me/rel-tools.git --ref main
codex plugin add rel@rel
```

Start a new Codex task after installation. The plugin configures the bundled
`rel-mcp` adapter and adds guidance for safe use of persistent browser sessions.
REL.app must be installed in `/Applications`.

The same plugin is available through the repository's Claude Code marketplace:

```sh
claude plugin marketplace add rel-me/rel-tools
claude plugin install rel@rel
```

See the [Codex](docs/CODEX_PLUGIN.md) and
[Claude Code](docs/CLAUDE_CODE_PLUGIN.md) plugin guides for verification and
updates.

## Use the Rust client

Until a crates.io release is announced, pin the public repository tag:

```toml
[dependencies]
rel-client = { git = "https://github.com/rel-me/rel-tools", tag = "v0.1.1" }
```

```rust,no_run
use rel_client::RelClient;

let client = RelClient::local();
let status = client.status()?;
println!("{}", status.data.overall_status);
# Ok::<(), rel_client::ClientError>(())
```

See the [Rust SDK guide](docs/SDK.md) and [RPC v1 contract](docs/RPC.md).

## Use the Python crawler

The crawler is intended for interaction-heavy sites where each selected link
must be clicked in REL, captured, and followed by browser-history Back. Install
it from this repository and run the public Hacker News example:

```sh
cd crawler
python3 -m venv .venv
.venv/bin/python -m pip install -e .
HN_MAX_LINKS=3 .venv/bin/rel-crawler run examples/hackernews.py:app
```

See the [crawler guide](docs/CRAWLER.md) for named Profiles, readiness selectors,
rendered-link discovery, checkpoints, output metadata, retrying failed entries,
load-more sources, and recovery behavior.

## Port a Playwright scraper

The Python compatibility package keeps the common Playwright browser, page,
and CSS-locator shape while REL owns Chromium and its saved configuration:

```sh
cd playwright
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python examples/hackernews.py
```

Change imports from `playwright.sync_api` or `playwright.async_api` to the
corresponding `rel_playwright` module, then select a Profile at
`chromium.launch(profile="Research")`. See the
[Playwright compatibility guide](docs/PLAYWRIGHT.md) for supported methods and
explicit limits.

## Development

```sh
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace

cd crawler
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
cd ..

cd playwright
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
cd ..

cd docs
npm ci
npm run check
```

The source code in this repository is MIT licensed. REL.app and the REL brand
are not covered by that license.
