# Tailscale Phone Access

Last verified: 2026-04-25

Phone acceptance: user confirmed the page is visible on a phone on 2026-04-25 after switching this route to static UI mode.

Use this URL from a phone logged in to the same Tailscale tailnet:

```text
https://yogas2.tail594315.ts.net:9447/
```

Route:

```text
Tailscale Serve HTTPS 9447 -> http://127.0.0.1:3100
```

This route is tailnet-only. It is not enabled as Tailscale Funnel/public internet access.
The demo should be started in static UI mode for phone access. Avoid source-mode Vite middleware on this route because mobile browsers can display a black shell when dev-only module paths are used through the Tailscale proxy.

Required Paperclip hostname allowlist:

```bash
pnpm paperclipai allowed-hostname yogas2.tail594315.ts.net \
  --config /vol1/1000/projects/toyresearch/.paperclip-labebe/instances/labebe-demo/config.json
```

Verification:

```bash
tailscale serve status
curl --noproxy '*' -k -fsS https://yogas2.tail594315.ts.net:9447/api/health
curl --noproxy '*' -k -fsS https://yogas2.tail594315.ts.net:9447/ | rg '@vite|/src/main|/assets/index'
```

Expected HTML: `/assets/index-*.js` is present, `/@vite/client` and `/src/main.tsx` are absent.

If a phone still shows a black screen after the static UI restart, force refresh or open:

```text
https://yogas2.tail594315.ts.net:9447/?v=static-ui
```

If needed, clear browser website data for `yogas2.tail594315.ts.net`.

Disable:

```bash
tailscale serve --https=9447 off
```
