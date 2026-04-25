# Tailscale Phone Access

Last verified: 2026-04-25

Phone acceptance: user confirmed the page is visible on a phone on 2026-04-25 after switching this route to static UI mode.

## URL

Open this URL on a phone that is logged in to the same Tailscale tailnet:

```text
https://yogas2.tail594315.ts.net:9447/
```

This is a Tailscale Serve entry, not a public Funnel entry.

## Current Route

```text
https://yogas2.tail594315.ts.net:9447/
  -> http://127.0.0.1:3100
```

Paperclip remains bound to loopback on the host. Tailscale terminates HTTPS on the tailnet side and proxies to the local service.

The Paperclip server is intentionally started in static UI mode for this phone route. Source-mode Vite middleware can load a black shell on mobile browsers through the Tailscale proxy because the page uses dev-only module paths such as `/@vite/client` and `/src/main.tsx`.

## Required Paperclip Host Allowlist

The Labebe demo instance must allow the Tailscale MagicDNS hostname:

```bash
pnpm paperclipai allowed-hostname yogas2.tail594315.ts.net \
  --config /vol1/1000/projects/toyresearch/.paperclip-labebe/instances/labebe-demo/config.json
```

Restart Paperclip after changing the allowlist.

## Verify

```bash
tailscale serve status
curl --noproxy '*' -k -fsS https://yogas2.tail594315.ts.net:9447/api/health
curl --noproxy '*' -k -fsS https://yogas2.tail594315.ts.net:9447/ | rg '@vite|/src/main|/assets/index'
```

Expected health result:

```json
{"status":"ok","version":"0.3.1","deploymentMode":"local_trusted","deploymentExposure":"private"}
```

The HTML check should show `/assets/index-*.js` and must not show `/@vite/client` or `/src/main.tsx`.

## If The Phone Shows A Black Screen

1. Force refresh the page, or open:

```text
https://yogas2.tail594315.ts.net:9447/?v=static-ui
```

2. If it still shows the old black page, clear the browser's website data for `yogas2.tail594315.ts.net` and open the URL again.

3. Confirm the server banner says `static-ui`, not `vite-dev-middleware`:

```bash
tmux capture-pane -pt paperclip-labebe-demo:0 -S -80 | rg 'static-ui|vite-dev-middleware'
```

## Disable

```bash
tailscale serve --https=9447 off
```
