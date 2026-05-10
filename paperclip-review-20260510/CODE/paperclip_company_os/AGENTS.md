# Paperclip Company OS Rules

Scope: this directory implements the shared Paperclip company execution kernel.

- This package is controller/runtime infrastructure, not a business-domain output area.
- Do not place Finbot, Labebe, Planning or Memory domain artifacts here.
- Keep schemas provider-agnostic and file-backed so a fresh agent can resume from paths.
- Every closeout must fail closed when evidence, validation, memory closeout or Paperclip readback is missing.
- Native runtime/MCP/skill config mutation must be represented as a gated change record, not hidden in ordinary execution code.
- For the active Paperclip production lane, `production-usable: blocked` is an
  execution baseline, not a completion state. Follow
  `/vol1/1000/projects/toyresearch/docs/superpowers/plans/2026-05-07-paperclip-unblock-to-passed-master-plan.md`
  until the master acceptance criteria pass or a hard external blocker requires
  user authorization.
- Do not treat `registered, not executed`, `future run needed`, `done with
  caveats`, `partial success`, or `blocked terminal package` as terminal success.
  Each remaining blocker must have exact issue ID, owner, evidence, validator,
  memory closeout or no-write reason, and Paperclip readback.
