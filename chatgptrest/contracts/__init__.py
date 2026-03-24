"""
Personal Intelligent Infrastructure – Cross-Cutting Contracts
======================================================================

This package defines the typed artifact schemas, trace-event envelope,
and event log that bind the four layers together:

    Layer 1 – Advisor (Interaction & Triage)
    Layer 2 – Workflow Services (Funnel / DeepResearch / QuickAnswer / Action)
    Layer 3 – Knowledge & Tool Substrate (KB)
    Layer 4 – Observability & Evolution (EvoMap)

Design references:
- CloudEvents v1.0 envelope for trace events
- Funnel DR → ProjectCard JSON Schema
- Advisor DR → AdvisorContext + C/K/U/R/I scoring model
- KB DR → EvidencePack + KB schemas
- EvoMap DR → TraceEvent as EvoMap signal source

All schemas use ``TypedDict`` + ``dataclasses`` so they stay
JSON-serialisable without heavy dependencies.
"""
