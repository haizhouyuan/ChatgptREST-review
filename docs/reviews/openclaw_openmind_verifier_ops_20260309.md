# OpenClaw + OpenMind Verification Report

- Timestamp UTC: `2026-03-09T14:07:07.299581+00:00`
- OpenClaw bin: `/vol1/1000/home-yuanhaizhou/.home-codex-official/.local/share/openclaw-2026.3.7/node_modules/openclaw/openclaw.mjs`
- State dir: `/vol1/1000/home-yuanhaizhou/.home-codex-official/.openclaw`

## Checks

- `plugins_doctor`: PASS | [plugins] feishu_bitable: Registered bitable tools
No plugin issues detected.
- `status_json_loaded`: PASS | sessions.count=11
- `topology_recognized`: PASS | agent_ids=['main', 'maintagent']
- `topology_matches_expectation`: PASS | topology=ops
- `heartbeat_agent_count`: PASS | expected=2
- `legacy_role_agents_removed`: PASS | configured=['main', 'maintagent']
- `main_profile_coding`: PASS | profile=coding
- `skills_repo_only`: PASS | extraDirs=['/vol1/1000/projects/ChatgptREST/skills-src'] allowBundled=[]
- `main_skills_repo_public`: PASS | skills=['chatgptrest-call']
- `main_has_openmind_tools`: PASS | alsoAllow=['sessions_send', 'sessions_list', 'sessions_history', 'openmind_memory_status', 'openmind_memory_recall', 'openmind_memory_capture', 'openmind_graph_query', 'openmind_advisor_ask']
- `main_no_sessions_spawn`: PASS | effective=['apply_patch', 'edit', 'exec', 'memory_get', 'memory_search', 'openmind_advisor_ask', 'openmind_graph_query', 'openmind_memory_capture', 'openmind_memory_recall', 'openmind_memory_status', 'process', 'read', 'session_status', 'sessions_history', 'sessions_list', 'sessions_send', 'write']
- `main_no_subagents_tool`: PASS | effective=['apply_patch', 'edit', 'exec', 'memory_get', 'memory_search', 'openmind_advisor_ask', 'openmind_graph_query', 'openmind_memory_capture', 'openmind_memory_recall', 'openmind_memory_status', 'process', 'read', 'session_status', 'sessions_history', 'sessions_list', 'sessions_send', 'write']
- `maint_skills_absent`: PASS | skills=[]
- `ops_main_has_watchdog_comm_tools`: PASS | effective=['apply_patch', 'edit', 'exec', 'memory_get', 'memory_search', 'openmind_advisor_ask', 'openmind_graph_query', 'openmind_memory_capture', 'openmind_memory_recall', 'openmind_memory_status', 'process', 'read', 'session_status', 'sessions_history', 'sessions_list', 'sessions_send', 'write']
- `maintagent_profile_minimal`: PASS | profile=minimal
- `maintagent_tools_hardened`: PASS | effective=['session_status', 'sessions_list', 'sessions_send']
- `ops_agent_to_agent_allow`: PASS | allow=['main', 'maintagent']
- `plugins_no_local_load_paths`: PASS | paths=[]
- `plugins_env_http_proxy_disabled`: PASS | allow=['acpx', 'diffs', 'dingtalk', 'feishu', 'google-gemini-cli-auth', 'openmind-advisor', 'openmind-graph', 'openmind-memory', 'openmind-telemetry']
- `gateway_bind_loopback`: PASS | bind=loopback
- `gateway_trusted_proxies_configured`: PASS | trustedProxies=['127.0.0.1/32', '::1/128']
- `gateway_auth_token_mode`: PASS | auth={'mode': 'token', 'allowTailscale': False, 'token': '<redacted>'}
- `gateway_auth_token_present`: PASS | auth={'mode': 'token', 'allowTailscale': False, 'token': '<redacted>'}
- `gateway_tailscale_disabled`: PASS | gateway={'port': 18789, 'mode': 'local', 'bind': 'loopback', 'trustedProxies': ['127.0.0.1/32', '::1/128'], 'controlUi': {'allowInsecureAuth': False}, 'auth': {'mode': 'token', 'allowTailscale': False, 'token': '<redacted>'}, 'tailscale': {'mode': 'off', 'resetOnExit': False}}
- `feishu_tools_disabled`: PASS | tools={'doc': False, 'chat': False, 'wiki': False, 'drive': False, 'perm': False, 'scopes': False}
- `security_no_feishu_doc_warning`: PASS | summary.attack_surface
- `advisor_unauth_ingress_rejected`: PASS | status=401 body={"detail":"Invalid or missing API key"}
- `openmind_probe_reply`: PASS | OPENMIND_OK OPENMIND_PROBE_576c98268c68
- `openmind_tool_round`: PASS | tool_called=True tool_result=True assistant='OPENMIND_OK OPENMIND_PROBE_576c98268c68'
- `memory_capture_probe_reply`: PASS | CAPTURE_OK TRAVEL_PREF_935067306d0b
- `memory_capture_tool_round`: PASS | tool_called=True tool_result=True assistant='CAPTURE_OK TRAVEL_PREF_935067306d0b'
- `memory_capture_recorded`: PASS | {"ok": true, "results": [{"audit_trail": [{"action": "stage", "agent": "openclaw", "audit_id": "5d3df0b4-7ad9-4581-93af-5cdd5286125d", "created_at": "2026-03-09T14:05:58.348632+00:00", "new_tier": "staging", "old_tier": null, "reason": "initial staging", "record_id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab"}, {"action": "promote", "agent": "system", "audit_id": "bcae6a14-ba92-4ac5-bcf1-ba7200a94d99", "created_at": "2026-03-09T14:05:58.352642+00:00", "new_tier": "episodic", "old_tier": "staging", "reason": "cognitive memory capture", "record_id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab"}], "category": "captured_memory", "duplicate": false, "message": "captured", "ok": true, "record_id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab", "tier": "episodic", "title": "Business travel preference TRAVEL_PREF_935067306d0b #1", "trace_id": "8cfc4e53-b543-435a-92d0-6f7e00c22b93"}]}
- `memory_recall_probe_reply`: PASS | RECALL_OK TRAVEL_PREF_935067306d0b
- `memory_recall_tool_round`: PASS | tool_called=True tool_result=True assistant='RECALL_OK TRAVEL_PREF_935067306d0b'
- `memory_recall_captured_block`: PASS | {"cache_ttl_seconds": 120, "context_blocks": [{"kind": "memory", "metadata": {"record_count": 2}, "provenance": [{"id": "d8360df0-6f46-43f5-9028-69278e462e81", "key": "working:sess-1:1", "type": "memory_record"}, {"id": "8f386465-fb7d-4496-817f-02ab9a9c1474", "key": "working:sess-1:1", "type": "memory_record"}], "source_type": "working", "text": "user: 我们在讨论安徽项目的图谱和记忆设计。\nuser: We are discussing the anhuisubstrate graph and memory design.", "title": "Working Memory", "token_count": 43}, {"kind": "memory", "metadata": {"record_count": 2, "scope": "cross_session"}, "provenance": [{"id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab", "key": "Business travel preference TRAVEL_PREF_935067306d0b #1", "type": "memory_record"}, {"id": "52e1745b-17d9-4c30-b657-d6f0daa350b1", "key": "Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1", "type": "memory_record"}], "source_type": "captured", "text": "- Business travel preference TRAVEL_PREF_935067306d0b #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_935067306d0b.\n- Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_c7ddcc9a8689.", "title": "Remembered Guidance", "token_count": 88}, {"kind": "policy", "metadata": {"hint_count": 2}, "provenance": [], "source_type": "policy", "text": "- Preserve conversation continuity using recent working memory before introducing new framing.\n- Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.", "title": "Execution Hints", "token_count": 49}], "degraded": false, "degraded_sources": [], "metadata": {"account_id": "", "agent_id": "", "graph_scopes": ["personal"], "repo": "ChatgptREST", "session_id": "", "thread_id": ""}, "ok": true, "prompt_prefix": "## Recent Conversation\nuser: 我们在讨论安徽项目的图谱和记忆设计。\nuser: We are discussing the anhuisubstrate graph and memory design.\n\n## Remembered Guidance\n- Business travel preference TRAVEL_PREF_935067306d0b #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_935067306d0b.\n- Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_c7ddcc9a8689.\n\n## Policy Hints\n- Preserve conversation continuity using recent working memory before introducing new framing.\n- Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.", "requested_sources": ["memory", "policy"], "resolved_sources": ["memory", "policy"], "trace_id": "dc41dde1-0282-49c4-9e6e-5fc531340f73", "used_tokens": 180}
- `memory_recall_marker_present`: PASS | {"cache_ttl_seconds": 120, "context_blocks": [{"kind": "memory", "metadata": {"record_count": 2}, "provenance": [{"id": "d8360df0-6f46-43f5-9028-69278e462e81", "key": "working:sess-1:1", "type": "memory_record"}, {"id": "8f386465-fb7d-4496-817f-02ab9a9c1474", "key": "working:sess-1:1", "type": "memory_record"}], "source_type": "working", "text": "user: 我们在讨论安徽项目的图谱和记忆设计。\nuser: We are discussing the anhuisubstrate graph and memory design.", "title": "Working Memory", "token_count": 43}, {"kind": "memory", "metadata": {"record_count": 2, "scope": "cross_session"}, "provenance": [{"id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab", "key": "Business travel preference TRAVEL_PREF_935067306d0b #1", "type": "memory_record"}, {"id": "52e1745b-17d9-4c30-b657-d6f0daa350b1", "key": "Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1", "type": "memory_record"}], "source_type": "captured", "text": "- Business travel preference TRAVEL_PREF_935067306d0b #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_935067306d0b.\n- Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_c7ddcc9a8689.", "title": "Remembered Guidance", "token_count": 88}, {"kind": "policy", "metadata": {"hint_count": 2}, "provenance": [], "source_type": "policy", "text": "- Preserve conversation continuity using recent working memory before introducing new framing.\n- Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.", "title": "Execution Hints", "token_count": 49}], "degraded": false, "degraded_sources": [], "metadata": {"account_id": "", "agent_id": "", "graph_scopes": ["personal"], "repo": "ChatgptREST", "session_id": "", "thread_id": ""}, "ok": true, "prompt_prefix": "## Recent Conversation\nuser: 我们在讨论安徽项目的图谱和记忆设计。\nuser: We are discussing the anhuisubstrate graph and memory design.\n\n## Remembered Guidance\n- Business travel preference TRAVEL_PREF_935067306d0b #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_935067306d0b.\n- Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_c7ddcc9a8689.\n\n## Policy Hints\n- Preserve conversation continuity using recent working memory before introducing new framing.\n- Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.", "requested_sources": ["memory", "policy"], "resolved_sources": ["memory", "policy"], "trace_id": "dc41dde1-0282-49c4-9e6e-5fc531340f73", "used_tokens": 180}
- `main_sessions_spawn_runtime_denied`: PASS | SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_12a90bc8af6b
- `main_sessions_spawn_negative_probe`: PASS | tool_called=False tool_result=False assistant='SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_12a90bc8af6b'
- `main_subagents_runtime_denied`: PASS | SUBAGENTS_UNAVAILABLE NEGPROBE_e549659adab3
- `main_subagents_negative_probe`: PASS | tool_called=False tool_result=False assistant='SUBAGENTS_UNAVAILABLE NEGPROBE_e549659adab3'
- `maintagent_probe_reply`: PASS | SENT
- `maintagent_to_main_transcript`: PASS | VERIFY_PING_6fc5174263db
- `main_latest_transcript_token_matches`: PASS | VERIFY_PING_6fc5174263db

## Security

- critical=0 warn=0 info=1
- findings: `summary.attack_surface`

## Config Hardening

- topology: `ops`
- skills extraDirs: `["/vol1/1000/projects/ChatgptREST/skills-src"]`
- skills allowBundled: `[]`
- main profile: `coding`
- main skills: `["chatgptrest-call"]`
- main tools: `{"alsoAllow": ["sessions_send", "sessions_list", "sessions_history", "openmind_memory_status", "openmind_memory_recall", "openmind_memory_capture", "openmind_graph_query", "openmind_advisor_ask"], "deny": ["group:automation", "group:ui", "image", "sessions_spawn", "subagents"], "profile": "coding"}`
- main effective tools: `["apply_patch", "edit", "exec", "memory_get", "memory_search", "openmind_advisor_ask", "openmind_graph_query", "openmind_memory_capture", "openmind_memory_recall", "openmind_memory_status", "process", "read", "session_status", "sessions_history", "sessions_list", "sessions_send", "write"]`
- agentToAgent allow: `["main", "maintagent"]`
- maint skills: `[]`
- maint tools: `{"alsoAllow": ["sessions_send", "sessions_list"], "profile": "minimal"}`
- maint effective tools: `["session_status", "sessions_list", "sessions_send"]`
- plugins allow: `["acpx", "diffs", "dingtalk", "feishu", "google-gemini-cli-auth", "openmind-advisor", "openmind-graph", "openmind-memory", "openmind-telemetry"]`
- plugins load paths: `[]`
- gateway config: `{"auth": {"allowTailscale": false, "mode": "token", "token": "<redacted>"}, "bind": "loopback", "controlUi": {"allowInsecureAuth": false}, "mode": "local", "port": 18789, "tailscale": {"mode": "off", "resetOnExit": false}, "trustedProxies": ["127.0.0.1/32", "::1/128"]}`
- feishu tools: `{"chat": false, "doc": false, "drive": false, "perm": false, "scopes": false, "wiki": false}`
- review evidence: `{"auth_probe": "docs/reviews/evidence/openclaw_openmind/B2/openmind_advisor_auth_ops_20260309.json", "config_snapshot": "docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_config_ops_20260309.json", "transcript_excerpt": "docs/reviews/evidence/openclaw_openmind/B1/openclaw_openmind_transcript_ops_20260309.json", "verifier_json": "docs/reviews/openclaw_openmind_verifier_ops_20260309.json", "verifier_md": "docs/reviews/openclaw_openmind_verifier_ops_20260309.md"}`

## OpenMind Probe

- token: `OPENMIND_PROBE_576c98268c68`
- reply: `OPENMIND_OK OPENMIND_PROBE_576c98268c68`
- transcript: `tool_called=True tool_result=True assistant='OPENMIND_OK OPENMIND_PROBE_576c98268c68'`
- tool details: `{"graph_ready": true, "kb_ready": true, "memory_ready": true, "ok": true}`

## Memory Capture / Recall

- capture marker: `TRAVEL_PREF_935067306d0b`
- capture reply: `CAPTURE_OK TRAVEL_PREF_935067306d0b`
- capture transcript: `tool_called=True tool_result=True assistant='CAPTURE_OK TRAVEL_PREF_935067306d0b'`
- capture details: `{"ok": true, "results": [{"audit_trail": [{"action": "stage", "agent": "openclaw", "audit_id": "5d3df0b4-7ad9-4581-93af-5cdd5286125d", "created_at": "2026-03-09T14:05:58.348632+00:00", "new_tier": "staging", "old_tier": null, "reason": "initial staging", "record_id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab"}, {"action": "promote", "agent": "system", "audit_id": "bcae6a14-ba92-4ac5-bcf1-ba7200a94d99", "created_at": "2026-03-09T14:05:58.352642+00:00", "new_tier": "episodic", "old_tier": "staging", "reason": "cognitive memory capture", "record_id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab"}], "category": "captured_memory", "duplicate": false, "message": "captured", "ok": true, "record_id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab", "tier": "episodic", "title": "Business travel preference TRAVEL_PREF_935067306d0b #1", "trace_id": "8cfc4e53-b543-435a-92d0-6f7e00c22b93"}]}`
- recall reply: `RECALL_OK TRAVEL_PREF_935067306d0b`
- recall transcript: `tool_called=True tool_result=True assistant='RECALL_OK TRAVEL_PREF_935067306d0b'`
- recall details: `{"cache_ttl_seconds": 120, "context_blocks": [{"kind": "memory", "metadata": {"record_count": 2}, "provenance": [{"id": "d8360df0-6f46-43f5-9028-69278e462e81", "key": "working:sess-1:1", "type": "memory_record"}, {"id": "8f386465-fb7d-4496-817f-02ab9a9c1474", "key": "working:sess-1:1", "type": "memory_record"}], "source_type": "working", "text": "user: 我们在讨论安徽项目的图谱和记忆设计。\nuser: We are discussing the anhuisubstrate graph and memory design.", "title": "Working Memory", "token_count": 43}, {"kind": "memory", "metadata": {"record_count": 2, "scope": "cross_session"}, "provenance": [{"id": "f53e5933-ad2e-46d2-8146-3d5518f4d4ab", "key": "Business travel preference TRAVEL_PREF_935067306d0b #1", "type": "memory_record"}, {"id": "52e1745b-17d9-4c30-b657-d6f0daa350b1", "key": "Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1", "type": "memory_record"}], "source_type": "captured", "text": "- Business travel preference TRAVEL_PREF_935067306d0b #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_935067306d0b.\n- Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_c7ddcc9a8689.", "title": "Remembered Guidance", "token_count": 88}, {"kind": "policy", "metadata": {"hint_count": 2}, "provenance": [], "source_type": "policy", "text": "- Preserve conversation continuity using recent working memory before introducing new framing.\n- Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.", "title": "Execution Hints", "token_count": 49}], "degraded": false, "degraded_sources": [], "metadata": {"account_id": "", "agent_id": "", "graph_scopes": ["personal"], "repo": "ChatgptREST", "session_id": "", "thread_id": ""}, "ok": true, "prompt_prefix": "## Recent Conversation\nuser: 我们在讨论安徽项目的图谱和记忆设计。\nuser: We are discussing the anhuisubstrate graph and memory design.\n\n## Remembered Guidance\n- Business travel preference TRAVEL_PREF_935067306d0b #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_935067306d0b.\n- Business travel preference TRAVEL_PREF_c7ddcc9a8689 #1: When planning business travel, prefer Hangzhou over Shanghai if schedules are similar. Marker TRAVEL_PREF_c7ddcc9a8689.\n\n## Policy Hints\n- Preserve conversation continuity using recent working memory before introducing new framing.\n- Knowledge coverage is low; escalate to /v2/advisor/ask for deep research if confidence is critical.", "requested_sources": ["memory", "policy"], "resolved_sources": ["memory", "policy"], "trace_id": "dc41dde1-0282-49c4-9e6e-5fc531340f73", "used_tokens": 180}`

## Advisor Auth

- probe: `{"authenticated_body": "{\"by_type\":{\"advisor_ask.kb_direct\":1,\"delivery.failed\":19,\"dispatch.task_completed\":2,\"dispatch.task_started\":2,\"kb.writeback\":1,\"llm.call_completed\":3,\"llm.call_failed\":1,\"memory.capture\":15,\"route.candidate_outcome\":4,\"route.fallback\":1,\"route.selected\":1,\"team.role.completed\":2,\"team.run.completed\":2,\"team.run.created\":2,\"tool.completed\":95,\"tool.failed\":10,\"workflow.completed\":130,\"workflow.failed\":6},\"by_domain\":{\"advisor_ask\":1,\"delivery\":19,\"dispatch\":4,\"kb\":1,\"llm\":8,\"memory\":15,\"routing\":2,\"team\":6,\"tool\":105,\"workflow\":136},\"total\":297}", "authenticated_status": 200, "unauthenticated_body": "{\"detail\":\"Invalid or missing API key\"}", "unauthenticated_status": 401, "url": "http://127.0.0.1:18711/v2/advisor/ask"}`

## Communication Probe

- token: `VERIFY_PING_6fc5174263db`
- probe reply: `SENT`
- transcript observed: `True`
- latest token in main transcript: `VERIFY_PING_6fc5174263db`

## Negative Runtime Probes

- sessions_spawn token: `NEGPROBE_12a90bc8af6b`
- sessions_spawn reply: `SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_12a90bc8af6b`
- sessions_spawn transcript: `tool_called=False tool_result=False assistant='SESSIONS_SPAWN_UNAVAILABLE NEGPROBE_12a90bc8af6b'`
- subagents token: `NEGPROBE_e549659adab3`
- subagents reply: `SUBAGENTS_UNAVAILABLE NEGPROBE_e549659adab3`
- subagents transcript: `tool_called=False tool_result=False assistant='SUBAGENTS_UNAVAILABLE NEGPROBE_e549659adab3'`

