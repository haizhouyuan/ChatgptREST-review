## Context

After the initial live smoke round:

- telemetry ingest to canonical atom was working
- issue-domain canonical export was working
- advisor recall still returned `sources.evomap = 0`

That was traced to a data-state constraint, not an API or routing failure:

- consult helper only exposes EvoMap hits with:
  - `promotion_status in ('active', 'staged')`
  - `groundedness >= 0.5`
- the live canonical DB had zero atoms meeting that condition

## Additional Fix Applied

The groundedness batch runner was too narrow:

- `run_p2_groundedness()` only processed `promotion_status='candidate'`
- many runtime-retrievable atoms created by activity ingest sit at:
  - `promotion_status='staged'`
  - `status='candidate'`

This was fixed in:

- `3f22bde` `fix: score staged atoms for evomap runtime visibility`

with a matching regression in `tests/test_groundedness.py`.

## Live Activation Procedure

To prove the runtime path end-to-end without widening the whole DB at once, a
single real atom was selected:

- `atom_id = at_act_4a0d5ad7401d3fe6`
- `canonical_question = commit 1c27125a on ChatgptREST`

The atom already satisfied the runtime-side promotion gate prerequisites:

- `promotion_status = staged`
- `status = candidate`

Its groundedness was evaluated with the existing checker:

- `check_atom_groundedness(...) -> overall = 1.0`

The resulting score was then written back to the atom and recorded into
`groundedness_audit` as:

- `audit_id = ga_1e17794b96a7`

This was a narrow runtime activation smoke, not a broad rollout.

## Recall Validation

Query:

```json
{
  "query": "commit 1c27125a on ChatgptREST",
  "top_k": 5
}
```

Endpoint:

- `POST /v1/advisor/recall`

Result:

```json
{
  "sources": {
    "kb": 5,
    "evomap": 1
  },
  "total_hits": 5
}
```

This proves:

1. EvoMap canonical atoms can now become consult-visible on the live runtime
2. The remaining gating issue was data-state / groundedness coverage, not a
   routing failure
3. The consult helper is correctly merging KB and EvoMap sources

## Conclusion

All three target live smoke chains are now proven:

1. `telemetry ingest -> canonical atom`
2. `issue-domain canonical export -> canonical result`
3. `advisor recall -> evomap source visible`

## Recommended Next Step

Do not hand-edit more atoms one by one.

The next production-safe step should be:

- define a narrow activation pack for high-value staged atoms
- run groundedness scoring on that pack
- only then expand recall-visible EvoMap coverage in a controlled way
