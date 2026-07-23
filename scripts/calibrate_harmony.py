"""Run Interlude's harmonic pipeline against the local calibration recordings."""

from argparse import ArgumentParser
from pathlib import Path
import json
import sys

import librosa
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import Interlude  # noqa: E402


def validate_expectations(measured, expectations):
    failures = []

    for name, threshold in expectations.items():
        if name.startswith("minimum_"):
            metric = name.removeprefix("minimum_")
            if measured.get(metric) is None or measured[metric] < threshold:
                failures.append(f"{metric} must be at least {threshold}")
        elif name.startswith("maximum_"):
            metric = name.removeprefix("maximum_")
            if measured.get(metric) is None or measured[metric] > threshold:
                failures.append(f"{metric} must be at most {threshold}")

    return {"passed": not failures, "failures": failures}


def analyze_track(audio_path):
    y, sr = librosa.load(audio_path, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    onset_envelope = librosa.onset.onset_strength(y=y, sr=sr)
    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sr,
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    detected_key = Interlude.detect_key_and_mode(
        Interlude.build_key_chroma_profile(y, sr)
    )
    harmonic_signal = librosa.effects.harmonic(y=y, margin=8)
    analysis = Interlude.analyze_harmonic_complexity(
        y,
        sr,
        beat_times,
        duration,
        harmonic_signal=harmonic_signal,
        detected_key=detected_key,
    )
    return {
        "duration": float(duration),
        "detected_key": {
            "root": detected_key["root"],
            "scale_type": detected_key["scale_type"],
            "correlation": detected_key["correlation"],
            "margin": detected_key["correlation_margin"],
        },
        "harmonic_complexity": analysis["overall_score"],
        "harmonic_evidence_score": analysis["evidence_score"],
        "diatonic_deviation": analysis["diatonic_deviation"],
        "adjusted_diatonic_deviation": analysis["adjusted_diatonic_deviation"],
        "harmonic_movement": analysis["harmonic_movement"],
        "tonal_stability": analysis["tonal_stability"],
        "voicing_density": analysis["voicing_density"],
        "modulation_load": analysis["modulation_load"],
        "harmonic_color": analysis["harmonic_color"],
        "mean_quality_color": analysis["movement"]["mean_quality_color"],
        "dominant_factors": analysis["dominant_factors"],
        "ambiguous_window_ratio": analysis["confidence"]["ambiguous_window_ratio"],
        "modulation_runs": analysis["modulation"]["runs"],
        "chord_change_count": analysis["movement"]["chord_change_count"],
        "unique_transition_ratio": analysis["movement"]["unique_transition_ratio"],
        "colored_chord_ratio": analysis["movement"]["colored_chord_ratio"],
        "altered_chord_ratio": analysis["movement"]["altered_chord_ratio"],
        "altered_salience": analysis["movement"]["altered_salience"],
        "chord_quality_counts": analysis["movement"]["chord_quality_counts"],
    }


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "tests" / "harmony_calibration_manifest.json",
    )
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=ROOT / "Test",
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="fixture_ids",
        help="Analyze only one manifest id; repeat to select several.",
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = []
    calibration_failed = False

    for fixture in manifest["recordings"]:
        if args.fixture_ids and fixture["id"] not in args.fixture_ids:
            continue

        audio_path = args.audio_root / fixture["filename"]
        if not audio_path.exists():
            results.append({**fixture, "status": "missing"})
            continue

        print(f"Analyzing {fixture['id']}...", file=sys.stderr, flush=True)
        measured = analyze_track(audio_path)
        validation = validate_expectations(
            measured,
            fixture.get("expectations", {}),
        )
        calibration_failed = calibration_failed or not validation["passed"]
        results.append(
            {
                **fixture,
                "status": "analyzed",
                "measured": measured,
                "validation": validation,
            }
        )
        print(f"Finished {fixture['id']}", file=sys.stderr, flush=True)

    print(json.dumps({"calibration_version": 1, "results": results}, indent=2))
    if calibration_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
