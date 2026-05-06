# Issue 157 Inline Answer Result Fix Todo v1

## Working Memory

- Branch: `fix/issue157-inline-answer`
- Issue: `#157`
- Scope: MCP result retrieval layer only
- Guardrail: do not touch unrelated dirty state in the main worktree

## Todo

- [x] Isolate work in a clean worktree and branch
- [x] Read issue `#157` and confirm symptom/root cause
- [x] Run GitNexus impact analysis before editing touched symbols
- [x] Write versioned design doc
- [ ] Implement shared answer-payload normalization for current chunked contract
- [ ] Update `chatgptrest_result()` to use normalized answer payloads
- [ ] Update answer prefetch cache to use the same normalization
- [ ] Add regression tests for direct fetch path
- [ ] Add regression tests for prefetch cache path
- [ ] Run focused pytest
- [ ] Run `gitnexus_detect_changes()`
- [ ] Write versioned walkthrough doc
- [ ] Push branch and open PR
- [ ] Run repo closeout workflow

## Notes

- Current root cause: MCP reads `/answer` as `{content,total_bytes,length}` but REST returns `{chunk,returned_chars,next_offset,done}`.
- The fix should be backward compatible with legacy answer payloads.
- Keep commits small and meaningful.
