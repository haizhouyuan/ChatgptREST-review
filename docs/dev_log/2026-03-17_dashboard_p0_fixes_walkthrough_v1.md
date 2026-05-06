# Dashboard P0 Fixes Walkthrough (v1)

## Summary

Implemented all 5 P0 fixes for the investor dashboard UX as specified in the task spec.

## Changes Made

### Fix 1: Split Investor Shell from Operator Shell
- Created `investor_base.html` - a dedicated template for investor pages
- Removed operator chrome elements: "Operator Dashboard" title, operator tabs, Raw JSON button, meta-strip with Root Runs/Source/Page
- Modified `routes_dashboard.py` to use `_render_investor_page()` for investor routes
- Updated all investor templates to extend `investor_base.html`

### Fix 2: Replace Full-Page Auto-Refresh with Incremental Refresh
- Modified `dashboard.js` to detect investor pages via `data-updated-indicator`
- For investor pages: fetches `/api/status` endpoint instead of full page reload
- Added "Updated Xs ago" indicator in header
- Operator pages still use full-page reload (unchanged)
- Added `/api/status` endpoint in routes

### Fix 3: Add Primary CTA to Investor Detail Pages
- Added primary CTA button to `investor_opportunity_detail.html`
- Button label based on `next_action` field or defaults (`Continue Research`/`Wait`/`Drop Thesis`)
- Uses existing `.primary-button` CSS class

### Fix 4: Fix Internal Terms and Language
- Changed "Current themes" → "Themes" in investor.html
- Changed "residual class" → "类型" (with tooltip showing original value)
- Added tooltips to ranking scores with explanations
- Fixed description text in Opportunity Radar

### Fix 5: Compress Detail Pages with Collapsible Sections
- Added `<details>` wrapper for Research Lanes (Claim/Skeptic/Expression) & Citation Register
- Added `<details>` wrapper for Source Scorecard & Historical Changes
- Primary content (thesis, decision, evidence) remains visible
- Secondary detailed content collapsed by default

## Files Changed

| File | Changes |
|------|---------|
| `chatgptrest/dashboard/templates/investor_base.html` | New file - investor shell template |
| `chatgptrest/api/routes_dashboard.py` | Added `_investor_nav_items()`, `_render_investor_page()`, status API, modified routes |
| `chatgptrest/dashboard/static/dashboard.js` | Incremental refresh for investor pages |
| `chatgptrest/dashboard/templates/investor.html` | Uses investor_base, fixed language |
| `chatgptrest/dashboard/templates/investor_opportunity_detail.html` | Primary CTA, collapsible sections, term fixes |
| `chatgptrest/dashboard/templates/investor_theme_detail.html` | Uses investor_base |
| `chatgptrest/dashboard/templates/investor_source_detail.html` | Uses investor_base |
| `tests/test_dashboard_routes.py` | Updated test assertion for "Themes" |

## Tests

```bash
./.venv/bin/pytest -q tests/test_dashboard_routes.py
# Result: All tests pass
```

## Residual Risks

1. The incremental refresh only fetches status metadata, not full page content - full content refresh would require more complex DOM patching
2. The collapsible sections use native `<details>` element - styling may need adjustment
3. Tooltips show raw internal values which may still be confusing to non-technical users

## Notes

- All investor routes now use `investor_base.html` which provides cleaner UX
- Operator dashboard unchanged - continues to use full-page auto-refresh
- Test updated to match new "Themes" copy (was "Current themes")
