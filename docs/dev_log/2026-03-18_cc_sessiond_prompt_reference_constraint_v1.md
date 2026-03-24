# 2026-03-18 cc-sessiond Prompt Reference Constraint v1

## Purpose

Turn the prompt-packaging rule into a hard `cc-sessiond` constraint:

- prompt is an index, not a duplicate spec
- prompt should reference versioned document paths
- prompt must not inline large Markdown spec bodies

This prevents long prompt packets from failing inside the Claude execution stack
and keeps task packets auditable and reusable.

## Fixed Rule

When creating a `cc-sessiond` session:

- keep the prompt short
- include repo / branch / mission / output contract
- reference detailed specs by path
- keep the actual blueprint, task spec, checklist, and walkthrough in versioned
  Markdown files

Do not paste large document bodies into the prompt.

## Runtime Enforcement

`CCSessionClient.create_session()` now rejects oversized prompts that look like
inlined document bundles.

The current guard blocks prompts that exceed the inline-size limit and also show
multiple document-bundle signals such as:

- many Markdown headings
- many bullets / numbered sections
- multiple fenced code blocks
- multiple Markdown file references

Rejected requests fail with a clear error:

`cc-sessiond prompt rejected: prompt must reference versioned document paths instead of pasting full document bodies.`

## API Behavior

`/v1/cc-sessions` and `/v1/cc-sessions/{session_id}/continue` convert this
constraint into `HTTP 400`.

That keeps the rule visible to callers instead of failing deep inside the
backend.

## Expected Prompt Shape

Example:

```text
Repo: /vol1/1000/projects/ChatgptREST
Branch: feat/example
Mission: execute the task packet
Read these first:
- /vol1/1000/projects/ChatgptREST/docs/2026-03-18_example_blueprint_v1.md
- /vol1/1000/projects/ChatgptREST/docs/dev_log/2026-03-18_example_task_spec_v1.md
Return JSON only.
```

Non-example:

- pasting the full blueprint body into the prompt
- pasting the full task spec body into the prompt
- embedding large markdown sections, fenced blocks, and long checklists directly
  in the prompt

## Tests Added

- `tests/test_cc_sessiond.py`
  - rejects an inlined document bundle
  - still accepts a short path-only prompt
- `tests/test_cc_sessiond_routes.py`
  - route returns `400` for a pasted long document bundle

## Result

This makes the rule durable:

- future `cc-sessiond` tasks follow the path-reference pattern by default
- long document bodies are kept in versioned files
- prompt packets stay compact enough for reliable execution
