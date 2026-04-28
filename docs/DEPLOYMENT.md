# Deployment And External Access

Created: 2026-04-28

## Current DTC Website

Preferred external URL:

```text
https://yogas2.tail594315.ts.net:10000/
```

Local source:

```text
labebe-gemini-demo/
```

Build:

```bash
cd /vol1/1000/projects/toyresearch/labebe-gemini-demo
npm run build
```

Serve local SPA:

```bash
python3 /vol1/1000/projects/toyresearch/planning/20260427_labebe_14day_execution/work_products/runtime_qa_templates/spa_static_server.py \
  --directory /vol1/1000/projects/toyresearch/labebe-gemini-demo/dist \
  --host 0.0.0.0 \
  --port 8790
```

Expose through Tailscale Funnel:

```bash
bash /vol1/1000/home-yuanhaizhou/.codex-shared/skills/tailscale-external-deploy/scripts/publish_funnel.sh 8790 10000
```

Verify:

```bash
curl --noproxy '*' -L -s -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' \
  https://yogas2.tail594315.ts.net:10000/
```

Do not rely on:

```text
http://fnos.dandanbaba.xyz:8790/
```

That path goes through router/DDNS/firewall and may return `502` even when the
local app and Tailscale Funnel are healthy.

## Current Boss Gallery / Static Outputs

Static output server:

```bash
python3 -m http.server 8778 --bind 0.0.0.0 \
  --directory /vol1/1000/projects/toyresearch/paperclip_runtime_duel/outputs
```

Current URLs:

```text
http://fnos.dandanbaba.xyz:8778/boss_gallery_v0/index.html
http://fnos.dandanbaba.xyz:8778/labebe_site_walkthrough/labebe_dtc_site_walkthrough.mp4
```

## Tailscale Skill

Use:

```text
/vol1/1000/home-yuanhaizhou/.codex-shared/skills/tailscale-external-deploy/
```

Maint record:

```text
/vol1/maint/docs/2026-04-28_tailscale_external_deploy_skill_and_yogas2_port_map.md
```

Safety:

- Do not run `tailscale serve reset` or `tailscale funnel reset` casually.
- Do not overwrite `443`, `8443`, `9443-9447`, or `10000` without checking
  `tailscale serve status`.
- Use tailnet-only Serve for sensitive tools.
- Use public Funnel only for shareable demos.

