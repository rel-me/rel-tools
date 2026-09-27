# CI on the Mac mini

All seven CI jobs run on the repository-scoped `rel-tools-mac-mini` runner,
using `[self-hosted, macOS, ARM64, rel-tools-ci]`. There are no GitHub-hosted
runner jobs. Rust stable, Rust 1.71.1, Ruby 3.1, Python 3.11/3.13, and Node 24
checks are retained; the former Linux jobs now validate on macOS ARM64.

CI runs for pull requests and pushes to `main`. Branch pushes do not duplicate
PR validation. New commits cancel superseded runs for the same PR or branch,
and each job has a 20-minute timeout. One runner executes these jobs serially.

## Host setup

The service lives at `/Users/local/actions-runner-rel-tools` on
`local@locals-Mac-mini-2.local`. It has its own `_work` directory and launch
service, separate from the existing REL and Fritz runners. The `local` account
must remain signed in for the LaunchAgent to run.

```sh
cd /Users/local/actions-runner-rel-tools
./svc.sh status
```

The host requires Xcode command-line tools and mise at `/opt/homebrew/bin/mise`.
Mise supplies Ruby 3.1 and Python 3.11/3.13. Ruby 3.1 builds apply the pinned
[upstream socket SDK header fix](https://github.com/ruby/ruby/commit/cb18deee7285dde67102c9702796d7eba0046af5),
which is needed on modern Xcode. Setup verifies socket and OpenSSL extensions
before testing. The Node setup action installs Node
24 into the runner's tool cache. Rust setup uses runner-local Cargo and rustup
homes under `$RUNNER_TOOL_CACHE`; it does not change the host's Rust default or
shell profiles. Each Python job creates a fresh virtual environment under
`$RUNNER_TEMP`, and Ruby installs its bundle there too. The runner cleans its
temporary directory between jobs. Downloaded toolchains and normal package
manager download caches persist locally instead of using Actions cache storage.

## Public repository access

The repository's **Approval for running fork pull request workflows from
contributors** setting must remain **Require approval for all external
contributors** (`all_external_contributors`). This setting was enabled when
the runner was provisioned. Review every fork's workflow and executable changes
before approval: approved jobs run as the Mac mini's `local` user and can access
that user's files. The runner's separate work directory is not a security
sandbox. Do not approve untrusted code to run on this host.

Workflow token permissions are read-only, and checkout does not persist its
GitHub token in the working copy.

## Validation

Validate workflow changes with `actionlint`; `.github/actionlint.yaml` declares
the custom runner label:

```sh
actionlint .github/workflows/ci.yml
```

Run the affected job commands on the mini in a separate verification checkout
before publishing workflow changes. CI does not require opening the REL app;
the Python and Ruby suites use local test fixtures.
