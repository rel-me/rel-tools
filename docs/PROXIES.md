# Configure proxies

Give each REL browser Session its own proxy configuration. For example, keep one
Session on an Oxylabs proxy, another on a Bright Data proxy, and a third on a
direct connection. Selecting a proxy routes that Session's browser traffic
through it; other Sessions keep their own assignments.

Proxy creation, configuration, assignment, rotation, and use require **REL Pro**.
Have your provider's proxy endpoint, port, username, and password ready. Use the
proxy credentials from its dashboard, which may differ from your account login.

## Add a proxy

1. Open **REL → Settings… → Proxies** and choose **Add Proxy**.
2. Choose a **Type**. Provider presets fill the endpoint and port. Use **Custom**
   for another HTTP proxy or an endpoint supplied by your provider.
3. Enter a unique **Alias**, such as `research-us` or `research-de`. REL uses this
   alias in the Session picker, CLI, and MCP tools. It cannot be renamed after
   creation.
4. Enter the **Username** and **Password**, and review the endpoint and port.
5. If the selected type offers location targeting, choose the location you need.
6. Review **Detect Exit Locale** and **HTTPS Certificates** below, then choose
   **Add Proxy**.

These are the endpoint defaults supplied by REL's presets. Use the endpoint and
credentials appropriate to your provider account and product.

| Type | Default host | Default port |
| --- | --- | --- |
| Oxylabs Residential | `pr.oxylabs.io` | `7777` |
| Oxylabs Datacenter | `dc.oxylabs.io` | `8000` |
| Oxylabs ISP | `isp.oxylabs.io` | `8001` |
| Bright Data | `brd.superproxy.io` | `44445` |
| Decodo Residential | `gate.decodo.com` | `7000` |
| IPRoyal Residential | `geo.iproyal.com` | `12321` |
| Custom | Enter your provider's HTTP proxy host | Enter its port |

For Oxylabs Residential or Datacenter, the editor offers **Location** targeting.
For Bright Data, enter the proxy username in the `brd-customer-…-zone-…` form;
the editor offers **Country**, **State**, **City**, and **ASN** fields. Bright Data
Sessions receive their own persistent provider session IDs.

Credentials stay in REL's secure credential storage. MCP's proxy-list tool
returns aliases and non-secret metadata, not stored passwords.

## Assign a proxy to a Session

Open a browser Session and use the toolbar's **Proxy** menu to select the saved
alias. Choose **None** for a direct connection. Repeat in another Session to
assign a different proxy. Adding a proxy in Settings does not assign it to every
Session.

When REL shows **Browser configuration changed. Reload to apply.**, choose
**Reload** when ready. Session cookies and storage are preserved. Existing
connections can continue on their old route until they close; verify the exit
IP after applying the change.

To create a Session with a proxy already selected, open **File → Create Session
from Profile** and choose its **Proxy**. **New Proxy…** opens the proxy editor
without discarding your Session draft. A saved Profile can also carry a proxy
assignment for future Sessions.

For details about when settings apply, see
[browser configuration changes](APP.md#browser-configuration-changes).

## Use a configured proxy from Codex

[Install the REL Codex plugin](CODEX_PLUGIN.md), configure the proxy in REL, and
start a new Codex chat. Refer to the saved alias rather than putting credentials
in your prompt:

```text
Use REL to list my configured proxy aliases. Open https://example.com in a new
Session using the research-us proxy, and summarize the page.
```

For an existing Session, identify it explicitly:

```text
Use REL Session123 to read its current page. Keep its existing proxy assignment.
```

The plugin can list configured aliases with `rel_list_proxies` and select a
proxy through the `proxy` input on URL-reading, capture, navigation, and
page-attachment tools. Configure new proxies in the app or through the CLI;
MCP does not provide proxy creation or credential editing.

See [MCP tool inputs](MCP.md#tools) for the supported operations.

## Use a proxy from the CLI

List configured aliases, then capture a URL through one:

```sh
rel proxy list
rel https://example.com/ --proxy research-us
```

For an existing Session, specify its ID to avoid creating another Session:

```sh
rel https://example.com/ --session-id Session123 --proxy research-us
```

An explicit proxy updates the reused Session's assignment. Omitting `--proxy`
keeps an existing Session's assignment. See the [CLI proxy reference](CLI.md#proxies)
for creating, editing, and transferring configurations.

## Timezone detection and browser identity

A proxy changes the Session's network route. Its exit IP and the timezone
reported by browser JavaScript are separate settings.

### Detect the proxy exit timezone automatically

1. Open **REL → Settings… → Proxies**, edit the proxy, and enable
   **Detect Exit Locale**. Existing detection choices are preserved; new proxies
   start with detection off.
2. Assign the proxy to the Session. Use **Private** browser identity, which
   enables the timezone control, or enable **Timezone** in **Custom Privacy**.
3. Save and apply any pending **Reload** banner.

REL requests the exit country and IANA timezone through that Session's proxy
using IPWHOIS.io before preparing the browser. For example, if the saved
identity uses `America/Los_Angeles` but the proxy exits in New York, websites
see `America/New_York`. Successful results are cached for up to 30 minutes per
Session and upstream route; provider session rotation changes that route.
Lookup failures report an error instead of silently using a different location.

Timezone detection works independently of language: **Custom** language keeps
its explicit locale while the enabled Timezone control uses the detected
zone. With Timezone disabled, Chromium keeps its native timezone.
Detection changes the effective browser identity without overwriting the saved
manual timezone or your Mac's system timezone.

### Set a timezone manually

Turn **Detect Exit Locale** off for the proxy to use the saved identity timezone.
To align it with the proxy location:

1. Check the proxy's actual exit location using an IP-check page in that Session.
   Use the exit location rather than assuming the provider's requested country
   determines a single timezone.
2. Open the Session's tab menu and edit its **Browser Identity**. Choose
   **New Browser Identity…** to customize it, or **Edit** beside **Custom Privacy**
   in a Profile or Session draft.
3. In **Custom Privacy**, enable **Timezone** and enter an IANA timezone name,
   such as `America/New_York` or `Europe/Berlin`.
4. Choose **Use Identity**, save the configuration, and apply any pending
   **Reload** banner.

Saved Profile edits apply to future Sessions; edit an existing Session's identity
to change that Session. If a rotating proxy moves to another timezone, review
the manual setting again.

### Verify the timezone

Open a timezone-check page in the Session and compare the browser timezone with
the proxy exit location. For a page you control, this JavaScript reads the
browser's effective timezone:

```js
Intl.DateTimeFormat().resolvedOptions().timeZone
```

See [browser identity](APP.md#browser-identity) for the other privacy controls.

## Exit country and certificate settings

When **Detect Exit Locale** and Automatic language are enabled, REL looks up
the exit country through the Session's proxy using IPWHOIS.io. Successful
results are cached for up to 30 minutes per Session and upstream route. The
service sees the proxy's exit IP. A failed lookup reports an error.
Turn detection off to use the configured location for Automatic language;
custom language settings take priority.

Under **HTTPS Certificates → Trust**, use **System trust** for ordinary proxy
connections. The Bright Data preset selects **Bright Data certificate** for
`brd.superproxy.io:44445`. Use **Custom certificate** only when your proxy
requires its own CA certificate. Additional roots apply only to REL Sessions
assigned to that proxy and allow the provider to inspect their HTTPS traffic.
REL continues checking hostnames, expiry dates, and certificate chains.
See [proxy certificate trust](APP.md#proxy-certificate-trust).

## Verify and troubleshoot

Open an IP-check page in each Session and compare the reported exit IP and
location with the proxy assignment. A persistent browser Session does not itself
guarantee a fixed exit IP; that also depends on the provider's product and
sticky-session settings.

If a page fails to load:

- Confirm the alias selected in that Session's **Proxy** menu.
- Review the host, port, proxy credentials, and permitted targeting in your
  provider dashboard.
- Apply any pending **Reload** banner before checking again.
- For certificate errors, review the proxy's trust setting and provider CA.
- Read the page error and REL's Logs for provider diagnostics. Exit-locale lookup
  errors can also prevent browser preparation when detection is enabled.

To import a provider's HTTP proxy curl example, use **Import Proxy** in Proxies
Settings. REL parses the command without executing it, opens the populated
editor for review, and requires saving before creating the proxy. Review the
alias and certificate settings before saving. See
[proxy curl import](APP.md#proxies-curl-command).
