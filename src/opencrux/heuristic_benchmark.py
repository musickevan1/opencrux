from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _band_penalty(value: float, bounds: list[float]) -> float:
    lower, upper = bounds
    if lower <= value <= upper:
        return 0.0
    if value < lower:
        return round(lower - value, 6)
    return round(value - upper, 6)


def _evaluate_clip(
    result: dict[str, Any],
    expectation: dict[str, Any],
    soft_metric_weights: dict[str, float],
) -> dict[str, Any]:
    hard_failures: list[str] = []
    soft_penalty = 0.0
    soft_penalty_breakdown: dict[str, float] = {}
    status = result.get("status")
    expected_status = expectation["expected_status"]

    if status != expected_status:
        hard_failures.append(f"expected status {expected_status}, got {status}")

    warning_codes: list[str] = []
    error_message = result.get("error")

    if status == "completed":
        analysis = result.get("analysis") or {}
        warnings = analysis.get("warnings") or []
        warning_codes = sorted(
            warning.get("code")
            for warning in warnings
            if isinstance(warning, dict) and warning.get("code")
        )

        required_warning_codes = expectation.get("required_warning_codes", [])
        forbidden_warning_codes = expectation.get("forbidden_warning_codes", [])
        for code in required_warning_codes:
            if code not in warning_codes:
                hard_failures.append(f"missing required warning code {code}")
        for code in forbidden_warning_codes:
            if code in warning_codes:
                hard_failures.append(f"forbidden warning code present: {code}")

        metrics = analysis.get("metrics") or {}
        attempt_count = metrics.get("attempt_count")
        attempt_count_range = expectation.get("attempt_count_range")
        if attempt_count_range is not None:
            minimum, maximum = attempt_count_range
            if attempt_count is None:
                hard_failures.append("missing metrics.attempt_count")
            elif not minimum <= attempt_count <= maximum:
                hard_failures.append(
                    f"attempt_count {attempt_count} outside expected range [{minimum}, {maximum}]"
                )

        for metric_name, bounds in expectation.get("metric_bands", {}).items():
            value = metrics.get(metric_name)
            if value is None:
                hard_failures.append(f"missing metrics.{metric_name}")
                continue
            penalty = _band_penalty(float(value), bounds)
            if penalty > 0:
                weight = soft_metric_weights.get(metric_name, 1.0)
                weighted_penalty = round(weight * penalty, 6)
                soft_penalty += weighted_penalty
                soft_penalty_breakdown[metric_name] = weighted_penalty

    if status == "failed":
        error_message = result.get("error")
        normalized_error = (error_message or "").lower()
        for fragment in expectation.get("required_error_substrings", []):
            if fragment.lower() not in normalized_error:
                hard_failures.append(f"missing error substring: {fragment}")

    return {
        "id": expectation["id"],
        "cohort": expectation.get("cohort"),
        "status": status,
        "error": error_message,
        "warning_codes": warning_codes,
        "passed": not hard_failures,
        "hard_failures": hard_failures,
        "soft_penalty": round(soft_penalty, 6),
        "soft_penalty_breakdown": soft_penalty_breakdown,
    }


def evaluate_benchmark(
    *,
    summary: dict[str, Any],
    benchmark_manifest: dict[str, Any],
    benchmark_expectations: dict[str, Any],
    baseline_report: dict[str, Any] | None = None,
    summary_path: str | None = None,
) -> dict[str, Any]:
    manifest_clips = benchmark_manifest.get("clips", [])
    expectations_by_id = {
        clip_expectation["id"]: clip_expectation for clip_expectation in benchmark_expectations.get("clips", [])
    }
    result_by_id = {result["id"]: result for result in summary.get("results", []) if isinstance(result, dict) and result.get("id")}
    benchmark_clip_ids = [clip["id"] for clip in manifest_clips]

    hard_failures: list[str] = []
    for clip_id in benchmark_clip_ids:
        if clip_id not in result_by_id:
            hard_failures.append(f"missing benchmark result for clip {clip_id}")
        if clip_id not in expectations_by_id:
            hard_failures.append(f"missing benchmark expectation for clip {clip_id}")

    unexpected_ids = sorted(set(result_by_id) - set(benchmark_clip_ids))
    for clip_id in unexpected_ids:
        hard_failures.append(f"unexpected result clip {clip_id}")

    soft_metric_weights = benchmark_expectations.get("soft_metric_weights", {})
    clip_reports: list[dict[str, Any]] = []
    for clip in manifest_clips:
        clip_id = clip["id"]
        if clip_id not in result_by_id or clip_id not in expectations_by_id:
            continue
        expectation = dict(expectations_by_id[clip_id])
        expectation.setdefault("cohort", clip.get("cohort"))
        clip_report = _evaluate_clip(result_by_id[clip_id], expectation, soft_metric_weights)
        clip_reports.append(clip_report)
        hard_failures.extend(f"{clip_id}: {failure}" for failure in clip_report["hard_failures"])

    soft_penalty_total = round(sum(report["soft_penalty"] for report in clip_reports), 6)
    baseline_comparison = None
    if baseline_report is not None:
        baseline_soft_penalty_total = float(baseline_report.get("soft_penalty_total", 0.0))
        baseline_comparison = {
            "baseline_report_path": baseline_report.get("report_path"),
            "baseline_passed": bool(baseline_report.get("passed")),
            "baseline_soft_penalty_total": round(baseline_soft_penalty_total, 6),
            "soft_penalty_delta": round(soft_penalty_total - baseline_soft_penalty_total, 6),
        }

    return {
        "benchmark_version": benchmark_manifest.get("benchmark_version"),
        "summary_path": summary_path,
        "passed": not hard_failures,
        "hard_failure_count": len(hard_failures),
        "hard_failures": hard_failures,
        "soft_penalty_total": soft_penalty_total,
        "clip_reports": clip_reports,
        "baseline_comparison": baseline_comparison,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate an OpenCrux heuristic benchmark summary.")
    parser.add_argument("summary_path", type=Path, help="Path to a CLI summary.json file.")
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to the committed benchmark manifest JSON.",
    )
    parser.add_argument(
        "--expectations",
        type=Path,
        required=True,
        help="Path to the committed benchmark expectations JSON.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Optional path to a committed baseline score report.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path for the evaluated benchmark report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    summary = load_json(args.summary_path)
    benchmark_manifest = load_json(args.manifest)
    benchmark_expectations = load_json(args.expectations)
    baseline_report = load_json(args.baseline) if args.baseline is not None else None

    report = evaluate_benchmark(
        summary=summary,
        benchmark_manifest=benchmark_manifest,
        benchmark_expectations=benchmark_expectations,
        baseline_report=baseline_report,
        summary_path=str(args.summary_path),
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_payload = dict(report)
        output_payload["report_path"] = str(args.output)
        args.output.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
        report = output_payload

    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())