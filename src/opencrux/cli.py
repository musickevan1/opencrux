from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .analysis import AnalysisError, VisionAnalyzer
from .config import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run OpenCrux analysis on a local climbing clip.")
    parser.add_argument("video_path", type=Path, nargs="?", help="Path to a local video clip.")
    parser.add_argument("--route-name", default=None, help="Optional route or problem name.")
    parser.add_argument("--gym-name", default=None, help="Optional gym or wall label.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional manifest path for batch verification of local sample clips.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path for writing the analysis JSON output.",
    )
    return parser


def analyze_clip(
    analyzer: VisionAnalyzer,
    video_path: Path,
    *,
    route_name: str | None,
    gym_name: str | None,
) -> dict[str, Any]:
    analysis = analyzer.analyze(
        video_path,
        session_id=uuid4().hex,
        original_filename=video_path.name,
        route_name=route_name,
        gym_name=gym_name,
    )
    return analysis.model_dump(mode="json")


def run_manifest(analyzer: VisionAnalyzer, manifest_path: Path, output_dir: Path | None) -> dict[str, Any]:
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_dir = manifest_path.parent
    results: list[dict[str, Any]] = []

    for entry in manifest_data:
        clip_path = (base_dir / entry["filename"]).resolve()
        result: dict[str, Any] = {
            "id": entry.get("id", clip_path.stem),
            "filename": entry["filename"],
            "source": entry.get("source"),
            "notes": entry.get("notes"),
        }

        if not clip_path.exists():
            result.update({"status": "missing", "error": f"Video not found: {clip_path}"})
        else:
            try:
                payload = analyze_clip(
                    analyzer,
                    clip_path,
                    route_name=entry.get("route_name"),
                    gym_name=entry.get("gym_name"),
                )
                result.update({"status": "completed", "analysis": payload})
            except AnalysisError as error:
                result.update({"status": "failed", "error": str(error)})

        results.append(result)

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            result_path = output_dir / f"{result['id']}.json"
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    summary = {
        "manifest": str(manifest_path),
        "result_count": len(results),
        "results": results,
    }
    if output_dir is not None:
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    analyzer = VisionAnalyzer(settings)

    if args.manifest is not None:
        manifest_path = args.manifest.expanduser().resolve()
        if not manifest_path.exists():
            parser.error(f"Manifest not found: {manifest_path}")

        summary = run_manifest(analyzer, manifest_path, args.output)
        print(json.dumps(summary, indent=2))
        if any(item["status"] != "completed" for item in summary["results"]):
            return 1
        return 0

    if args.video_path is None:
        parser.error("Provide a video path or use --manifest.")

    video_path = args.video_path.expanduser().resolve()
    if not video_path.exists():
        parser.error(f"Video not found: {video_path}")

    try:
        payload = analyze_clip(
            analyzer,
            video_path,
            route_name=args.route_name,
            gym_name=args.gym_name,
        )
    except AnalysisError as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
        return 1

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())