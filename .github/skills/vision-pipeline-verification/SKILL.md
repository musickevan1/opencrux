---
name: vision-pipeline-verification
description: "Use when verifying OpenCrux MediaPipe and OpenCV changes, testing climbing video heuristics, validating failure modes, or reviewing warning quality in the vision pipeline."
---
# Vision Pipeline Verification

Use this skill when analysis behavior changes or when new climbing footage needs validation.

## Behaviors To Verify

- The video can be opened and sampled.
- Pose extraction succeeds on supported clips.
- Unsupported clips fail clearly.
- Warnings surface when coverage or visibility is weak.
- Attempt segmentation remains deterministic for the same input.
- Derived metrics remain explainable and timestamp-linked.

## Failure Modes

- No climber detected
- Multiple visible people
- Heavy occlusion
- Very short clips
- Corrupted or unsupported video formats
- Long continuous footage where attempt boundaries are ambiguous

## Evidence

- Automated tests for pure heuristics
- API-level tests for upload and retrieval behavior
- Manual verification on at least one known-good and one known-bad clip
