---
description: How to observe the ChatGPT/Gemini/Qwen driver browser via CDP for debugging and UI inspection
---

# /observe-driver — CDP Driver Browser Observation

Use this workflow when you need to see what the driver browser is doing — e.g., debugging answer extraction issues, investigating new UI behavior, or capturing evidence of driver errors.

## Port Mapping

| Port | Browser | Usage |
|------|---------|-------|
| `9222` | User's Chrome | Connected by `chrome-devtools` MCP. **Do NOT use for driver observation** |
| `9226` | ChatGPT driver | ChatGPT Web UI automation |
| `9335` | Qwen driver | Qwen Web UI automation |

## Steps

// turbo-all

### 1. List open pages in the driver browser

```bash
timeout 5 curl -s --connect-timeout 2 http://127.0.0.1:9226/json/list | python3 -c "
import sys,json
for p in json.load(sys.stdin):
    print(f'id={p[\"id\"]}  title={p.get(\"title\",\"\")[:60]}  url={p.get(\"url\",\"\")[:80]}')
"
```

Replace `9226` with `9335` for Qwen driver.

### 2. Take a screenshot of a specific page

```bash
cd /vol1/1000/projects/ChatgptREST && timeout 15 .venv/bin/python3 -c "
import asyncio, json, base64, websockets

async def main():
    ws_url = 'ws://127.0.0.1:9226/devtools/page/{TARGET_ID}'
    async with websockets.connect(ws_url, max_size=20*1024*1024) as ws:
        await ws.send(json.dumps({'id': 1, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
        resp = json.loads(await ws.recv())
        data = resp.get('result', {}).get('data', '')
        if data:
            img = base64.b64decode(data)
            path = '/tmp/driver_screenshot.png'
            with open(path, 'wb') as f:
                f.write(img)
            print(f'Screenshot saved: {path} ({len(img)} bytes)')

asyncio.run(main())
"
```

Replace `{TARGET_ID}` with the page ID from step 1.

### 3. View the screenshot

Use `view_file /tmp/driver_screenshot.png` to see the screenshot.

### 4. Get page DOM (optional, for element inspection)

```bash
cd /vol1/1000/projects/ChatgptREST && timeout 15 .venv/bin/python3 -c "
import asyncio, json, websockets

async def main():
    ws_url = 'ws://127.0.0.1:9226/devtools/page/{TARGET_ID}'
    async with websockets.connect(ws_url, max_size=20*1024*1024) as ws:
        # Evaluate JS to get specific elements
        await ws.send(json.dumps({
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {'expression': 'document.querySelector(\"[data-testid=stop-button]\")?.outerHTML || \"not found\"'}
        }))
        resp = json.loads(await ws.recv())
        val = resp.get('result', {}).get('result', {}).get('value', '')
        print(val[:500])

asyncio.run(main())
"
```

## Time-series Observation

For tracking UI changes over time (e.g., during Pro Extended thinking):

1. Submit a job via the repo wrapper or public REST surface. Do not hard-code legacy MCP bare tool names.
2. Wait ~60s for the job to start processing
3. Take screenshots at intervals: `sleep 5 && <screenshot script>`
4. Compare screenshots to understand the generation lifecycle

Example:

```bash
/usr/bin/python3 skills-src/chatgptrest-call/scripts/chatgptrest_call.py \
  --provider chatgpt \
  --preset pro_extended \
  --idempotency-key observe-driver-001 \
  --question "Analyze this issue and explain what the model is thinking through." \
  --out-answer /tmp/observe-driver-answer.md
```

## Common Selectors to Check

| Element | Selector |
|---------|----------|
| Stop button | `button[data-testid='stop-button']` |
| Assistant messages | `[data-message-author-role='assistant']` |
| Canvas panel | `[data-testid='canvas-panel']` |
| Composer | `#prompt-textarea` |

## Troubleshooting

- **Connection refused**: driver not running → `systemctl --user status chatgptrest-driver.service`
- **Empty page list**: driver just started, no tabs open yet → wait and retry
- **`websockets` not found**: use `.venv/bin/python3` (project venv has it)
