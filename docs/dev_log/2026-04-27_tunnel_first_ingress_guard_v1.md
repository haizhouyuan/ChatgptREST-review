# 2026-04-27 Tunnel-First Ingress Guard v1

## Decision

ChatgptREST should not be operated as a public HTTP service. The supported access mode is tunnel-first:

- local process access on `127.0.0.1`
- SSH local port forwarding
- Tailscale / private-network access

Public reverse proxies may continue to exist on the same host for unrelated websites, but they must not expose ChatgptREST API or MCP paths.

## Why

The post-incident review showed public scanner traffic reaching the host while ChatgptREST itself was correctly bound to loopback. That means the weak point was not the FastAPI bind address but the host ingress layer. Application auth is necessary, but it is not the right first boundary for an automation control plane.

## Implemented Control

`chatgptrest/api/app.py` now includes a public-ingress middleware. By default:

```text
CHATGPTREST_REJECT_PUBLIC_INGRESS=1
```

If the real client IP is public/global, the API returns:

```json
{
  "detail": {
    "error": "public_ingress_blocked",
    "error_type": "PublicIngressBlocked",
    "reason": "chatgptrest_is_tunnel_first"
  }
}
```

The rejection is also written to:

```text
artifacts/monitor/api_rejections/YYYYMMDD.jsonl
```

Allowed by default:

- loopback
- private networks
- link-local and reserved ranges
- Tailscale / CGNAT `100.64.0.0/10`

Temporary exception:

```text
CHATGPTREST_PUBLIC_INGRESS_ALLOW_CIDRS=<cidr-list>
```

This should only be used for short-lived fixed admin IP exceptions.

## Tunnel Command

From the client machine:

```bash
ssh -N \
  -L 18711:127.0.0.1:18711 \
  -L 18712:127.0.0.1:18712 \
  <user>@<host>
```

Then point clients at:

- REST: `http://127.0.0.1:18711`
- MCP: `http://127.0.0.1:18712/mcp`

## Residual Work

The application guard is defense in depth. The host-level ingress should still be cleaned up separately:

1. Remove any nginx route that proxies ChatgptREST API/MCP paths from public listeners.
2. Keep unrelated public static sites separate from ChatgptREST.
3. Prefer firewall rules that only expose SSH/Tailscale and required public websites.
