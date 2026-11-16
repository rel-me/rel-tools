# Bounded service startup timeout documentation

The user reported a resolved REL.app proxy-list refresh failure with
“Resource temporarily unavailable (os error 35)” and requested that the UI handle
slow service startup on reboot without waiting too long for a genuine failure.

The implementation in rel-me/rel#891 normalizes request-read socket timeouts to
retryable TIMEOUT errors. Update the canonical RPC transport guide in the same
change to describe HTTP 504, TIMEOUT, and safe retry semantics.

No delegated prompts for this documentation change.
