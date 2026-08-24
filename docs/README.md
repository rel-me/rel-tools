# REL documentation website

The public guides in this directory are the canonical source for the repository
and [docs.rel.me](https://docs.rel.me):

- `CLI.md` → `/cli/`
- `APP.md` → `/app/`
- `AI.md` → `/ai/`
- `ACTIONS.md` → `/actions/`
- `CODEX_PLUGIN.md` → `/codex-plugin/`
- `CLAUDE_CODE_PLUGIN.md` → `/claude-code-plugin/`
- `MCP.md` → `/mcp/`
- `RPC.md` → `/rpc/`
- `SDK.md` → `/sdk/`
- `CRAWLER.md` → `/crawler/`
- `PLAYWRIGHT.md` → `/playwright/`

Edit those source files, not the generated guide files under
`src/content/docs/`. `scripts/sync-docs.mjs` prepares the Markdown for
Starlight before each build.

## Local development

```sh
npm ci
npm run dev
```

Validate the production build and internal links with:

```sh
npm run check
```

CI validates every documentation change. Production deployment is managed by
the proprietary product repository so Cloudflare credentials remain private;
it builds this repository's `main` branch as the canonical source.
