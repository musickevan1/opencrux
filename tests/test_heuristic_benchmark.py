from opencrux.heuristic_benchmark import evaluate_benchmark


def build_benchmark_manifest() -> dict[str, object]:
    return {
        "benchmark_version": "milestone1-v1",
        "clips": [
            {"id": "known-good", "cohort": "supported"},
            {"id": "known-bad-occlusion", "cohort": "caution"},
            {"id": "known-unsupported", "cohort": "unsupported"},
        ],
    }


def build_benchmark_expectations() -> dict[str, object]:
    return {
        "benchmark_version": "milestone1-v1",
        "soft_metric_weights": {
            "estimated_time_on_wall_seconds": 1.0,
            "lateral_span_ratio": 1.0,
        },
        "clips": [
            {
                "id": "known-good",
                "expected_status": "completed",
                "forbidden_warning_codes": ["multiple_people_detected"],
                "attempt_count_range": [1, 1],
                "metric_bands": {
                    "estimated_time_on_wall_seconds": [8.0, 9.0],
                    "lateral_span_ratio": [0.09, 0.12],
                },
            },
            {
                "id": "known-bad-occlusion",
                "expected_status": "completed",
                "required_warning_codes": ["multiple_people_detected"],
                "attempt_count_range": [1, 1],
                "metric_bands": {
                    "estimated_time_on_wall_seconds": [12.5, 13.5],
                    "lateral_span_ratio": [0.04, 0.06],
                },
            },
            {
                "id": "known-unsupported",
                "expected_status": "failed",
                "required_error_substrings": ["multiple climbers", "one dominant climber"],
            },
        ],
    }


def build_summary() -> dict[str, object]:
    return {
        "results": [
            {
                "id": "known-good",
                "status": "completed",
                "analysis": {
                    "warnings": [],
                    "metrics": {
                        "attempt_count": 1,
                        "estimated_time_on_wall_seconds": 8.48,
                        "lateral_span_ratio": 0.105,
                    },
                },
            },
            {
                "id": "known-bad-occlusion",
                "status": "completed",
                "analysis": {
                    "warnings": [{"code": "multiple_people_detected"}],
                    "metrics": {
                        "attempt_count": 1,
                        "estimated_time_on_wall_seconds": 13.12,
                        "lateral_span_ratio": 0.048,
                    },
                },
            },
            {
                "id": "known-unsupported",
                "status": "failed",
                "error": "OpenCrux detected multiple climbers for a substantial portion of this clip. The current slice only supports one dominant climber per video.",
            },
        ]
    }


def test_evaluate_benchmark_passes_verified_baseline() -> None:
    report = evaluate_benchmark(
        summary=build_summary(),
        benchmark_manifest=build_benchmark_manifest(),
        benchmark_expectations=build_benchmark_expectations(),
        summary_path="summary.json",
    )

    assert report["passed"] is True
    assert report["hard_failures"] == []
    assert report["soft_penalty_total"] == 0.0


def test_evaluate_benchmark_rejects_unsupported_success_regression() -> None:
    summary = build_summary()
    summary["results"][2] = {
        "id": "known-unsupported",
        "status": "completed",
        "analysis": {"warnings": [], "metrics": {"attempt_count": 1}},
    }

    report = evaluate_benchmark(
        summary=summary,
        benchmark_manifest=build_benchmark_manifest(),
        benchmark_expectations=build_benchmark_expectations(),
        summary_path="summary.json",
    )

    assert report["passed"] is False
    assert any("known-unsupported: expected status failed, got completed" == failure for failure in report["hard_failures"])


def test_evaluate_benchmark_rejects_missing_required_warning() -> None:
    summary = build_summary()
    summary["results"][1]["analysis"]["warnings"] = []

    report = evaluate_benchmark(
        summary=summary,
        benchmark_manifest=build_benchmark_manifest(),
        benchmark_expectations=build_benchmark_expectations(),
        summary_path="summary.json",
    )

    assert report["passed"] is False
    assert any("known-bad-occlusion: missing required warning code multiple_people_detected" == failure for failure in report["hard_failures"])