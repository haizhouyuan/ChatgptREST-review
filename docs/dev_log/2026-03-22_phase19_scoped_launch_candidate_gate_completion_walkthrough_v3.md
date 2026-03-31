# Phase 19 Scoped Launch Candidate Gate Walkthrough v3

## What Changed From v2

Two things were cleaned up:

1. default input resolution now prefers the newest existing upstream artifact
2. runner output now writes the next free `report_vN` instead of always targeting `report_v1`

## Practical Effect

The current `Phase 19` default path is finally self-consistent:

- it no longer defaults to stale `v1` evidence
- it no longer requires a manual “please read v2 instead” caveat

That makes `Phase 19 v3` the first version that can be used as the current formal scoped gate without path-version footnotes.
