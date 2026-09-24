# Contributing

Issues and focused pull requests for the clients and public API documentation
are welcome. For security problems, follow [SECURITY.md](SECURITY.md) instead of
opening a public issue.

Before submitting a change, run:

```sh
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace

cd ruby
bundle install
bundle exec rake test
gem build rel-client.gemspec
cd ..

cd crawler
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
cd ..

# From the repository root:
python3 -m venv .venv
.venv/bin/python -m pip install -e playwright -e crawlee
.venv/bin/python -m unittest discover -s playwright/tests -v
.venv/bin/python -m unittest discover -s crawlee/tests -v

cd docs
npm ci
npm run check
```

API behavior is implemented by the proprietary REL.app runtime. Proposals for
new routes or runtime behavior may be discussed here, but the implementation is
not part of this repository.
