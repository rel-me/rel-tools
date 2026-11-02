# Session bridge recovery diagnostics

User request: Creating a Session with no proxy times out in running REL.app. Find the stalled preparation step and fix it.

Document the preparation-stage trace events and the recovery behavior implemented by rel-me/rel PR #879. The prompt-only investigation PR #878 was merged while implementation verification was in progress. Session persistence can precede acknowledgement failure; preserve available diagnostics and list Sessions before retrying. No delegated implementation prompts.
