# Browser actions

REL uses one browser-action contract across the CLI, MCP server, RPC v1, and
Rust SDK. Actions are JSON objects with an `action` discriminator. Arrays run
in order and stop at the first failure.

## Where actions are accepted

| Surface | Multiple actions | One action |
| --- | --- | --- |
| CLI | `rel perform ACTIONS`, `rel capture URL --actions JSON` | Repeat `--action JSON`, or use `rel page action PAGE_ID --action JSON` |
| MCP | `rel_capture.actions` | `rel_page_action.action` |
| RPC v1 | `POST /v1/perform`, `POST /v1/captures` | `POST /v1/pages/{page_id}/actions` |
| Rust SDK | `PerformRequest.actions`, `CaptureRequest.actions` | `PageActionRequest.action` |

The same object shapes and validation rules apply on every surface. The CLI and
MCP server forward actions through RPC v1; neither has a separate browser
implementation.

## Quick reference

| Action | Required fields | Purpose |
| --- | --- | --- |
| `click` | `selector` | Click the first matching element. |
| `wait-for` | `selector`; optional positive `timeout` | Wait until a matching element is present. |
| `type` | `selector`, nonempty `text` | Append text to an editable control. |
| `fill` | `selector`, `text` | Replace an editable control's contents. |
| `clear` | `selector` | Remove an editable control's contents. |
| `press` | `selector`, `key` | Send one supported named key to a control. |
| `select` | `selector`, `value` | Select one enabled option by exact value. |
| `wait` | nonnegative `seconds` | Pause action execution for a bounded duration. |
| `click-link` | `link`, `match` | Click an anchor by resolved HTTP(S) URL. |

## JSON objects

```json
{ "action": "click", "selector": "button.more" }
{ "action": "click", "selector": "button.more", "mouse_move": false, "scroll": false }
{ "action": "wait-for", "selector": "#loaded-content", "timeout": 10 }
{ "action": "type", "selector": "#search", "text": "Magickraft" }
{ "action": "fill", "selector": "#email", "text": "listener@example.com" }
{ "action": "clear", "selector": "#query" }
{ "action": "press", "selector": "#search", "key": "Enter" }
{ "action": "select", "selector": "#genre", "value": "disco" }
{ "action": "wait", "seconds": 0.5 }
{
  "action": "click-link",
  "link": "https://example.com/more",
  "match": { "type": "fuzzy-link", "threshold": 0.9 }
}
```

Function-style strings and legacy object shapes are rejected. Action objects
are closed contracts: fields not listed for that action are rejected by the
agent.

## Selectors

Selector actions use CEF's read-only renderer DOM snapshot. Supported selectors
are comma-separated lists composed of tag, universal, ID, class, presence or
value attribute selectors, plus descendant, child (`>`), adjacent-sibling
(`+`), and general-sibling (`~`) combinators. Pseudo-classes, pseudo-elements,
namespaces, and CSS escapes are rejected.

`wait-for` checks only for presence and does not require layout bounds. Its
optional positive `timeout` is measured from the start of that action and is
capped by the enclosing operation's remaining deadline. Omitting it preserves
the enclosing deadline. If its own timeout expires first, REL returns
`ACTION_TIMEOUT`; if the enclosing deadline expires first, REL returns
`TIMEOUT`. `click` reads the first match's bounds and dispatches CEF mouse
input. A missing click target returns
`ACTION_TARGET_NOT_FOUND` without polling, so put `wait-for` immediately before
`click` when a page renders the target asynchronously.

## Click behavior

`click` and `click-link` accept two optional booleans:

| Field | Default | Behavior |
| --- | --- | --- |
| `mouse_move` | `true` | Send a Chromium-local mouse-move event before button-down and button-up. |
| `scroll` | `true` | Use bounded Chromium wheel input and re-read bounds until an offscreen target is visible. |

Setting `mouse_move` to `false` sends only button-down and button-up. Neither
mode moves the macOS cursor. Setting `scroll` to `false` requires the target to
already be visible.

`click-link` resolves anchor `href` values in the same read-only snapshot,
normalizes the requested HTTP(S) URL, and applies its `fuzzy-link` threshold.
The threshold must be between `0` and `1`; `1` requires an exact normalized URL
match.

Click targeting and dispatch never execute page JavaScript, mutate the DOM,
invoke accessibility activation, or use Chrome DevTools Protocol. Missing,
unreachable, and unsupported targets fail without a fallback.

## Text, keys, and selects

`type` focuses an editable control and appends nonempty text. `fill` replaces
the current contents and permits an empty string. `clear` is the explicit
emptying form. Text actions reject missing, disabled, read-only, or non-editable
targets.

`press` focuses its target and accepts exactly these named keys:

```text
Enter Tab Escape Backspace Delete
ArrowUp ArrowDown ArrowLeft ArrowRight
Home End PageUp PageDown Space
```

`select` targets a `<select>` element and chooses one enabled `<option>` by its
exact `value`. Form updates dispatch ordinary DOM events so page state remains
synchronized. These actions use fixed renderer operations and never accept
caller-supplied JavaScript.

## CLI examples

Pass an ordered array to `perform`:

```sh
rel perform '[
  {"action":"wait-for","selector":"#disco_search","timeout":10},
  {"action":"fill","selector":"#disco_search","text":"Magickraft"},
  {"action":"press","selector":"#disco_search","key":"Enter"}
]'
```

For URL capture, repeat `--action` or pass an array with `--actions`. The two
options may be combined and preserve command-line order:

```sh
rel https://example.com \
  --action '{"action":"wait-for","selector":"#disco_search","timeout":10}' \
  --actions '[{"action":"type","selector":"#disco_search","text":"Magickraft"}]'
```

## MCP examples

`rel_capture` accepts the same ordered array:

```json
{
  "url": "https://example.com",
  "actions": [
    { "action": "fill", "selector": "#disco_search", "text": "Magickraft" },
    { "action": "press", "selector": "#disco_search", "key": "Enter" }
  ]
}
```

`rel_page_action` accepts one of the same objects in its `action` field. MCP's
input schemas enumerate all nine action kinds and forward the validated objects
through the corresponding RPC operations.

## RPC examples

`POST /v1/perform` and `POST /v1/captures` accept an `actions` array.
`POST /v1/pages/{page_id}/actions` accepts one object under `action`:

```json
{
  "action": { "action": "select", "selector": "#genre", "value": "disco" },
  "timeout": 90,
  "wait": 1
}
```

The agent validates every object before sending it through the private Chromium
bridge. A page action remains pinned to the page, session, URL, and proxy chosen
when that page was attached.

## Rust SDK

The public `Action` enum serializes directly to the JSON objects above:

```rust
use rel_client::{Action, FuzzyLinkMatch};

let actions = vec![
    Action::WaitFor {
        selector: "#disco_search".into(),
        timeout: Some(10.0),
    },
    Action::Fill {
        selector: "#disco_search".into(),
        text: "Magickraft".into(),
    },
    Action::Press {
        selector: "#disco_search".into(),
        key: "Enter".into(),
    },
    Action::ClickLink {
        link: "https://example.com/more".into(),
        match_rule: FuzzyLinkMatch::new(0.9),
        mouse_move: None,
        scroll: None,
    },
];
```

`None` uses the default `true` behavior for `mouse_move` and `scroll`; use
`Some(false)` to disable either behavior.

## Viewport and failures

Browser sessions controlled while not visible use the **Background Browser
Size** preset in **REL → Settings… → General**, which defaults to 1,920 × 947
CSS pixels. Visible tabs follow the resizable REL window. The viewport is a
global app setting rather than an action field.

Actions stop at the first failure and return the standard structured RPC error.
No action falls back to a different element, alternate browser backend, page
script, or undocumented compatibility shape.
