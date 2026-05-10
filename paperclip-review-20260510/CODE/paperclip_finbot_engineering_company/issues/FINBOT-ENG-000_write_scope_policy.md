# FINBOT-ENG-000 Boundary + Write-Scope Policy + Dry-Run Root

Status: closed

## Objective

Create the machine-readable write-scope policy and dry-run root.

## Expected Artifacts

- `contracts/WRITE_SCOPE_POLICY.json`
- `tools/validate_write_scope.py`
- `artifacts/dry_run/company_seed_manifest.json`

## Closeout Gate

Passes only when the validator rejects symlink escape, forbidden roots, and apply mode by default.

