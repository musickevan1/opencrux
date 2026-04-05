# Milestone Operations

## Purpose

Use this document as the lightweight milestone operating model for OpenCrux.

It is meant to provide the useful parts of structured milestone management without introducing a second project system outside the repository.

## Source Of Truth

OpenCrux should keep milestone and progress state in repo docs.

Primary docs:

- [prd-status.md](prd-status.md): current product posture, active milestone, and recommended next slice
- [milestone-1.md](milestone-1.md): current milestone scope, acceptance criteria, and known risks
- [next-session-handover.md](next-session-handover.md): live checkpoint and exact next-session start point

Supporting docs:

- implementation or phase handoffs such as [ui-revamp-phase-1-handoff.md](ui-revamp-phase-1-handoff.md)
- verification logs such as [ui-phase-1-verification-log.md](ui-phase-1-verification-log.md)
- bounded workflow docs such as [autopilot-session-protocol.md](autopilot-session-protocol.md) and [autoresearch-heuristic-protocol.md](autoresearch-heuristic-protocol.md)

## Milestone Registry

### Milestone 1

Goal:

- deliver the local-first single-climber recorded-footage slice with explainable metrics and honest unsupported-footage behavior

Status:

- implemented
- verified
- ready for sign-off

Current follow-on slices:

- default product slice: Phase 1.3 CI wiring for targeted verification
- separate bounded track: supervised heuristic autoresearch inside [src/opencrux/heuristics.py](../src/opencrux/heuristics.py)

### Milestone 2

Goal:

- add vision-language coaching insights to the analysis pipeline using Gemma 4 via Ollama with Gemini API fallback

Status:

- implemented
- tests passing

## Standard Slice Shape

Every bounded slice should use these sections, whether they live in a milestone doc, a handoff doc, or a phase-specific artifact:

1. Discovery
2. Implementation
3. Verification
4. Review
5. Next Step

This is enough structure to preserve continuity without turning the repo into process overhead.

## Status Vocabulary

Use these status labels consistently:

- planned: the slice is defined but not started
- in progress: implementation or verification is currently underway
- blocked: the slice cannot proceed without an external decision or dependency
- implemented: the code or doc change landed but verification is incomplete
- verified: implementation and relevant checks passed
- ready for sign-off: verified and waiting only on explicit acceptance or release sequencing
- archived: no longer active, retained only as project history

## Required Artifacts Per Slice

Minimum artifact set for any meaningful slice:

1. scope and success condition in an existing milestone or phase doc
2. implementation evidence in code or docs
3. verification evidence in tests, benchmark output, or manual verification notes
4. residual risk and exact next step in [next-session-handover.md](next-session-handover.md)

## When To Create A New Phase Doc

Create a new phase-specific document only when one of these is true:

- the slice spans multiple sessions
- the verification evidence needs a durable narrative
- the slice changes user-visible behavior or release posture

Do not create a new phase doc for tiny one-file changes that can be fully described in [next-session-handover.md](next-session-handover.md).

## When To Start A New Milestone

Start a new milestone only when all of the following are true:

1. the current milestone has stable acceptance criteria
2. the core behavior is already verified
3. the next work changes the product boundary rather than simply hardening the same slice

## Current Recommendation

Do not create a separate GSD project for OpenCrux right now.

Use this document plus the existing repo docs as the operating structure, and keep milestone truth local to the codebase.