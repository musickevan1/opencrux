"""Tests for biomechanical analysis."""
from __future__ import annotations

import math

from opencrux.biomechanics import compute_joint_angle, compute_frame_angles, compute_reach_metrics, LANDMARK


class TestJointAngles:
    def test_right_angle(self):
        angle = compute_joint_angle(
            a=(0.0, 0.0), b=(1.0, 0.0), c=(1.0, 1.0)
        )
        assert abs(angle - 90.0) < 0.1

    def test_straight_angle(self):
        angle = compute_joint_angle(
            a=(0.0, 0.0), b=(0.5, 0.0), c=(1.0, 0.0)
        )
        assert abs(angle - 180.0) < 0.1

    def test_zero_length_returns_zero(self):
        angle = compute_joint_angle(
            a=(1.0, 1.0), b=(1.0, 1.0), c=(2.0, 2.0)
        )
        assert angle == 0.0

    def test_compute_frame_angles_from_landmarks(self):
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33
        landmarks[LANDMARK.LEFT_SHOULDER] = {"x": 0.4, "y": 0.3, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.LEFT_ELBOW] = {"x": 0.3, "y": 0.5, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.LEFT_WRIST] = {"x": 0.2, "y": 0.5, "z": 0.0, "visibility": 0.9}

        angles = compute_frame_angles(landmarks)
        assert "left_elbow" in angles
        assert 0 < angles["left_elbow"] < 180

    def test_low_visibility_landmarks_excluded(self):
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.1}] * 33
        angles = compute_frame_angles(landmarks)
        assert len(angles) == 0

    def test_too_few_landmarks_returns_empty(self):
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 10
        angles = compute_frame_angles(landmarks)
        assert angles == {}

    def test_hip_wall_offset_computed(self):
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33
        landmarks[LANDMARK.LEFT_HIP] = {"x": 0.45, "y": 0.7, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.RIGHT_HIP] = {"x": 0.55, "y": 0.7, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.LEFT_SHOULDER] = {"x": 0.4, "y": 0.4, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.RIGHT_SHOULDER] = {"x": 0.6, "y": 0.4, "z": 0.0, "visibility": 0.9}

        angles = compute_frame_angles(landmarks)
        assert "hip_wall_offset" in angles
        assert angles["hip_wall_offset"] >= 0


class TestReachMetrics:
    def test_compute_body_span(self):
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33
        landmarks[LANDMARK.LEFT_WRIST] = {"x": 0.3, "y": 0.2, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.RIGHT_WRIST] = {"x": 0.7, "y": 0.25, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.LEFT_ANKLE] = {"x": 0.4, "y": 0.9, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.RIGHT_ANKLE] = {"x": 0.6, "y": 0.85, "z": 0.0, "visibility": 0.9}

        metrics = compute_reach_metrics(landmarks)
        assert "body_span" in metrics
        assert metrics["body_span"] > 0

    def test_arm_extension(self):
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33
        landmarks[LANDMARK.LEFT_SHOULDER] = {"x": 0.4, "y": 0.4, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.LEFT_WRIST] = {"x": 0.2, "y": 0.2, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.RIGHT_SHOULDER] = {"x": 0.6, "y": 0.4, "z": 0.0, "visibility": 0.9}
        landmarks[LANDMARK.RIGHT_WRIST] = {"x": 0.8, "y": 0.4, "z": 0.0, "visibility": 0.9}

        metrics = compute_reach_metrics(landmarks)
        assert "left_arm_extension" in metrics
        assert "right_arm_extension" in metrics
        assert metrics["left_arm_extension"] > 0
        assert metrics["right_arm_extension"] > 0
