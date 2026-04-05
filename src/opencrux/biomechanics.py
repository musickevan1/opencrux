"""Joint angle calculation and biomechanical metrics from pose landmarks."""
from __future__ import annotations

import math
from typing import Any


class LANDMARK:
    """MediaPipe pose landmark indices."""
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28


def compute_joint_angle(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    """Compute angle at point b formed by segments a-b and b-c, in degrees."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.sqrt(ba[0] ** 2 + ba[1] ** 2)
    mag_bc = math.sqrt(bc[0] ** 2 + bc[1] ** 2)
    if mag_ba == 0 or mag_bc == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def _lm_xy(landmarks: list[dict], idx: int) -> tuple[float, float] | None:
    lm = landmarks[idx]
    if lm.get("visibility", 0) < 0.3:
        return None
    return (lm["x"], lm["y"])


def compute_frame_angles(landmarks: list[dict[str, Any]]) -> dict[str, float]:
    """Compute all joint angles from 33 landmarks."""
    if len(landmarks) < 33:
        return {}
    angles: dict[str, float] = {}
    joint_defs = [
        ("left_elbow", LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_ELBOW, LANDMARK.LEFT_WRIST),
        ("right_elbow", LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_ELBOW, LANDMARK.RIGHT_WRIST),
        ("left_shoulder", LANDMARK.LEFT_HIP, LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_ELBOW),
        ("right_shoulder", LANDMARK.RIGHT_HIP, LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_ELBOW),
        ("left_hip", LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_HIP, LANDMARK.LEFT_KNEE),
        ("right_hip", LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_HIP, LANDMARK.RIGHT_KNEE),
        ("left_knee", LANDMARK.LEFT_HIP, LANDMARK.LEFT_KNEE, LANDMARK.LEFT_ANKLE),
        ("right_knee", LANDMARK.RIGHT_HIP, LANDMARK.RIGHT_KNEE, LANDMARK.RIGHT_ANKLE),
    ]
    for name, a_idx, b_idx, c_idx in joint_defs:
        a = _lm_xy(landmarks, a_idx)
        b = _lm_xy(landmarks, b_idx)
        c = _lm_xy(landmarks, c_idx)
        if a and b and c:
            angles[name] = round(compute_joint_angle(a, b, c), 1)

    l_hip = _lm_xy(landmarks, LANDMARK.LEFT_HIP)
    r_hip = _lm_xy(landmarks, LANDMARK.RIGHT_HIP)
    l_shoulder = _lm_xy(landmarks, LANDMARK.LEFT_SHOULDER)
    r_shoulder = _lm_xy(landmarks, LANDMARK.RIGHT_SHOULDER)
    if l_hip and r_hip and l_shoulder and r_shoulder:
        hip_center = ((l_hip[0] + r_hip[0]) / 2, (l_hip[1] + r_hip[1]) / 2)
        shoulder_center = ((l_shoulder[0] + r_shoulder[0]) / 2, (l_shoulder[1] + r_shoulder[1]) / 2)
        dx = abs(hip_center[0] - shoulder_center[0])
        dy = abs(hip_center[1] - shoulder_center[1])
        if dy > 0:
            angles["hip_wall_offset"] = round(math.degrees(math.atan2(dx, dy)), 1)
    return angles


def compute_reach_metrics(landmarks: list[dict[str, Any]]) -> dict[str, float]:
    """Compute reach and extension metrics."""
    metrics: dict[str, float] = {}
    l_wrist = _lm_xy(landmarks, LANDMARK.LEFT_WRIST)
    r_wrist = _lm_xy(landmarks, LANDMARK.RIGHT_WRIST)
    l_ankle = _lm_xy(landmarks, LANDMARK.LEFT_ANKLE)
    r_ankle = _lm_xy(landmarks, LANDMARK.RIGHT_ANKLE)
    l_shoulder = _lm_xy(landmarks, LANDMARK.LEFT_SHOULDER)
    r_shoulder = _lm_xy(landmarks, LANDMARK.RIGHT_SHOULDER)

    hand_ys = [p[1] for p in [l_wrist, r_wrist] if p]
    foot_ys = [p[1] for p in [l_ankle, r_ankle] if p]
    if hand_ys and foot_ys:
        metrics["body_span"] = round(max(foot_ys) - min(hand_ys), 3)

    for side, s, w in [("left", l_shoulder, l_wrist), ("right", r_shoulder, r_wrist)]:
        if s and w:
            dist = math.sqrt((s[0] - w[0]) ** 2 + (s[1] - w[1]) ** 2)
            metrics[f"{side}_arm_extension"] = round(dist, 3)
    return metrics
