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
| Oxylabs ISP | `disp.oxylabs.io` | `8001` |
| Bright Data | `brd.superproxy.io` | `44445` |
| Decodo Residential | `gate.decodo.com` | `7000` |
| IPRoyal Residential | `geo.iproyal.com` | `12321` |
| Custom | Enter your provider's HTTP proxy host | Enter its port |

For **Oxylabs ISP**, enter **Available IPs** and the first assigned upstream
port. For example, 5 IPs starting at port 8001 use ports 8001 through 8005.
REL keeps each browser session on its assigned port, choosing the least-used
port for new sessions and sharing ports once all IPs are in use. **Rotate Proxy
Session** advances to the next port, wrapping to the first port at the end.
A single-IP pool retains its IP. Existing `isp.oxylabs.io` configurations keep
their gateway when edited. ISP credentials use `user-USERNAME`; REL does not
append session IDs or location parameters. See the [API fields](RPC.md#proxies).

For Oxylabs Residential or Datacenter, the editor offers **Location** targeting.
For Bright Data, enter the proxy username in the `brd-customer-…-zone-…` form;
the editor offers **Country**, **State**, **City**, and **ASN** fields. Bright Data
Sessions receive their own persistent provider session IDs.

Credentials stay in REL's secure credential storage. MCP's proxy-list tool
returns aliases and non-secret metadata, not stored passwords.

## Test a saved proxy

Select a proxy in **Settings → Proxies**, then choose **Test**, or right-click
its row and choose **Test**. The **Proxy Test** sheet runs automatically and
supports **Run Tests** to repeat the suite.

The suite checks upstream DNS and TCP connectivity, HTTP forwarding,
authenticated HTTPS with system and proxy-specific certificate trust, exit IP,
country and IANA timezone, country targeting, and the **Detect Exit Locale**
setting. It uses the saved configuration and a fresh provider sticky session,
and sends requests through the proxy to example.com and IPWHOIS.io. It does not
change existing browser Sessions or expose saved credentials.

Results show passed, failed, warning, or skipped checks and elapsed time.
A failed destination request can also indicate an unavailable test service.
A country mismatch or disabled exit-locale detection is a warning. Browser
fingerprint timezone overrides, DNS/WebRTC leak behavior, and MASQUE/UDP need
browser-session verification and are explicitly marked untested by this suite.

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

### HTTP/3 and MASQUE

The Oxylabs Residential proxy editor has a **MASQUE (HTTP/3)** checkbox.
The masked connection string updates immediately: enabled shows
`https://…@masque.oxylabs.io:50000`; disabled shows the configured HTTP upstream,
normally `http://…@pr.oxylabs.io:7777`. The MASQUE URL describes the HTTP/3
connection and requires a MASQUE-capable client.

New Oxylabs configurations default to MASQUE enabled when the setting is omitted.
An explicit `oxylabs_masque_enabled: false` disables it, including for residential
proxies. The saved choice survives unrelated edits, restart, and transfers.
After saving, open pages show a configuration banner; choose **Reload** to apply
the changed transport.

Keep the TCP upstream set to `pr.oxylabs.io:7777` with the Oxylabs provider enabled.
REL sends UDP traffic through `masque.oxylabs.io:50000` using authenticated HTTP/3
CONNECT-UDP. TCP traffic continues through the configured HTTP proxy. Both
transports use the same Rust-owned credentials, location parameters, and
per-session sticky ID. Existing session IDs and credentials are preserved.
Datacenter, ISP, and custom upstreams retain their configured transport settings.
Disabling the Oxylabs provider disables MASQUE. Outbound UDP must be available
for HTTP/3; REL reports transport errors when it is blocked.

Each browser session connects to its own trusted loopback HTTP/3 relay. Rust
verifies Oxylabs TLS, adds Proxy-Authorization, and forwards datagrams and
RFC 9297 capsules. CEF receives only the loopback address and session CA,
never provider credentials. Proxy-session rotation and deletion close the
session's QUIC tunnels. Target names are passed to Oxylabs without local DNS
resolution. WebRTC's non-proxied UDP remains disabled.

Origin HTTP/3 still depends on the site's advertised support. HTTPS sites
without HTTP/3 use their normal TCP tunnel through the configured proxy.
Provider authentication, certificate, timeout, or UDP failures are reported as
proxy errors; REL never sends UDP directly to the origin. Oxylabs restricts
some UDP targets, including Google. Live provider connectivity requires
UDP port 50000 to be reachable from your network.

The session's **Logs** panel records MASQUE listener and tunnel setup stages,
CONNECT versus CONNECT-UDP routing, upstream response statuses, elapsed times,
and redacted provider rejection details. Search for `MASQUE` to trace a tunnel
by its connection/stream ID. Oxylabs `X-Error-Description` diagnostics are retained;
credentials, cookies, arbitrary response headers, and page contents are excluded.
