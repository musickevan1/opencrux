# Milestone 1

## Objective

Deliver a thin vertical slice for recorded single-climber climbing analysis: ingest a video, extract pose landmarks, derive a small metric set, persist the result, and display it in a local web UI.

## In Scope

- Recorded bouldering or board-session clips
- One dominant climber in frame
- Local analysis with MediaPipe and OpenCV
- Session persistence as JSON
- Metric set:
  - attempt count
  - estimated time on wall
  - average rest interval
  - lateral span
  - vertical progress ratio
  - hesitation markers

## Acceptance Criteria

- A supported video upload returns a completed analysis payload.
- A failed analysis returns a clear, user-visible failure reason.
- Session results persist locally and can be reloaded by session id.
- The UI shows metrics, attempt timing, and warnings.
- The UI makes reliability posture obvious before metrics, and unsupported or warning-heavy footage does not read like a clean success path.
- Automated checks cover the heuristic and API wiring surfaces.
- Heuristic changes preserve benchmark v1 expectations for supported, caution, and unsupported sample cohorts before promotion.

## Known Risks

- Attempt segmentation is heuristic and conservative.
- Pose quality is sensitive to occlusion, camera angle, and lighting.
- Multi-person footage is intentionally unsupported and should fail clearly once it dominates the clip.
- Multi-pose warning posture is intentionally conservative so caution clips surface honesty before they cross into unsupported failure behavior.
- The current slice does not infer route difficulty or technique quality.
