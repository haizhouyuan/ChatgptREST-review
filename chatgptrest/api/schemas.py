from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    kind: str
    input: Dict[str, Any] = Field(default_factory=dict)  # noqa: A003
    params: Dict[str, Any] = Field(default_factory=dict)
    client: Optional[Dict[str, Any]] = None


class AdvisorAdviseRequest(BaseModel):
    raw_question: str
    context: Dict[str, Any] = Field(default_factory=dict)
    force: bool = False
    execute: bool = False
    mode: str = "balanced"
    orchestrate: bool = False
    quality_threshold: Optional[int] = None
    crosscheck: bool = False
    max_retries: int = 0
    agent_options: Dict[str, Any] = Field(default_factory=dict)


class AdvisorRunStepView(BaseModel):
    step_id: str
    step_type: str
    status: str
    attempt: int = 0
    job_id: Optional[str] = None
    lease_id: Optional[str] = None
    lease_expires_at: Optional[float] = None
    evidence_path: Optional[str] = None
    created_at: float
    updated_at: float
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)


class AdvisorRunView(BaseModel):
    ok: bool = True
    run_id: str
    request_id: Optional[str] = None
    mode: str
    status: str
    route: Optional[str] = None
    raw_question: Optional[str] = None
    normalized_question: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    quality_threshold: Optional[int] = None
    crosscheck: bool = False
    max_retries: int = 0
    orchestrate_job_id: Optional[str] = None
    final_job_id: Optional[str] = None
    degraded: bool = False
    error_type: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float
    ended_at: Optional[float] = None
    steps: list[AdvisorRunStepView] = Field(default_factory=list)


class AdvisorRunEventView(BaseModel):
    id: int
    run_id: str
    step_id: Optional[str] = None
    ts: float
    type: str
    payload: Optional[Dict[str, Any]] = None


class AdvisorRunEventsView(BaseModel):
    ok: bool = True
    run_id: str
    after_id: int
    next_after_id: int
    events: list[AdvisorRunEventView] = Field(default_factory=list)


class JobView(BaseModel):
    ok: bool = True
    job_id: str
    kind: Optional[str] = None
    parent_job_id: Optional[str] = None
    phase: Optional[str] = None
    phase_detail: Optional[str] = None
    status: str
    path: Optional[str] = None
    preview: str = ""
    answer_chars: Optional[int] = None
    conversation_url: Optional[str] = None
    conversation_export_format: Optional[str] = None
    conversation_export_path: Optional[str] = None
    conversation_export_sha256: Optional[str] = None
    conversation_export_chars: Optional[int] = None
    created_at: float
    updated_at: float
    not_before: Optional[float] = None
    attempts: Optional[int] = None
    max_attempts: Optional[int] = None
    retry_after_seconds: Optional[int] = None
    queue_position: Optional[int] = None
    estimated_wait_seconds: Optional[int] = None
    min_prompt_interval_seconds: Optional[int] = None
    action_hint: Optional[str] = None
    completion_quality: Optional[str] = None
    last_event_type: Optional[str] = None
    last_event_at: Optional[float] = None
    prompt_sent_at: Optional[float] = None
    assistant_answer_ready_at: Optional[float] = None
    cancel_requested_at: Optional[float] = None
    reason_type: Optional[str] = None
    reason: Optional[str] = None
    recovery_status: Optional[str] = None
    recovery_detail: Optional[str] = None
    safe_next_action: Optional[str] = None
    error: Optional[str] = None


class AnswerChunk(BaseModel):
    ok: bool = True
    job_id: str
    offset: int
    returned_chars: int
    next_offset: Optional[int] = None
    done: bool
    chunk: str


class ConversationChunk(AnswerChunk):
    """Same shape as AnswerChunk — kept as distinct type for API clarity."""
    pass


class JobEvent(BaseModel):
    id: int
    job_id: str
    ts: float
    type: str
    payload: Optional[Dict[str, Any]] = None


class JobEvents(BaseModel):
    ok: bool = True
    job_id: str
    after_id: int
    next_after_id: int
    events: list[JobEvent] = Field(default_factory=list)


class PauseView(BaseModel):
    ok: bool = True
    mode: str
    until_ts: float
    active: bool
    now: float
    seconds_remaining: float
    reason: Optional[str] = None


class PauseSetRequest(BaseModel):
    mode: str
    until_ts: Optional[float] = None
    duration_seconds: Optional[int] = None
    reason: Optional[str] = None


class IncidentView(BaseModel):
    incident_id: str
    fingerprint_hash: str
    signature: str
    category: Optional[str] = None
    severity: str
    status: str
    created_at: float
    updated_at: float
    last_seen_at: float
    count: int
    job_ids: list[str] = Field(default_factory=list)
    evidence_dir: Optional[str] = None
    repair_job_id: Optional[str] = None
    codex_input_hash: Optional[str] = None
    codex_last_run_ts: Optional[float] = None
    codex_run_count: int = 0
    codex_last_ok: Optional[bool] = None
    codex_last_error: Optional[str] = None
    codex_autofix_last_ts: Optional[float] = None
    codex_autofix_run_count: int = 0


class IncidentsList(BaseModel):
    ok: bool = True
    next_before_ts: Optional[float] = None
    next_before_incident_id: Optional[str] = None
    incidents: list[IncidentView] = Field(default_factory=list)


class RemediationActionView(BaseModel):
    action_id: str
    incident_id: str
    action_type: str
    status: str
    risk_level: str
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error: Optional[str] = None


class RemediationActionsList(BaseModel):
    ok: bool = True
    incident_id: str
    actions: list[RemediationActionView] = Field(default_factory=list)


class GlobalJobEvents(BaseModel):
    ok: bool = True
    after_id: int
    next_after_id: int
    events: list[JobEvent] = Field(default_factory=list)


class IdempotencyRecordView(BaseModel):
    ok: bool = True
    idempotency_key: str
    request_hash: str
    job_id: str
    created_at: float


class JobSummary(BaseModel):
    job_id: str
    kind: str
    parent_job_id: Optional[str] = None
    phase: Optional[str] = None
    status: str
    created_at: float
    updated_at: float
    not_before: Optional[float] = None
    attempts: Optional[int] = None
    max_attempts: Optional[int] = None
    conversation_url: Optional[str] = None
    answer_path: Optional[str] = None
    conversation_export_path: Optional[str] = None
    action_hint: Optional[str] = None
    reason_type: Optional[str] = None
    reason: Optional[str] = None


class JobsList(BaseModel):
    ok: bool = True
    next_before_ts: Optional[float] = None
    next_before_job_id: Optional[str] = None
    jobs: list[JobSummary] = Field(default_factory=list)


class ClientIssueReportRequest(BaseModel):
    project: str
    title: str
    severity: Optional[str] = None
    kind: Optional[str] = None
    symptom: Optional[str] = None
    raw_error: Optional[str] = None
    job_id: Optional[str] = None
    conversation_url: Optional[str] = None
    artifacts_path: Optional[str] = None
    source: Optional[str] = None
    fingerprint: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueStatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None
    actor: Optional[str] = None
    linked_job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueEvidenceLinkRequest(BaseModel):
    job_id: Optional[str] = None
    conversation_url: Optional[str] = None
    artifacts_path: Optional[str] = None
    note: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueVerificationRequest(BaseModel):
    verification_type: str
    status: str = "passed"
    verifier: Optional[str] = None
    note: Optional[str] = None
    job_id: Optional[str] = None
    conversation_url: Optional[str] = None
    artifacts_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueUsageEvidenceRequest(BaseModel):
    job_id: str
    client_name: Optional[str] = None
    kind: Optional[str] = None
    status: str = "completed"
    answer_chars: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueView(BaseModel):
    ok: bool = True
    issue_id: str
    fingerprint_hash: str
    fingerprint_text: str
    project: str
    title: str
    kind: Optional[str] = None
    severity: str
    status: str
    source: Optional[str] = None
    symptom: Optional[str] = None
    raw_error: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    count: int
    latest_job_id: Optional[str] = None
    latest_conversation_url: Optional[str] = None
    latest_artifacts_path: Optional[str] = None
    created_at: float
    updated_at: float
    first_seen_at: float
    last_seen_at: float
    closed_at: Optional[float] = None


class ClientIssueReportView(ClientIssueView):
    created: bool
    reopened: bool = False


class ClientIssueEvent(BaseModel):
    id: int
    issue_id: str
    ts: float
    type: str
    payload: Optional[Dict[str, Any]] = None


class ClientIssueEvents(BaseModel):
    ok: bool = True
    issue_id: str
    after_id: int
    next_after_id: int
    events: list[ClientIssueEvent] = Field(default_factory=list)


class ClientIssueVerificationView(BaseModel):
    verification_id: str
    issue_id: str
    ts: float
    verification_type: str
    status: str
    verifier: Optional[str] = None
    note: Optional[str] = None
    job_id: Optional[str] = None
    conversation_url: Optional[str] = None
    artifacts_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueVerifications(BaseModel):
    ok: bool = True
    issue_id: str
    verifications: list[ClientIssueVerificationView] = Field(default_factory=list)


class ClientIssueUsageEvidenceView(BaseModel):
    usage_id: str
    issue_id: str
    ts: float
    job_id: str
    client_name: Optional[str] = None
    kind: Optional[str] = None
    status: str
    answer_chars: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientIssueUsageEvidenceList(BaseModel):
    ok: bool = True
    issue_id: str
    usage: list[ClientIssueUsageEvidenceView] = Field(default_factory=list)


class ClientIssuesList(BaseModel):
    ok: bool = True
    next_before_ts: Optional[float] = None
    next_before_issue_id: Optional[str] = None
    issues: list[ClientIssueView] = Field(default_factory=list)


class ClientIssueGraphQueryRequest(BaseModel):
    issue_id: Optional[str] = None
    family_id: Optional[str] = None
    q: Optional[str] = None
    status: Optional[str] = None
    include_closed: bool = True
    limit: int = 20
    neighbor_depth: int = 1


class ClientIssueGraphNode(BaseModel):
    id: str
    kind: str
    label: str
    attrs: Dict[str, Any] = Field(default_factory=dict)


class ClientIssueGraphEdge(BaseModel):
    source: str
    target: str
    type: str
    attrs: Dict[str, Any] = Field(default_factory=dict)


class ClientIssueGraphQueryResponse(BaseModel):
    ok: bool = True
    generated_at: float
    summary: Dict[str, Any] = Field(default_factory=dict)
    matches: list[Dict[str, Any]] = Field(default_factory=list)
    nodes: list[ClientIssueGraphNode] = Field(default_factory=list)
    edges: list[ClientIssueGraphEdge] = Field(default_factory=list)


class ClientIssueCanonicalQueryRequest(BaseModel):
    issue_id: Optional[str] = None
    q: Optional[str] = None
    status: Optional[str] = None
    limit: int = 20


class ClientIssueCanonicalProjectionView(BaseModel):
    projection_name: str
    projection_state: str
    projection_reason: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ClientIssueCanonicalObjectView(BaseModel):
    object_id: str
    canonical_key: str
    domain: str
    object_type: str
    title: str
    summary: Optional[str] = None
    status: Optional[str] = None
    authority_level: str
    source_ref: Optional[str] = None
    source_repo: Optional[str] = None
    source_path: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    projections: list[ClientIssueCanonicalProjectionView] = Field(default_factory=list)


class ClientIssueCanonicalQueryResponse(BaseModel):
    ok: bool = True
    generated_at: float
    summary: Dict[str, Any] = Field(default_factory=dict)
    matches: list[Dict[str, Any]] = Field(default_factory=list)
    objects: list[ClientIssueCanonicalObjectView] = Field(default_factory=list)


class BuildInfoView(BaseModel):
    git_sha: Optional[str] = None
    git_dirty: Optional[bool] = None


class OpsStatusView(BaseModel):
    ok: bool = True
    now: float
    pause: PauseView
    jobs_by_status: Dict[str, int] = Field(default_factory=dict)
    raw_jobs_by_status: Dict[str, int] = Field(default_factory=dict)
    stale_jobs_by_status: Dict[str, int] = Field(default_factory=dict)
    stale_jobs_total: int = 0
    active_incidents: int = 0
    active_incident_families: int = 0
    active_open_issues: int = 0
    active_issue_families: int = 0
    stuck_wait_jobs: int = 0
    ui_canary_ok: Optional[bool] = None
    ui_canary_failed_providers: list[str] = Field(default_factory=list)
    attention_reasons: list[str] = Field(default_factory=list)
    last_job_event_id: Optional[int] = None
    build: Optional[BuildInfoView] = None
