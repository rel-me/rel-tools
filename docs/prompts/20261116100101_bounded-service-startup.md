# Bounded service startup timeout documentation

The user reported a resolved REL.app proxy-list refresh failure with
“Resource temporarily unavailable (os error 35)” and requested that the UI handle
slow service startup on reboot without waiting too long for a genuine failure.

The implementation in rel-me/rel#891 normalizes request-read socket timeouts to
retryable TIMEOUT errors. Update the canonical RPC transport guide in the same
change to describe HTTP 504, TIMEOUT, and safe retry semantics.

Delegated to `monitor_startup_pr`: “Companion documentation PR is
https://github.com/rel-me/rel-tools/pull/262 at d94d64b, final documentation head.
Please monitor its checks too (documentation-only, no tests required locally),
and fix attributable failures if needed. Root REL implementation still
uncommitted; make dev-agent-open is running now. Do not change REL files until
root final-push signal.”

Follow-up: the final documentation head includes this delegated-prompt log;
recheck that head after its push and report required-check completion.

Follow-up delegated to `monitor_startup_pr`: “Reconsider the docs MSRV blocker:
if it can be fixed narrowly by explicitly selecting an already installed
compatible Xcode SDK in that CI job, preserving Rust 1.71.1 and all existing
coverage, please make that fix in docs PR #262, log this delegated prompt in its
existing docs/prompts file, validate the workflow, commit/push, and monitor the
new head again. Do not change global xcode-select, weaken checks, or change
toolchain versions. If a compatible SDK is unavailable or policy unclear, report
that exact blocker instead. REL PR #891 source/head must stay unchanged while
its current checks run.”
