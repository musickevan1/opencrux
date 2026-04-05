"""Annotated frame generation with pose overlays and technique highlights."""
from __future__ import annotations

from enum import Enum
from typing import Any

import cv2
import numpy as np

from .biomechanics import LANDMARK


class AnnotationLayer(Enum):
    SKELETON = "skeleton"
    ANGLES = "angles"
    MOVEMENT_TRAIL = "movement_trail"
    METRICS_OVERLAY = "metrics_overlay"


POSE_CONNECTIONS = [
    (LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER),
    (LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_ELBOW),
    (LANDMARK.LEFT_ELBOW, LANDMARK.LEFT_WRIST),
    (LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_ELBOW),
    (LANDMARK.RIGHT_ELBOW, LANDMARK.RIGHT_WRIST),
    (LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_HIP),
    (LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_HIP),
    (LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP),
    (LANDMARK.LEFT_HIP, LANDMARK.LEFT_KNEE),
    (LANDMARK.LEFT_KNEE, LANDMARK.LEFT_ANKLE),
    (LANDMARK.RIGHT_HIP, LANDMARK.RIGHT_KNEE),
    (LANDMARK.RIGHT_KNEE, LANDMARK.RIGHT_ANKLE),
]


def _to_pixel(x: float, y: float, w: int, h: int) -> tuple[int, int]:
    return (int(x * w), int(y * h))


def _draw_skeleton(canvas: np.ndarray, landmarks: list[dict], color=(0, 255, 200)) -> None:
    h, w = canvas.shape[:2]
    for a_idx, b_idx in POSE_CONNECTIONS:
        a, b = landmarks[a_idx], landmarks[b_idx]
        if a.get("visibility", 0) < 0.3 or b.get("visibility", 0) < 0.3:
            continue
        cv2.line(canvas, _to_pixel(a["x"], a["y"], w, h), _to_pixel(b["x"], b["y"], w, h), color, 2, cv2.LINE_AA)
    for lm in landmarks:
        if lm.get("visibility", 0) < 0.3:
            continue
        cv2.circle(canvas, _to_pixel(lm["x"], lm["y"], w, h), 4, color, -1, cv2.LINE_AA)


def _draw_angles(canvas: np.ndarray, landmarks: list[dict], angles: dict[str, float]) -> None:
    h, w = canvas.shape[:2]
    positions = {
        "left_elbow": LANDMARK.LEFT_ELBOW, "right_elbow": LANDMARK.RIGHT_ELBOW,
        "left_shoulder": LANDMARK.LEFT_SHOULDER, "right_shoulder": LANDMARK.RIGHT_SHOULDER,
        "left_hip": LANDMARK.LEFT_HIP, "right_hip": LANDMARK.RIGHT_HIP,
        "left_knee": LANDMARK.LEFT_KNEE, "right_knee": LANDMARK.RIGHT_KNEE,
    }
    for name, val in angles.items():
        if name not in positions:
            continue
        lm = landmarks[positions[name]]
        if lm.get("visibility", 0) < 0.3:
            continue
        pt = _to_pixel(lm["x"], lm["y"], w, h)
        cv2.putText(canvas, f"{val:.0f}", (pt[0] + 8, pt[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1, cv2.LINE_AA)


def _draw_trail(canvas: np.ndarray, trail: list[tuple[float, float]], color=(255, 100, 50)) -> None:
    h, w = canvas.shape[:2]
    if len(trail) < 2:
        return
    points = [_to_pixel(x, y, w, h) for x, y in trail]
    for i in range(1, len(points)):
        alpha = i / len(points)
        thickness = max(1, int(alpha * 3))
        c = tuple(int(v * alpha) for v in color)
        cv2.line(canvas, points[i - 1], points[i], c, thickness, cv2.LINE_AA)


def annotate_frame(
    *,
    frame: np.ndarray,
    landmarks: list[dict[str, Any]],
    angles: dict[str, float],
    layers: list[AnnotationLayer],
    centroid_trail: list[tuple[float, float]] | None = None,
    metrics_text: list[str] | None = None,
) -> bytes:
    """Annotate a video frame with pose data and return as JPEG bytes."""
    canvas = frame.copy()
    if AnnotationLayer.SKELETON in layers:
        _draw_skeleton(canvas, landmarks)
    if AnnotationLayer.ANGLES in layers:
        _draw_angles(canvas, landmarks, angles)
    if AnnotationLayer.MOVEMENT_TRAIL in layers and centroid_trail:
        _draw_trail(canvas, centroid_trail)
    if AnnotationLayer.METRICS_OVERLAY in layers and metrics_text:
        y = 30
        for line in metrics_text:
            cv2.putText(canvas, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            y += 22
    _, buffer = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return buffer.tobytes()
