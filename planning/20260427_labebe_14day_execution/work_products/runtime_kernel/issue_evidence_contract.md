# Issue Evidence Contract v0

Issue: `PCL-001`

## Done Means Evidence, Not Assertion

An issue cannot be marked done because an agent says it is done. It needs artifact evidence.

## Required Closeout Files

Every issue must provide:

- `handoff.md`
- `evidence_manifest.json`
- all required acceptance artifacts from `05_ISSUE_INDEX_AND_ACCEPTANCE.md`

## Required Manifest Fields

Each `evidence_manifest.json` must include:

- issue id;
- artifact set;
- owner role;
- worker/runtime;
- artifact list;
- source references where available;
- commands/methods used;
- confidence;
- limitations;
- forbidden actions check;
- next handoff.

## Worker Restrictions

Workers must not:

- call Pro/Gemini;
- edit outside assigned write scope;
- invent product/review/safety/material claims;
- start full crawls unless the issue explicitly asks;
- mark sprint-level issues done.

## Main Controller Responsibilities

Main controller must:

- review artifacts;
- decide whether evidence is usable;
- run or request gates;
- integrate into the master plan or Commerce Decision Layer;
- document accepted and rejected outputs.

