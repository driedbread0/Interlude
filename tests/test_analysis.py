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

    def test_modulation_requires_confidence_and_two_consecutive_windows(self):
        windows = [
            {
                "window": 1,
                "local_root": "G",
                "local_key_correlation": 0.75,
                "local_key_correlation_margin": 0.20,
            },
            {
                "window": 2,
                "local_root": "G",
                "local_key_correlation": 0.76,
                "local_key_correlation_margin": 0.21,
            },
            {
                "window": 3,
                "local_root": "D",
                "local_key_correlation": 0.59,
                "local_key_correlation_margin": 0.30,
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
        self.assertIn("Harmonic", summary)


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


if __name__ == "__main__":
    unittest.main()
