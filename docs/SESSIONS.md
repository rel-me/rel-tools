# Projects, Profiles and Sessions

A Project owns its Session membership, chat, actions, model preference and tab
order. Public session creation requires `project_id`. Current-page calls require
a Project or Session selector; the frontmost native window does not supply API
scope. Browser-state owners are private and cannot span Projects.

A Profile is a reusable configuration template. Every new `Session<number>` owns
independent browser state by default, even when created from the same Profile.
Shared state requires an explicit group choice at creation. Only explicitly
grouped Sessions share cookies, site data, configuration, browser identity and
routing. A Profile name or matching display name does not establish membership.

Use `POST /v1/sessions` with `project_id` and an optional Profile selection to
create an independent Session. To start an explicit shared set, supply `group_id:"new"`. To join one, supply
`project_id` and an existing `group_id` in that same Project. Public browser management uses
Session IDs. There are no public group resource or reset APIs.

`GET /v1/sessions` lists sessions; `GET /v1/sessions/{id}` reads one. Resources
include Project ownership and configuration metadata. `group_id` is present only
for explicitly shared state; an independent Session need not have one. Treat all
IDs as opaque and use the complete Session ID for browser operations. A missing
Session returns a structured error instead of selecting another tab.

Profile edits apply to future Sessions. Explicit configuration reapply uses
`POST /v1/sessions/{id}/reapply` with an optional `profile_id` and
`include_shared_sessions` when applying to an explicit shared set. It preserves
Session IDs, navigation and browser data. It does not reset cookies or reseed
Profile data. Closing the final Session removes its private state owner without
creating a replacement blank tab.

Browser fingerprint controls are scoped to that Session's state owner. Selecting
the `graphics` override without `device_surfaces` preserves native device memory
and storage-quota reporting in workers while applying the graphics policy.
With graphics selected, `canvas_noise_mode: "native"` preserves native 2D canvas
readbacks in windows and workers, including OffscreenCanvas. It does not disable
the WebGL profile, WebGL readback policy, or WebGPU policy. Use
`canvas_noise_mode: "deterministic"` to enable the Session's stable canvas noise.
These settings do not guarantee that a fingerprinting service assigns a new
visitor identity: other device signals can remain equal across independent
Sessions and proxy exits.

CLI, SDK and MCP adapters must be able to express the required scope. Inspect
the installed adapter's schema and use an explicit existing `session_id` when
appropriate. Do not send legacy group labels, infer membership from Profile
names or rely on obsolete reset helpers. If an adapter cannot express a required
Project/group selection, report that capability gap or use the supported
[RPC](RPC.md) request; do not invent compatibility behavior.

For a running or failed browser operation, use [browser diagnostics](BROWSER_DIAGNOSTICS.md)
before discarding its Session. Unknown cookie seed history, exit identity or
response provenance remains unknown; template reuse is not evidence of continuity.
