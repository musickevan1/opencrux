"""Tests for annotated frame generation."""
from __future__ import annotations

import numpy as np

from opencrux.annotator import annotate_frame, AnnotationLayer


class TestAnnotator:
    def test_annotate_frame_returns_jpeg_bytes(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = [
            {"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}
            for _ in range(33)
        ]
        angles = {"left_elbow": 90.0, "right_elbow": 120.0}

        result = annotate_frame(
            frame=frame,
            landmarks=landmarks,
            angles=angles,
            layers=[AnnotationLayer.SKELETON, AnnotationLayer.ANGLES],
        )
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:2] == b'\xff\xd8'  # JPEG magic

    def test_skeleton_only(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33

        result = annotate_frame(
            frame=frame, landmarks=landmarks, angles={},
            layers=[AnnotationLayer.SKELETON],
        )
        assert isinstance(result, bytes)
        assert result[:2] == b'\xff\xd8'

    def test_movement_trail_layer(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33
        trail = [(0.3, 0.6), (0.4, 0.55), (0.5, 0.5)]

        result = annotate_frame(
            frame=frame, landmarks=landmarks, angles={},
            layers=[AnnotationLayer.MOVEMENT_TRAIL],
            centroid_trail=trail,
        )
        assert isinstance(result, bytes)

    def test_metrics_overlay(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33

        result = annotate_frame(
            frame=frame, landmarks=landmarks, angles={},
            layers=[AnnotationLayer.METRICS_OVERLAY],
            metrics_text=["Elbow: 90deg", "Hip offset: 5deg"],
        )
        assert isinstance(result, bytes)

    def test_empty_layers_still_returns_jpeg(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9}] * 33

        result = annotate_frame(
            frame=frame, landmarks=landmarks, angles={}, layers=[],
        )
        assert isinstance(result, bytes)
        assert result[:2] == b'\xff\xd8'

    def test_low_visibility_landmarks_not_drawn(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # All landmarks invisible
        landmarks = [{"x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.1}] * 33

        result = annotate_frame(
            frame=frame, landmarks=landmarks, angles={},
            layers=[AnnotationLayer.SKELETON],
        )
        # Should still return valid JPEG (just no skeleton drawn)
        assert isinstance(result, bytes)
        assert result[:2] == b'\xff\xd8'
