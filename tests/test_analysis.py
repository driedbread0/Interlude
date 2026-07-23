import asyncio
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from fastapi import HTTPException

import Interlude
import app as api


class KeyDetectionTests(unittest.TestCase):
    def test_canonical_major_profiles_rotate_to_every_tonic(self):
        for root_index, root in Interlude.INDEX_TO_NOTE.items():
            with self.subTest(root=root):
                detected = Interlude.detect_key_and_mode(
                    np.roll(Interlude.KRUMHANSL_MAJOR_PROFILE, root_index),
                    allow_derived_modes=False,
                )
                self.assertEqual(detected["root"], root)
                self.assertEqual(detected["scale_type"], "major")
                self.assertAlmostEqual(detected["correlation"], 1.0)

    def test_canonical_minor_profile_and_correlation(self):
        a_minor = np.roll(
            Interlude.KRUMHANSL_MINOR_PROFILE,
            Interlude.NOTE_TO_INDEX["A"],
        )
        detected = Interlude.detect_key_and_mode(
            a_minor,
            allow_derived_modes=False,
        )
        self.assertEqual((detected["root"], detected["scale_type"]), ("A", "minor"))
        self.assertGreater(detected["correlation_margin"], 0)

    def test_guarded_mode_promotion_requires_characteristic_energy(self):
        dorian = Interlude.derived_mode_profile("dorian")
        promoted = Interlude.detect_key_and_mode(dorian)
        self.assertEqual(promoted["scale_type"], "dorian")
        self.assertEqual(promoted["profile_type"], "derived_mode")

        without_characteristic_energy = dorian.copy()
        without_characteristic_energy[9] = without_characteristic_energy[8] - 0.01
        guarded = Interlude.detect_key_and_mode(without_characteristic_energy)
        self.assertNotEqual(guarded["scale_type"], "dorian")

    def test_harmonic_and_melodic_minor_are_manual_only(self):
        for pattern_name in ("harmonic_minor", "melodic_minor"):
            profile = Interlude.SCALE_PATTERNS[pattern_name].astype(float) + 0.01
            detected = Interlude.detect_key_and_mode(profile)
            self.assertNotIn(
                detected["scale_type"],
                {"harmonic_minor", "melodic_minor"},
            )
            self.assertEqual(Interlude.get_scale_mask("C", pattern_name).shape, (12,))

    def test_manual_key_override_controls_harmony_analysis(self):
        chroma = np.tile(
            (Interlude.SCALE_PATTERNS["harmonic_minor"] + 0.1)[:, None],
            (1, 20),
        )
        detected = {
            "root": "C",
            "scale_type": "major",
            "correlation": 0.8,
            "correlation_margin": 0.2,
            "algorithm": "krumhansl_schmuckler_extended_v1",
            "profile_type": "canonical",
        }
        with mock.patch.object(
            Interlude.librosa.feature,
            "chroma_cqt",
            return_value=chroma,
        ), mock.patch.object(
            Interlude.librosa.decompose,
            "nn_filter",
            side_effect=lambda value, **_kwargs: value,
        ):
            result = Interlude.analyze_harmonic_complexity(
                np.ones(4096),
                22050,
                np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
                4.0,
                root_override="D",
                scale_override="harmonic_minor",
                harmonic_signal=np.ones(4096),
                detected_key=detected,
            )
        self.assertEqual(result["analysis_key"]["root"], "D")
        self.assertEqual(result["analysis_key"]["scale_type"], "harmonic_minor")
        self.assertEqual(result["detected_key"], detected)
        self.assertEqual(result["raw_score"], result["diatonic_deviation"])
        self.assertEqual(
            result["windows"][0]["raw_complexity"],
            result["windows"][0]["diatonic_deviation"],
        )
        self.assertEqual(
            result["windows"][0]["adjusted_complexity"],
            result["windows"][0]["harmonic_complexity"],
        )

    def test_modulation_requires_confidence_and_two_consecutive_windows(self):
        windows = [
            {
                "window": 1,
                "local_root": "G",
                "local_scale_type": "major",
                "local_key_correlation": 0.75,
                "local_key_correlation_margin": 0.20,
                "ambiguous": False,
            },
            {
                "window": 2,
                "local_root": "G",
                "local_scale_type": "major",
                "local_key_correlation": 0.76,
                "local_key_correlation_margin": 0.21,
                "ambiguous": False,
            },
            {
                "window": 3,
                "local_root": "D",
                "local_scale_type": "minor",
                "local_key_correlation": 0.59,
                "local_key_correlation_margin": 0.30,
                "ambiguous": False,
            },
        ]
        self.assertEqual(
            Interlude.detect_sustained_modulations(windows, "C", "major"),
            {1, 2},
        )

    def test_silent_input_is_rejected(self):
        with self.assertRaises(Interlude.AnalysisInputError):
            Interlude.build_key_chroma_profile(np.zeros(22050), 22050)

    def test_flat_tonally_empty_profile_is_rejected(self):
        nearly_flat = np.ones(12) + np.linspace(0.0, 0.01, 12)
        with self.assertRaises(Interlude.AnalysisInputError):
            Interlude.detect_key_and_mode(nearly_flat)


class HarmonicComplexityTests(unittest.TestCase):
    @staticmethod
    def chord_region(label, start):
        root, quality = label.split(":", 1)
        return {
            "start": float(start),
            "end": float(start + 1),
            "label": label,
            "root": root,
            "quality": quality,
            "similarity": 0.9,
            "margin": 0.1,
            "ambiguous": False,
            "smoothed": False,
        }

    def test_sustain_weighting_and_trim_reduce_isolated_chromatic_frame(self):
        chroma = np.zeros((12, 40))
        chroma[[0, 4, 7], :] = 1.0
        chroma[6, 20] = 4.0
        raw_normalized = chroma / np.sum(chroma, axis=0, keepdims=True)
        processed = Interlude.preprocess_harmonic_chroma(chroma)
        raw_deviation = float(np.mean(raw_normalized[6]))
        robust_deviation = float(Interlude.trimmed_mean(processed[6]))
        self.assertLess(robust_deviation, raw_deviation * 0.25)

    def test_repeated_and_novel_chord_movement_are_distinct(self):
        repeated_labels = ["C:major", "G:major", "C:major", "G:major", "C:major"]
        novel_labels = ["C:major", "D:minor", "E:minor", "F:major", "G:major"]
        repeated = [self.chord_region(label, index) for index, label in enumerate(repeated_labels)]
        novel = [self.chord_region(label, index) for index, label in enumerate(novel_labels)]
        repeated_transitions = Interlude.chord_transitions(repeated)
        novel_transitions = Interlude.chord_transitions(novel)
        repeated_counts = {
            transition: repeated_transitions.count(transition)
            for transition in set(repeated_transitions)
        }
        novel_counts = {
            transition: novel_transitions.count(transition)
            for transition in set(novel_transitions)
        }
        repeated_result = Interlude.summarize_harmonic_movement(repeated, repeated_counts)
        novel_result = Interlude.summarize_harmonic_movement(novel, novel_counts)
        self.assertEqual(repeated_result["repeated_transition_ratio"], 1.0)
        self.assertEqual(novel_result["novel_transition_ratio"], 1.0)
        self.assertGreater(
            novel_result["harmonic_movement"],
            repeated_result["harmonic_movement"],
        )

    def test_extensions_do_not_create_false_root_movement(self):
        regions = []
        for index, quality in enumerate(("major", "major7", "dominant9")):
            region = self.chord_region(f"C:{quality}", index)
            region["movement_label"] = "C:major"
            regions.append(region)

        self.assertEqual(Interlude.chord_transitions(regions), [])

    def test_dense_voicing_is_separate_from_diatonic_deviation(self):
        triad = np.zeros((12, 24))
        triad[[0, 4, 7], :] = 1.0
        dense = np.zeros((12, 24))
        dense[[0, 2, 4, 5, 7, 9, 11], :] = 1.0
        triad_density = Interlude.estimate_voicing_density(
            Interlude.preprocess_harmonic_chroma(triad)
        )
        dense_density = Interlude.estimate_voicing_density(
            Interlude.preprocess_harmonic_chroma(dense)
        )
        self.assertGreater(
            dense_density["voicing_density"],
            triad_density["voicing_density"],
        )
        self.assertGreater(
            dense_density["estimated_active_pitch_classes"],
            triad_density["estimated_active_pitch_classes"],
        )

    def test_composite_uses_documented_weights(self):
        evidence = Interlude.harmonic_evidence_score(
            0.2,
            0.4,
            0.75,
            0.5,
            0.6,
            0.7,
        )
        score = Interlude.harmonic_composite_score(
            0.2,
            0.4,
            0.75,
            0.5,
            0.6,
            0.7,
        )
        self.assertAlmostEqual(evidence, 0.5045)
        self.assertAlmostEqual(score, Interlude.normalized_harmonic_sigmoid(evidence))

    def test_sigmoid_preserves_endpoints_and_expands_midrange(self):
        self.assertAlmostEqual(Interlude.normalized_harmonic_sigmoid(0.0), 0.0)
        self.assertAlmostEqual(Interlude.normalized_harmonic_sigmoid(1.0), 1.0)
        self.assertGreater(Interlude.normalized_harmonic_sigmoid(0.4), 0.6)

    def test_extended_and_altered_chords_have_more_color_than_triads(self):
        results = {}
        for quality in ("major", "major7", "dominant_b9"):
            profile = np.zeros(12)
            for interval, weight in Interlude.CHORD_QUALITIES[quality]["intervals"]:
                profile[interval] = weight
            results[quality] = Interlude.estimate_chord_region(profile)

        self.assertEqual(results["major"]["label"], "C:major")
        self.assertEqual(results["major7"]["label"], "C:major7")
        self.assertEqual(results["dominant_b9"]["label"], "C:dominant_b9")
        self.assertLess(
            results["major"]["color_evidence"],
            results["major7"]["color_evidence"],
        )
        self.assertLess(
            results["major7"]["color_evidence"],
            results["dominant_b9"]["color_evidence"],
        )

    def test_altered_chord_salience_exceeds_common_seventh_color(self):
        major7 = self.chord_region("C:major7", 0)
        major7.update(
            color_complexity=0.44,
            color_evidence=0.44,
            quality_confidence=1.0,
        )
        altered = self.chord_region("C:dominant_b9", 0)
        altered.update(
            color_complexity=0.92,
            color_evidence=0.92,
            quality_confidence=1.0,
        )

        common = Interlude.summarize_harmonic_movement([major7], {})
        altered_result = Interlude.summarize_harmonic_movement([altered], {})

        self.assertGreater(
            altered_result["harmonic_color"],
            common["harmonic_color"],
        )

    def test_modulation_load_rewards_repeated_confident_runs(self):
        windows = [
            {
                "window": number,
                "start": float(number - 1),
                "end": float(number),
                "ambiguous": False,
            }
            for number in range(1, 33)
        ]
        one_run = {
            "modulation_windows": {1, 2},
            "confidence_by_window": {1: 0.8, 2: 0.8},
            "runs": [{"confidence": 0.8}],
        }
        four_runs = {
            "modulation_windows": set(range(1, 9)),
            "confidence_by_window": {number: 0.8 for number in range(1, 9)},
            "runs": [{"confidence": 0.8} for _ in range(4)],
        }

        sparse = Interlude.summarize_modulation_load(windows, one_run)
        frequent = Interlude.summarize_modulation_load(windows, four_runs)

        self.assertGreater(frequent["modulation_load"], sparse["modulation_load"])
        self.assertGreater(frequent["run_density"], sparse["run_density"])

    def test_low_key_confidence_is_ambiguous(self):
        local = {"correlation": 0.50, "correlation_margin": 0.01}
        global_key = {"correlation": 0.80, "correlation_margin": 0.20}
        confidence = Interlude.key_confidence_metadata(local, global_key)
        self.assertTrue(confidence["ambiguous"])
        self.assertEqual(confidence["level"], "low")

    def test_mode_change_can_form_a_modulation_run_with_transition_windows(self):
        windows = []
        for number, mode in enumerate(("major", "minor", "minor", "major"), start=1):
            windows.append(
                {
                    "window": number,
                    "local_root": "C",
                    "local_scale_type": mode,
                    "local_key_correlation": 0.82,
                    "local_key_correlation_margin": 0.18,
                    "ambiguous": False,
                }
            )
        result = Interlude.classify_modulation_windows(windows, "C", "major")
        self.assertEqual(result["modulation_windows"], {2, 3})
        self.assertEqual(result["transition_windows"], {1, 2, 3, 4})
        self.assertEqual(result["runs"][0]["scale_type"], "minor")
        self.assertEqual(result["runs"][0]["noncentered_window_ratio"], 1.0)

    def test_in_key_tonicization_is_not_labeled_as_modulation(self):
        windows = [
            {
                "window": number,
                "local_root": "G",
                "local_scale_type": "major",
                "local_key_correlation": 0.9,
                "local_key_correlation_margin": 0.25,
                "ambiguous": False,
                "tonally_centered": True,
            }
            for number in range(1, 9)
        ]

        result = Interlude.classify_modulation_windows(windows, "C", "major")

        self.assertEqual(result["modulation_windows"], set())
        self.assertEqual(result["runs"], [])

    def test_tonal_stability_rewards_centered_duration_and_long_runs(self):
        centered = [
            {
                "start": float(index),
                "end": float(index + 1),
                "ambiguous": False,
                "tonally_centered": True,
                "tonal_stability": 0.8,
            }
            for index in range(4)
        ]
        interrupted = [dict(window) for window in centered]
        for index in (1, 3):
            interrupted[index]["tonally_centered"] = False
            interrupted[index]["tonal_stability"] = 0.0

        centered_result = Interlude.summarize_tonal_stability(centered)
        interrupted_result = Interlude.summarize_tonal_stability(interrupted)

        self.assertGreater(
            centered_result["tonal_stability"],
            interrupted_result["tonal_stability"],
        )
        self.assertEqual(centered_result["longest_centered_run_ratio"], 1.0)
        self.assertEqual(interrupted_result["longest_centered_run_ratio"], 0.25)

    def test_ambiguous_harmony_chart_points_have_no_complexity_value(self):
        windows = [
            {
                "start": 0.0,
                "end": 2.0,
                "time_range": "0.00-2.00s",
                "harmonic_complexity": None,
                "diatonic_deviation": 0.4,
                "harmonic_movement": 0.2,
                "tonal_instability": 0.5,
                "voicing_density": 0.3,
                "ambiguous": True,
                "harmonic_evidence": "low-confidence harmonic evidence",
                "modulation_state": "ambiguous",
            }
        ]

        point = Interlude.build_harmonic_chart_points(windows)[0]

        self.assertIsNone(point["y"])
        self.assertTrue(point["ambiguous"])
        self.assertEqual(point["tooltip"], "Low-confidence harmonic evidence")


class TempoStabilityTests(unittest.TestCase):
    def test_stable_and_phase_shifted_beats_have_identical_stability(self):
        beats = np.arange(0.0, 16.5, 0.5)
        shifted = beats + 0.137
        stable = Interlude.analyze_tempo_stability(beats, 17.0, 120.0)
        phase_shifted = Interlude.analyze_tempo_stability(shifted, 17.2, 120.0)
        self.assertAlmostEqual(stable["overall_score"], 1.0)
        self.assertAlmostEqual(
            stable["overall_score"],
            phase_shifted["overall_score"],
        )

    def test_jittered_intervals_score_lower(self):
        intervals = np.tile([0.45, 0.55], 16)
        beats = np.concatenate(([0.0], np.cumsum(intervals)))
        result = Interlude.analyze_tempo_stability(beats, 17.0, 120.0)
        self.assertLess(result["overall_score"], 0.25)
        self.assertEqual(result["beat_interval_count"], len(intervals))
        self.assertIsNotNone(result["windows"][0]["local_bpm"])

    def test_insufficient_beats_return_no_stability(self):
        result = Interlude.analyze_tempo_stability(np.array([0.5]), 1.0, 120.0)
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result["beat_interval_count"], 0)


class PitchTrackingTests(unittest.TestCase):
    def test_pitch_scores_are_probability_weighted(self):
        summary = Interlude.summarize_pitch_estimates(
            np.ones(4, dtype=bool),
            np.ones(4, dtype=bool),
            np.array([1.0, 1.0, 1.0, 0.5]),
            np.array([1.0, 1.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 0.0, 100.0]),
        )
        self.assertAlmostEqual(summary["score"], 3.0 / 3.5)
        self.assertAlmostEqual(summary["effective_voiced_frames"], 3.5)
        self.assertEqual(summary["reliability"], "high")

    def test_reliability_thresholds_and_polyphony_cap(self):
        self.assertEqual(Interlude.classify_pitch_reliability(2.9, 10, 0.9), "insufficient")
        self.assertEqual(Interlude.classify_pitch_reliability(4.0, 100, 0.9), "low")
        self.assertEqual(Interlude.classify_pitch_reliability(20.0, 100, 0.7), "medium")
        self.assertEqual(Interlude.classify_pitch_reliability(40.0, 100, 0.7), "high")

        analysis = {
            "source": "full_mix_harmonic",
            "reliability": "high",
            "windows": [{"reliability": "medium"}],
        }
        capped = Interlude.cap_pitch_reliability_for_polyphony(analysis, True)
        self.assertEqual(capped["reliability"], "low")
        self.assertEqual(capped["windows"][0]["reliability"], "low")
        self.assertTrue(capped["windows"][0]["polyphony_limited"])
        self.assertTrue(capped["polyphony_limited"])

    def test_pyin_voiced_state_accepts_clean_tone_without_fixed_probability_gate(self):
        f0 = np.full(8, 440.0)
        voiced = np.ones(8, dtype=bool)
        probabilities = np.full(8, 0.55)
        with mock.patch.object(
            Interlude.librosa,
            "pyin",
            return_value=(f0, voiced, probabilities),
        ):
            result = Interlude.analyze_pitch_accuracy(
                np.ones(2048),
                22050,
                np.array([0.0, 1.0, 2.0]),
                2.0,
            )
        self.assertIsNotNone(result["overall_score"])
        self.assertEqual(result["valid_pitch_frames"], 8)
        self.assertAlmostEqual(result["mean_voiced_probability"], 0.55)
        self.assertEqual(result["windows"][0]["source"], "full_mix_harmonic")

    def test_pyin_silence_is_insufficient(self):
        f0 = np.full(8, np.nan)
        voiced = np.zeros(8, dtype=bool)
        probabilities = np.zeros(8)
        with mock.patch.object(
            Interlude.librosa,
            "pyin",
            return_value=(f0, voiced, probabilities),
        ):
            result = Interlude.analyze_pitch_accuracy(
                np.zeros(2048),
                22050,
                np.array([0.0, 1.0, 2.0]),
                2.0,
            )
        self.assertIsNone(result["overall_score"])
        self.assertEqual(result["reliability"], "insufficient")

    def test_low_reliability_pitch_is_not_selected_as_topline_weakness(self):
        summary = Interlude.build_topline_summary(
            {"overall_score": 0.8},
            {"overall_score": 0.1, "reliability": "low"},
            {"overall_score": 0.7},
            {"overall_score": 0.9},
        )
        self.assertIn("harmonic", summary.lower())


class VocalSeparationTests(unittest.TestCase):
    def test_success_loads_stem_and_cleans_temporary_directory(self):
        generated_directory = None

        def create_stem(command, **_kwargs):
            nonlocal generated_directory
            generated_directory = Path(command[command.index("-o") + 1])
            stem = generated_directory / Interlude.VOCAL_SEPARATION_MODEL / "track" / "vocals.wav"
            stem.parent.mkdir(parents=True)
            stem.write_bytes(b"stem")
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.object(Interlude, "vocal_separation_available", return_value=True), mock.patch.object(
            Interlude.subprocess,
            "run",
            side_effect=create_stem,
        ), mock.patch.object(
            Interlude.librosa,
            "load",
            return_value=(np.ones(32), 22050),
        ):
            signal, sample_rate = Interlude.separate_vocal_stem("song.wav", 10.0, 22050)

        self.assertEqual(sample_rate, 22050)
        self.assertEqual(len(signal), 32)
        self.assertIsNotNone(generated_directory)
        self.assertFalse(generated_directory.exists())

    def test_timeout_failure_and_malformed_output_are_explicit_and_cleaned(self):
        cases = [
            subprocess.TimeoutExpired(["demucs"], 600),
            subprocess.CalledProcessError(1, ["demucs"], stderr="model failed"),
            None,
        ]

        for side_effect in cases:
            with self.subTest(side_effect=type(side_effect).__name__):
                generated_directory = None

                def fail_or_return(command, **_kwargs):
                    nonlocal generated_directory
                    generated_directory = Path(command[command.index("-o") + 1])
                    if side_effect is not None:
                        raise side_effect
                    return subprocess.CompletedProcess(command, 0)

                with mock.patch.object(Interlude, "vocal_separation_available", return_value=True), mock.patch.object(
                    Interlude.subprocess,
                    "run",
                    side_effect=fail_or_return,
                ):
                    with self.assertRaises(Interlude.VocalSeparationError):
                        Interlude.separate_vocal_stem("song.wav", 10.0, 22050)

                self.assertIsNotNone(generated_directory)
                self.assertFalse(generated_directory.exists())

    def test_unavailable_separation_never_falls_back(self):
        with mock.patch.object(Interlude, "vocal_separation_available", return_value=False):
            with self.assertRaises(Interlude.VocalSeparationError):
                Interlude.separate_vocal_stem("song.wav", 10.0)


class ApiContractTests(unittest.TestCase):
    def test_old_clients_default_to_no_separation(self):
        request = api.AnalyzeRequest(filename="song.wav", file_data="AA==")
        self.assertFalse(request.separate_vocals)

    def test_options_expose_vocal_separation_capability(self):
        with mock.patch.object(Interlude, "vocal_separation_available", return_value=False):
            result = asyncio.run(api.options())
        self.assertFalse(result["capabilities"]["vocal_separation"]["available"])
        self.assertEqual(
            result["capabilities"]["vocal_separation"]["model"],
            Interlude.VOCAL_SEPARATION_MODEL,
        )

    def test_failed_separated_analysis_is_not_persisted(self):
        before = set(api.PROJECTS)
        request = api.AnalyzeRequest(
            filename="song.wav",
            file_data="AA==",
            separate_vocals=True,
        )

        async def fail_analysis(*_args, **_kwargs):
            raise Interlude.VocalSeparationError("separation failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            upload = Path(temp_dir) / "upload.wav"
            with mock.patch.object(Interlude, "vocal_separation_available", return_value=True), mock.patch.object(
                api,
                "safe_upload_path",
                return_value=upload,
            ), mock.patch.object(
                api,
                "decode_file",
                return_value=b"audio",
            ), mock.patch.object(
                api,
                "run_in_threadpool",
                side_effect=fail_analysis,
            ):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(api.analyze(request))

            self.assertEqual(raised.exception.status_code, 503)
            self.assertFalse(upload.exists())

        self.assertEqual(set(api.PROJECTS), before)

    def test_successful_analysis_retains_project_audio_and_delete_cleans_it(self):
        before = set(api.PROJECTS)
        request = api.AnalyzeRequest(filename="source.wav", file_data="AA==")
        result = {
            "project": {
                "created_at": "2026-01-01T00:00:00+00:00",
                "duration": 1.0,
                "sample_rate": 22050,
                "bpm": 120.0,
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            upload = temp_path / "upload.wav"
            media_dir = temp_path / "media"
            media_dir.mkdir()

            with mock.patch.object(api, "safe_upload_path", return_value=upload), mock.patch.object(
                api,
                "decode_file",
                return_value=b"audio bytes",
            ), mock.patch.object(
                api,
                "run_in_threadpool",
                new=mock.AsyncMock(return_value=result),
            ), mock.patch.object(
                api,
                "MEDIA_DIR",
                media_dir,
            ), mock.patch.object(
                api,
                "save_projects",
            ):
                response = asyncio.run(api.analyze(request))
                project_id = response["project"]["id"]
                audio_url = response["project"]["audio_url"]
                media_path = media_dir / Path(audio_url).name

                self.assertTrue(media_path.exists())
                self.assertFalse(upload.exists())
                self.assertEqual(media_path.read_bytes(), b"audio bytes")

                asyncio.run(api.delete_project(project_id))
                self.assertFalse(media_path.exists())
                self.assertNotIn(project_id, api.PROJECTS)

        self.assertEqual(set(api.PROJECTS), before)


if __name__ == "__main__":
    unittest.main()
