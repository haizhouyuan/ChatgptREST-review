# Issue Index And Acceptance Ledger

Date: 2026-04-27
Status: Execution ledger after final Pro confirmation and first integration wave

This file is the local issue ledger for the 14-day sprint. It is not a replacement for Paperclip once issues are created there; it is the continuity source for Codex and delegated agents.

## Issue Status Values

- `draft`: defined locally, not yet active.
- `ready`: accepted into execution plan.
- `active`: assigned to main controller or worker.
- `blocked`: waiting on a concrete dependency.
- `review`: outputs exist and are under gate review.
- `done`: closeout evidence accepted.
- `deferred`: explicitly moved out of this sprint.

## Issue Ledger

| ID | Title | Owner Role | Status | Dependencies | Required Closeout Evidence |
| --- | --- | --- | --- | --- | --- |
| PCL-001 | Minimal Paperclip Operating Kernel | Paperclip Program Architect | review | Pro final confirmation completed | org tree, issue contract, gate kernel, evidence manifest schema |
| LAB-001 | Scope Boundary and Source Registry | Program Strategist / Evidence Steward | review | PCL-001 draft | scope boundary, source registry, source cards |
| LAB-002 | Tool and Source Method Probe | Tooling Research Engineer | review | LAB-001 draft | method comparison, access matrix, failures, initial media probe |
| LAB-003 | Product Master v0 and Data QA | Product Data Analyst | review | LAB-001, LAB-002 partial | product master draft, QA reports, unsafe fields |
| LAB-004 | Stratified 6-8 SKU Product Dossiers | Product Intelligence Analyst | review | LAB-003 | sample rationale, dossiers, facts sample, image role sample, claim seed ledger |
| LAB-005 | ASIN Identity and Marketplace Listing Sample | Marketplace Intelligence Analyst | review | LAB-004 sample list, LAB-002 Amazon method | ASIN candidates, match scoring, listing facts, source limitations |
| LAB-006 | Public Media Asset Probe and Scene Index | Media Asset Researcher | review | LAB-001, LAB-002 media method | media manifest, scene index, usage notes |
| LAB-007 | Commerce Decision Layer v0 | Commerce Strategist / UX Architect | review | LAB-004, LAB-006 sample, LAB-005 deferred to identity-first method | portfolio map, shopper mission map, hero matrix, nav matrix, PDP strategy, bundle map, design decision matrix |
| LAB-008 | Pure DTC Primary + Fallback Prototype | UX Designer / Prototype Engineer | review | LAB-007 and Design Decision Gate | prototype URLs/builds, route map, screenshots, design QA, browser QA |
| LAB-009 | AI Boss Gallery A-F v0 with Claim Gate | AI Demo Producer / Claim Steward | review | LAB-004/LAB-006 sample, Claim Gate | gallery pages, claim ledger, blocked claims, QA reports |
| LAB-010 | Executive Decision Pack | Main Controller / Writer | review | LAB-008, LAB-009 QA | executive pack, evidence wall, design summary, next build scope |

## Current Sprint Constraint

Final Pro confirmation is complete. The sprint is now narrowed by Pro feedback:

- exactly two active orgs;
- marketplace work is ASIN identity-first, not full Amazon crawl-first;
- DTC design is pure Labebe commerce, not mixed with Paperclip/AI demos;
- Paperclip/Boss Gallery comes after the Commerce Decision Layer.

## Gate-Linked Done Definition

An issue cannot be `done` unless:

- all acceptance criteria have an artifact path;
- `evidence_manifest.json` exists;
- `handoff.md` exists for delegated work;
- known limitations are explicit;
- forbidden actions were not taken;
- main controller has reviewed the outputs.
