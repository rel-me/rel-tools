# User request

> Lemonsqueezy is shutting down.. we don't have any paying customers, so lets swap it out for an alternative. Let's use stripe managed platforms and handle license keys ourself.

Companion public guide update for rel-me/rel#893. Document REL license delivery,
two-Mac activation, and Stripe Managed Payments billing through Link.

No delegated implementation prompts for this guide update.


## Follow-up: repair MSRV CI (2026-11-17)

User request:

> Review github.com/rel-me/rel-tools PR 263 (codex/gabriel/stripe-managed-licensing -> main) and make the smallest safe fix for the attached failing CI. Locate its repository and checkout before making changes. Use gh with --repo github.com/rel-me/rel-tools to inspect latest runs, annotations, and logs before changing code. Do not guess or refactor unrelated code. Run the narrowest verification, commit, push, and summarize the root cause, fix, and result.

Attached run: 43984174963, MSRV job 133708100620. GitHub logs show Rust
1.71.1 dependency build scripts link against the Command Line Tools macOS27.2
SDK, whose arm64e.x1 text stubs are unsupported by the active Xcode linker.
Select the active Xcode macOS SDK explicitly for the existing MSRV check;
keep Rust1.71.1 and the same workspace/all-targets coverage.

Delegated monitoring prompt:

> Monitor rel-me/rel-tools PR263 (codex/gabriel/stripe-managed-licensing) after the MSRV SDK-selection fix is pushed. Use gh --repo github.com/rel-me/rel-tools on supported commands to inspect latest runs/checks/logs and wait for terminal results on the exact pushed head. Diagnose any failure from logs and coordinate minimal fixes with root before editing. Do not alter Rust version, dependency requirements, or test coverage to bypass the failure. The patch only sets SDKROOT from /usr/bin/xcrun --sdk macosx --show-sdk-path before cargo check --workspace --all-targets. Root owns the checkout /Users/local/.codex/worktrees/stripe-msrv-ci/rel-tools and is running local Rust1.71.1 verification. Do not change files or commit while root verifies.
