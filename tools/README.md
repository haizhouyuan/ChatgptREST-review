# Tools

Small local helper scripts used during the Labebe research/demo work.

Tracked scripts:

- `minimax_video_i2v.py` submits and polls a MiniMax image-to-video task using
  `MINIMAX_API_KEY`.
- `xxd` is a minimal local shim for `xxd -r -p` in environments without the
  system binary.

Untracked local binaries:

- `cloudflared` is a downloaded executable and is intentionally ignored.

Do not commit API keys, downloaded vendor binaries, generated media, or local
runtime logs from this directory.
