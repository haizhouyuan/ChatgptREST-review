---
name: "paperclip-demo-operator"
description: >
  Use when operating the Labebe demo inside Paperclip: issue selection,
  heartbeat evidence, comments, status changes, local artifact paths, or demo
  replay. Do not use for product design reasoning itself.
metadata:
  paperclip:
    tags:
      - paperclip
      - operations
      - demo
---

# Paperclip Demo Operator

Paperclip is the control plane for this demo. It is not the source of truth for product claims.

## Runtime Contract

- Adapter: `process`
- Command: `/usr/bin/env python3 .../scripts/paperclip_demo_agent.py`
- Bind: `127.0.0.1:3100`
- Deployment: `local_trusted/private`
- External accounts: disabled
- Real credentials in portable config: forbidden

## Heartbeat Rules

1. Work from one assigned issue.
2. Write a local artifact to `outputs`.
3. Add a Paperclip comment or status update when API credentials are available.
4. If a gate is missing, mark blocked with the owner and exact unblock action.
5. Keep run evidence reproducible: artifact path, source labels, issue identifier, agent slug.

## Demo Replay Checklist

- Health endpoint is `ok`.
- Company is `Labebe AI Design Studio`.
- Agents are `process` adapter, not paid model adapters.
- Skills are installed in company library and listed in desired skills.
- MCP config exists as template and does not contain a raw API key.
- At least one end-to-end case issue has a succeeded heartbeat, generated artifact, and Paperclip comment.
