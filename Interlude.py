"""Core analysis pipeline for Interlude.

This file turns an uploaded song into the data structure consumed by the web app.
The rough flow is:

1. Load audio and estimate beat locations.
2. Run local analysis metrics: tempo, pitch, harmony, and dynamics.
3. Build frontend-friendly chart and visualization payloads.
4. Send the computed evidence plus the audio file to the OpenAI API.
5. Return one project-shaped result object for the FastAPI backend.

Most functions return dictionaries instead of custom classes because those
objects are sent directly through the API as JSON.
"""

from pathlib import Path
from datetime import datetime, timezone
import base64
import importlib.util
import os
import subprocess
import sys
import tempfile

import librosa
import numpy as np
import scipy.ndimage
from openai import OpenAI


# ---------------------------------------------------------------------------
# Configuration and environment
# ---------------------------------------------------------------------------

client = None

# Used only when running this file directly from the command line.
filename = "/Users/27PranT/Desktop/Billie Jean (Long Version) - Michael Jackson (128k).wav"

BEATS_PER_TEMPO_WINDOW = 8
BEATS_PER_PITCH_WINDOW = 16
BEATS_PER_HARMONY_WINDOW = 4
BEATS_PER_DYNAMICS_WINDOW = 8
DYNAMICS_CONTOUR_TOLERANCE = 0.25
TEMPO_LOG_TOLERANCE = 0.05
MIN_MODULATION_WINDOWS = 2
MIN_KEY_CORRELATION = 0.60
MIN_KEY_CORRELATION_MARGIN = 0.10
MIN_MODE_CORRELATION_ADVANTAGE = 0.10
MIN_KEY_PROFILE_VARIATION = 0.05
MIN_EFFECTIVE_PITCH_FRAMES = 3.0
MIN_LOCAL_KEY_CORRELATION = 0.55
MIN_LOCAL_KEY_MARGIN = 0.05
HARMONY_KEY_CONTEXT_WINDOWS = 2
CHROMA_SUSTAIN_FRAMES = 5
CHROMA_TRIM_FRACTION = 0.10
ACTIVE_PITCH_CLASS_THRESHOLD = 0.10
MIN_CHORD_SIMILARITY = 0.62
MIN_CHORD_MARGIN = 0.015
CHORD_COLOR_SELECTION_PENALTY = 0.08
CHORD_CHROMA_FMIN = "C2"
CHORD_CHROMA_OCTAVES = 4
MAX_HARMONIC_CHANGES_PER_BAR = 4.0
MAX_MODULATION_DEVIATION_REDUCTION = 0.55
MIN_MODULATION_CONFIDENCE = 0.30
MIN_MODULATION_NONCENTERED_RATIO = 0.50
HARMONIC_SIGMOID_CENTER = 0.24
HARMONIC_SIGMOID_SCALE = 0.10
HARMONIC_HOTSPOT_THRESHOLD = 0.60

HARMONIC_COMPLEXITY_WEIGHTS = {
    "diatonic_deviation": 0.08,
    "harmonic_movement": 0.34,
    "tonal_instability": 0.07,
    "voicing_density": 0.03,
    "modulation_load": 0.16,
    "harmonic_color": 0.32,
}

VOCAL_SEPARATION_MODEL = "htdemucs"

USER_ROOT = None
USER_SCALE_TYPE = None

DEFAULT_TEXT_FEEDBACK_MODEL = "gpt-5.5"
DEFAULT_AUDIO_FEEDBACK_MODEL = "gpt-audio-1.5"
SUPPORTED_OPENAI_AUDIO_INPUTS = {
    ".mp3": "mp3",
    ".wav": "wav",
}


def load_local_env(env_path=None):
    """Load key/value pairs from a local .env file if they are not set already.

    This keeps local API credentials out of source code. The app still respects
    real environment variables first, which is better for deployed environments.
    """
    env_path = env_path or Path(__file__).with_name(".env")

    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value


# ---------------------------------------------------------------------------
# Music theory lookup tables
# ---------------------------------------------------------------------------

NOTE_TO_INDEX = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

INDEX_TO_NOTE = {
    0: "C",
    1: "C#",
    2: "D",
    3: "Eb",
    4: "E",
    5: "F",
    6: "F#",
    7: "G",
    8: "Ab",
    9: "A",
    10: "Bb",
    11: "B",
}

SCALE_PATTERNS = {
    "major": np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1]),
    "minor": np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0]),
    "dorian": np.array([1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0]),
    "phrygian": np.array([1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0]),
    "lydian": np.array([1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1]),
    "mixolydian": np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0]),
    "locrian": np.array([1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0]),
    "harmonic_minor": np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1]),
    "melodic_minor": np.array([1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1]),
}

KRUMHANSL_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
KRUMHANSL_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

CLASSICAL_KEY_PROFILES = {
    "major": KRUMHANSL_MAJOR_PROFILE,
    "minor": KRUMHANSL_MINOR_PROFILE,
}

# These profiles are guarded extensions of the empirical major/minor profiles,
# not additional Krumhansl probe-tone profiles. Each swap moves the tonal
# weight of a natural scale degree to the pitch that defines the target mode.
DERIVED_MODE_CONFIG = {
    "dorian": {
        "parent": "minor",
        "swaps": ((8, 9),),
        "evidence": ((9, 8),),
    },
    "phrygian": {
        "parent": "minor",
        "swaps": ((1, 2),),
        "evidence": ((1, 2),),
    },
    "lydian": {
        "parent": "major",
        "swaps": ((5, 6),),
        "evidence": ((6, 5),),
    },
    "mixolydian": {
        "parent": "major",
        "swaps": ((10, 11),),
        "evidence": ((10, 11),),
    },
    "locrian": {
        "parent": "minor",
        "swaps": ((1, 2), (6, 7)),
        "evidence": ((1, 2), (6, 7)),
    },
}

CHORD_QUALITIES = {
    "major": {"intervals": ((0, 1.0), (4, 0.9), (7, 0.75)), "color": 0.00},
    "minor": {"intervals": ((0, 1.0), (3, 0.9), (7, 0.75)), "color": 0.00},
    "sus2": {"intervals": ((0, 1.0), (2, 0.85), (7, 0.75)), "color": 0.08},
    "sus4": {"intervals": ((0, 1.0), (5, 0.85), (7, 0.75)), "color": 0.08},
    "augmented": {"intervals": ((0, 1.0), (4, 0.9), (8, 0.8)), "color": 0.35},
    "diminished": {"intervals": ((0, 1.0), (3, 0.9), (6, 0.8)), "color": 0.35},
    "major6": {
        "intervals": ((0, 1.0), (4, 0.9), (7, 0.7), (9, 0.65)),
        "color": 0.24,
    },
    "minor6": {
        "intervals": ((0, 1.0), (3, 0.9), (7, 0.7), (9, 0.65)),
        "color": 0.30,
    },
    "dominant7": {
        "intervals": ((0, 1.0), (4, 0.9), (7, 0.65), (10, 0.8)),
        "color": 0.36,
    },
    "major7": {
        "intervals": ((0, 1.0), (4, 0.9), (7, 0.65), (11, 0.8)),
        "color": 0.44,
    },
    "minor7": {
        "intervals": ((0, 1.0), (3, 0.9), (7, 0.65), (10, 0.8)),
        "color": 0.38,
    },
    "minor_major7": {
        "intervals": ((0, 1.0), (3, 0.9), (7, 0.65), (11, 0.8)),
        "color": 0.72,
    },
    "half_diminished7": {
        "intervals": ((0, 1.0), (3, 0.9), (6, 0.75), (10, 0.8)),
        "color": 0.62,
    },
    "diminished7": {
        "intervals": ((0, 1.0), (3, 0.9), (6, 0.75), (9, 0.8)),
        "color": 0.68,
    },
    "add9": {
        "intervals": ((0, 1.0), (2, 0.72), (4, 0.9), (7, 0.65)),
        "color": 0.34,
    },
    "minor_add9": {
        "intervals": ((0, 1.0), (2, 0.72), (3, 0.9), (7, 0.65)),
        "color": 0.42,
    },
    "dominant9": {
        "intervals": ((0, 1.0), (2, 0.7), (4, 0.9), (7, 0.55), (10, 0.8)),
        "color": 0.64,
    },
    "major9": {
        "intervals": ((0, 1.0), (2, 0.7), (4, 0.9), (7, 0.55), (11, 0.8)),
        "color": 0.68,
    },
    "minor9": {
        "intervals": ((0, 1.0), (2, 0.7), (3, 0.9), (7, 0.55), (10, 0.8)),
        "color": 0.70,
    },
    "dominant_b9": {
        "intervals": ((0, 1.0), (1, 0.75), (4, 0.9), (7, 0.5), (10, 0.8)),
        "color": 0.92,
    },
    "dominant_sharp9": {
        "intervals": ((0, 1.0), (3, 0.75), (4, 0.9), (7, 0.5), (10, 0.8)),
        "color": 0.96,
    },
}


def chord_movement_family(quality):
    """Collapse extensions to the root/triad identity used for movement."""
    if quality in {
        "major",
        "major6",
        "dominant7",
        "major7",
        "add9",
        "dominant9",
        "major9",
        "dominant_b9",
        "dominant_sharp9",
    }:
        return "major"

    if quality in {
        "minor",
        "minor6",
        "minor7",
        "minor_major7",
        "minor_add9",
        "minor9",
    }:
        return "minor"

    if quality in {"diminished", "half_diminished7", "diminished7"}:
        return "diminished"

    if quality in {"sus2", "sus4"}:
        return "suspended"

    return quality


class AnalysisInputError(ValueError):
    """Raised when uploaded audio cannot support a meaningful analysis."""


class VocalSeparationError(RuntimeError):
    """Raised when explicitly requested vocal separation cannot complete."""


# ---------------------------------------------------------------------------
# OpenAI API helpers
# ---------------------------------------------------------------------------

def get_client():
    """Create the OpenAI client lazily so local analysis can still run offline."""
    global client

    if client is None:
        load_local_env()
        client = OpenAI()  # reads OPENAI_API_KEY from the environment

    return client


def get_text_feedback_model():
    """Read the text-only feedback model, allowing a local .env override."""
    load_local_env()
    return os.getenv("INTERLUDE_TEXT_MODEL", DEFAULT_TEXT_FEEDBACK_MODEL)


def get_audio_feedback_model():
    """Read the audio-capable feedback model, allowing a local .env override."""
    load_local_env()
    return os.getenv("INTERLUDE_AUDIO_MODEL", DEFAULT_AUDIO_FEEDBACK_MODEL)


def encode_audio_input(song_path):
    """Return a Chat Completions audio content part for supported files.

    The Responses API `input_file` path is for supported document/context file
    types, not raw audio such as `.wav`. For song listening context, the audio
    must be base64 encoded and passed as `input_audio` to an audio-capable
    Chat Completions model.
    """
    song_path = Path(song_path)
    audio_format = SUPPORTED_OPENAI_AUDIO_INPUTS.get(song_path.suffix.lower())

    if audio_format is None:
        return None

    encoded_audio = base64.b64encode(song_path.read_bytes()).decode("utf-8")

    return {
        "type": "input_audio",
        "input_audio": {
            "data": encoded_audio,
            "format": audio_format,
        },
    }


def extract_chat_completion_text(completion):
    """Safely extract text from an audio-capable chat completion."""
    message = completion.choices[0].message

    if message.content:
        return message.content

    audio = getattr(message, "audio", None)
    transcript = getattr(audio, "transcript", None) if audio else None

    if transcript:
        return transcript

    return "The OpenAI API returned a response, but Interlude could not find text feedback in it."


def request_music_feedback(prompt, song_path):
    """Ask OpenAI for feedback using audio input when the file type supports it."""
    audio_part = encode_audio_input(song_path)

    if audio_part is not None:
        completion = get_client().chat.completions.create(
            model=get_audio_feedback_model(),
            modalities=["text"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        audio_part,
                    ],
                }
            ],
        )
        return extract_chat_completion_text(completion)

    fallback_prompt = f"""{prompt}

Audio attachment note:
The uploaded file type is not currently sent as direct audio input to OpenAI by this prototype. Use the computed metrics as the primary evidence.
"""

    response = get_client().responses.create(
        model=get_text_feedback_model(),
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": fallback_prompt},
                ],
            }
        ],
    )
    return response.output_text


# ---------------------------------------------------------------------------
# Shared scoring and beat-window helpers
# ---------------------------------------------------------------------------

def get_scale_mask(root, scale_type):
    """Return a 12-note binary mask for a root plus scale/mode."""
    if scale_type not in SCALE_PATTERNS:
        supported_scales = ", ".join(sorted(SCALE_PATTERNS))
        raise ValueError(f"scale_type must be one of: {supported_scales}")

    root_idx = NOTE_TO_INDEX[root]
    return np.roll(SCALE_PATTERNS[scale_type], root_idx)


def beat_windows(beat_times, duration, beats_per_window):
    """Create beat-synchronous analysis windows across the song."""
    if len(beat_times) < 2:
        return [(0, 0.0, duration, "0.00-%.2fs" % duration)]

    windows = []
    for start_idx in range(0, len(beat_times) - 1, beats_per_window):
        end_idx = min(start_idx + beats_per_window, len(beat_times) - 1)
        start_time = float(beat_times[start_idx])
        end_time = float(beat_times[end_idx])

        if end_time <= start_time:
            continue

        windows.append(
            (
                len(windows) + 1,
                start_time,
                end_time,
                f"{start_time:.2f}-{end_time:.2f}s",
            )
        )

    return windows


def tempo_interval_evidence(intervals, target_interval):
    """Return log-ratio errors and Gaussian stability evidence for beat gaps."""
    intervals = np.asarray(intervals, dtype=float)
    valid = np.isfinite(intervals) & (intervals > 0)

    if target_interval is None or target_interval <= 0 or not np.any(valid):
        return np.array([]), np.array([])

    log_errors = np.abs(np.log(intervals[valid] / target_interval))
    scores = np.exp(-0.5 * (log_errors / TEMPO_LOG_TOLERANCE) ** 2)
    return log_errors, scores


# ---------------------------------------------------------------------------
# Metric analyzers
# ---------------------------------------------------------------------------

def analyze_tempo_stability(beat_times, duration, global_bpm):
    """Score beat-rate stability from inter-beat interval consistency.

    Beat locations may follow local audio evidence, but a stable performance
    should keep consecutive beat intervals close to the global target period.
    Log-ratio errors are symmetric for proportionally fast and slow intervals
    and do not depend on the absolute phase of an onset detector.
    """
    beat_times = np.asarray(beat_times, dtype=float)
    beat_intervals = np.diff(beat_times)
    bpm_value = float(np.atleast_1d(global_bpm)[0]) if np.size(global_bpm) else 0.0
    target_interval = 60.0 / bpm_value if bpm_value > 0 else None

    if target_interval is None and len(beat_intervals):
        valid_intervals = beat_intervals[beat_intervals > 0]
        target_interval = (
            float(np.median(valid_intervals)) if len(valid_intervals) else None
        )

    windows = beat_windows(beat_times, duration, BEATS_PER_TEMPO_WINDOW)
    tempo_windows = []
    interval_starts = beat_times[:-1]

    for window_number, start_time, end_time, label in windows:
        in_window = (interval_starts >= start_time) & (interval_starts < end_time)
        local_intervals = beat_intervals[in_window]
        local_errors, local_scores = tempo_interval_evidence(
            local_intervals,
            target_interval,
        )
        score = float(np.mean(local_scores)) if len(local_scores) else None
        local_bpm = (
            float(60.0 / np.median(local_intervals[local_intervals > 0]))
            if np.any(local_intervals > 0)
            else None
        )

        tempo_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "score": score,
                "local_bpm": local_bpm,
                "beat_interval_count": int(len(local_scores)),
                "mean_log_interval_error": (
                    float(np.mean(local_errors)) if len(local_errors) > 0 else None
                ),
            }
        )

    all_errors, all_scores = tempo_interval_evidence(
        beat_intervals,
        target_interval,
    )
    overall_score = float(np.mean(all_scores)) if len(all_scores) else None
    median_bpm = (
        float(60.0 / np.median(beat_intervals[beat_intervals > 0]))
        if np.any(beat_intervals > 0)
        else None
    )
    unstable_windows = [
        window
        for window in tempo_windows
        if window["score"] is not None and window["score"] < 0.72
    ]

    return {
        "overall_score": overall_score,
        "windows": tempo_windows,
        "unstable_windows": unstable_windows,
        "global_bpm": bpm_value,
        "median_bpm": median_bpm,
        "target_interval": target_interval,
        "mean_log_interval_error": (
            float(np.mean(all_errors)) if len(all_errors) else None
        ),
        "beat_count": int(len(beat_times)),
        "beat_interval_count": int(len(all_scores)),
        "log_tolerance": TEMPO_LOG_TOLERANCE,
    }


def nearest_equal_tempered_errors(frequencies):
    """Return cents error from the nearest equal-tempered pitch."""
    valid_frequencies = frequencies[~np.isnan(frequencies)]

    if len(valid_frequencies) == 0:
        return np.array([])

    midi_values = librosa.hz_to_midi(valid_frequencies)
    nearest_midi_values = np.round(midi_values)
    return np.abs((midi_values - nearest_midi_values) * 100)


def vibrato_tolerant_pitch_errors(f0):
    """Estimate pitch error while reducing penalties for vibrato and bends."""
    valid = ~np.isnan(f0)

    if not np.any(valid):
        return np.full_like(f0, np.nan)

    frame_indices = np.arange(len(f0))
    interpolated_f0 = np.interp(frame_indices, frame_indices[valid], f0[valid])
    smoothed_f0 = scipy.ndimage.median_filter(interpolated_f0, size=7)

    raw_errors = np.full_like(f0, np.nan, dtype=float)
    smoothed_errors = np.full_like(f0, np.nan, dtype=float)
    raw_errors[valid] = nearest_equal_tempered_errors(f0[valid])
    smoothed_errors[valid] = nearest_equal_tempered_errors(smoothed_f0[valid])

    # Use whichever view is kinder: raw pitch or short-window smoothed pitch.
    tolerant_errors = np.minimum(raw_errors, smoothed_errors)

    # Fast but continuous pitch motion is likely expressive bending, so soften it.
    smoothed_midi = librosa.hz_to_midi(smoothed_f0)
    cents_motion = np.abs(np.gradient(smoothed_midi) * 100)
    bend_like_motion = cents_motion > 10
    tolerant_errors[bend_like_motion & valid] *= 0.65

    return np.minimum(tolerant_errors, 50)


def classify_pitch_reliability(
    effective_voiced_frames,
    total_frames,
    mean_voiced_probability,
):
    """Classify whether pYIN supplied enough trustworthy voiced evidence."""
    effective_ratio = (
        float(effective_voiced_frames / total_frames) if total_frames > 0 else 0.0
    )

    if effective_voiced_frames < MIN_EFFECTIVE_PITCH_FRAMES:
        return "insufficient"

    if effective_ratio < 0.10 or mean_voiced_probability < 0.20:
        return "low"

    if effective_ratio < 0.30 or mean_voiced_probability < 0.50:
        return "medium"

    return "high"


def summarize_pitch_estimates(
    frame_mask,
    valid,
    voiced_prob,
    pitch_scores,
    pitch_errors,
):
    """Aggregate probability-weighted pitch evidence for one frame region."""
    frame_mask = np.asarray(frame_mask, dtype=bool)
    selected = frame_mask & valid
    total_frames = int(np.sum(frame_mask))
    valid_count = int(np.sum(selected))
    weights = np.clip(
        np.nan_to_num(voiced_prob[selected], nan=0.0),
        0.0,
        1.0,
    )
    effective_frames = float(np.sum(weights))
    mean_probability = float(np.mean(weights)) if valid_count else 0.0
    reliability = classify_pitch_reliability(
        effective_frames,
        total_frames,
        mean_probability,
    )

    if reliability == "insufficient" or not np.any(weights > 0):
        score = None
        mean_error = None
    else:
        score = float(np.average(pitch_scores[selected], weights=weights))
        mean_error = float(np.average(pitch_errors[selected], weights=weights))

    return {
        "score": score,
        "valid_pitch_frames": valid_count,
        "effective_voiced_frames": effective_frames,
        "voiced_frame_ratio": (
            float(valid_count / total_frames) if total_frames else 0.0
        ),
        "effective_voiced_ratio": (
            float(effective_frames / total_frames) if total_frames else 0.0
        ),
        "mean_voiced_probability": mean_probability,
        "mean_abs_cents_error": mean_error,
        "reliability": reliability,
    }


def cap_pitch_reliability_for_polyphony(pitch_analysis, polyphony_warning):
    """Prevent full-mix pYIN evidence from overclaiming dense material."""
    if not polyphony_warning or pitch_analysis.get("source") != "full_mix_harmonic":
        return pitch_analysis

    rank = {"insufficient": 0, "low": 1, "medium": 2, "high": 3}

    if rank.get(pitch_analysis.get("reliability"), 0) > rank["low"]:
        pitch_analysis["reliability"] = "low"

    for window in pitch_analysis.get("windows", []):
        if rank.get(window.get("reliability"), 0) > rank["low"]:
            window["reliability"] = "low"
        window["polyphony_limited"] = True

    pitch_analysis["polyphony_limited"] = True
    return pitch_analysis


def analyze_pitch_accuracy(
    y,
    sr,
    beat_times,
    duration,
    source="full_mix_harmonic",
):
    """Score probability-weighted monophonic pitch over phrase windows."""
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
    )
    frame_times = librosa.times_like(f0, sr=sr)
    voiced_prob = np.nan_to_num(voiced_prob, nan=0.0)
    valid = np.isfinite(f0) & np.asarray(voiced_flag, dtype=bool)
    pitch_errors = vibrato_tolerant_pitch_errors(f0)
    pitch_scores = np.full_like(pitch_errors, np.nan, dtype=float)
    pitch_scores[valid] = np.exp(-pitch_errors[valid] / 100)
    windows = beat_windows(beat_times, duration, BEATS_PER_PITCH_WINDOW)

    pitch_windows = []
    for window_number, start_time, end_time, label in windows:
        in_window = (frame_times >= start_time) & (frame_times < end_time)
        summary = summarize_pitch_estimates(
            in_window,
            valid,
            voiced_prob,
            pitch_scores,
            pitch_errors,
        )

        pitch_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "source": source,
                "polyphony_limited": False,
                **summary,
            }
        )

    overall = summarize_pitch_estimates(
        np.ones(len(f0), dtype=bool),
        valid,
        voiced_prob,
        pitch_scores,
        pitch_errors,
    )
    weak_windows = [
        window
        for window in pitch_windows
        if window["score"] is not None and window["score"] < 0.72
    ]

    return {
        "overall_score": overall["score"],
        "windows": pitch_windows,
        "weak_windows": weak_windows,
        "source": source,
        "polyphony_limited": False,
        **{key: value for key, value in overall.items() if key != "score"},
    }


def analyze_dynamics(y, sr, beat_times, duration, hop_length=512):
    """Score how cleanly local RMS follows a simple energy contour.

    A section can be dynamically controlled while staying steady, fading in, or
    fading out. For that reason, each beat window is compared against its own
    linear RMS trend instead of being compared against a flat loudness target.
    """
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    frame_times = librosa.times_like(rms, sr=sr, hop_length=hop_length)
    windows = beat_windows(beat_times, duration, BEATS_PER_DYNAMICS_WINDOW)
    global_energy_reference = float(np.percentile(rms, 95)) if len(rms) else 0.0
    dynamics_windows = []

    for window_number, start_time, end_time, label in windows:
        in_window = (frame_times >= start_time) & (frame_times < end_time)
        local_rms = rms[in_window]

        if len(local_rms) < 2:
            variation = None
            mean_rms = None
            trend_slope = None
            trend_start = None
            trend_end = None
            trend_residual = None
            relative_residual = None
            trend_direction = None
            score = None
        else:
            local_rms = local_rms.astype(float)
            filter_size = min(
                len(local_rms),
                max(3, int(round(len(local_rms) / 4))),
            )

            if filter_size % 2 == 0:
                filter_size -= 1

            # Smooth over a meaningful part of the window so the trend follows
            # the volume envelope, not every drum transient or waveform pulse.
            smoothed_rms = (
                scipy.ndimage.median_filter(local_rms, size=filter_size)
                if filter_size >= 3
                else local_rms
            )
            x = np.linspace(0.0, 1.0, len(smoothed_rms))
            trend_slope, trend_intercept = np.polyfit(x, smoothed_rms, 1)
            fitted_rms = trend_slope * x + trend_intercept
            trend_residual = float(np.sqrt(np.mean((smoothed_rms - fitted_rms) ** 2)))
            variation = float(np.max(smoothed_rms) - np.min(smoothed_rms))
            mean_rms = float(np.mean(smoothed_rms))
            amplitude_scale = max(
                float(np.percentile(smoothed_rms, 95)),
                variation,
                global_energy_reference * 0.05,
                1e-8,
            )
            relative_residual = float(trend_residual / amplitude_scale)
            score = float(1 / (1 + relative_residual / DYNAMICS_CONTOUR_TOLERANCE))
            trend_start = float(fitted_rms[0])
            trend_end = float(fitted_rms[-1])

            if abs(trend_slope) < amplitude_scale * 0.05:
                trend_direction = "steady"
            elif trend_slope > 0:
                trend_direction = "rising"
            else:
                trend_direction = "falling"

        dynamics_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "score": score,
                "raw_variation": variation,
                "mean_rms": mean_rms,
                "trend_slope": float(trend_slope) if trend_slope is not None else None,
                "trend_start": trend_start,
                "trend_end": trend_end,
                "trend_direction": trend_direction,
                "trend_residual": trend_residual,
                "relative_residual": relative_residual,
            }
        )

    contour_scores = [
        window["score"]
        for window in dynamics_windows
        if window["score"] is not None
    ]

    return {
        "overall_score": (
            float(np.mean(contour_scores)) if contour_scores else None
        ),
        "windows": dynamics_windows,
    }


# ---------------------------------------------------------------------------
# Harmony, key detection, and modulation helpers
# ---------------------------------------------------------------------------

def detect_polyphonic_density(chroma):
    """Estimate whether many notes are active at once in the chroma signal."""
    chroma_max = np.max(chroma, axis=0)
    active_notes = np.zeros(chroma.shape[1], dtype=int)
    active = chroma_max > 0
    active_notes[active] = np.sum(chroma[:, active] > (0.2 * chroma_max[active]), axis=0)
    polyphonic_ratio = float(np.mean(active_notes >= 3)) if chroma.shape[1] else 0.0

    return {
        "polyphonic_ratio": polyphonic_ratio,
        "warning": polyphonic_ratio > 0.35,
    }


def key_fit(chroma_profile, root, scale_type):
    """Return how much chroma energy belongs to a candidate key/mode."""
    total = np.sum(chroma_profile)

    if total == 0:
        return 0.0

    mask = get_scale_mask(root, scale_type)
    return float(np.sum(chroma_profile * mask) / total)


def validate_key_profile(chroma_profile):
    """Return a finite 12-bin PCP or reject tonally empty evidence."""
    profile = np.asarray(chroma_profile, dtype=float).reshape(-1)
    mean_magnitude = np.mean(np.abs(profile)) if profile.size else 0.0
    normalized_variation = (
        float(np.std(profile) / mean_magnitude) if mean_magnitude > 0 else 0.0
    )

    if (
        profile.shape != (12,)
        or not np.all(np.isfinite(profile))
        or np.sum(np.abs(profile)) <= 1e-8
        or normalized_variation < MIN_KEY_PROFILE_VARIATION
    ):
        raise AnalysisInputError(
            "The audio does not contain enough tonal information for key detection."
        )

    return profile


def build_key_chroma_profile(y, sr):
    """Build the full-track PCP used only for key and mode detection."""
    y = np.asarray(y, dtype=float)

    if not len(y) or np.max(np.abs(y)) <= 1e-6:
        raise AnalysisInputError(
            "The audio is silent or too quiet to analyze reliably."
        )

    trimmed, _ = librosa.effects.trim(y)

    if not len(trimmed) or np.max(np.abs(trimmed)) <= 1e-6:
        raise AnalysisInputError(
            "The audio is silent or too quiet to analyze reliably."
        )

    try:
        chroma = librosa.feature.chroma_cqt(y=trimmed, sr=sr)
    except Exception as exc:
        raise AnalysisInputError(
            "The audio is too short or lacks enough pitched content for key detection."
        ) from exc

    return validate_key_profile(np.mean(chroma, axis=1))


def pearson_profile_correlation(chroma_profile, key_profile):
    """Calculate Pearson correlation without emitting flat-profile warnings."""
    profile = validate_key_profile(chroma_profile)
    key_profile = np.asarray(key_profile, dtype=float)
    centered_profile = profile - np.mean(profile)
    centered_key = key_profile - np.mean(key_profile)
    denominator = np.linalg.norm(centered_profile) * np.linalg.norm(centered_key)

    if denominator <= 1e-12:
        return -1.0

    return float(np.dot(centered_profile, centered_key) / denominator)


def derived_mode_profile(mode):
    """Return one guarded modal extension of a Krumhansl parent profile."""
    config = DERIVED_MODE_CONFIG[mode]
    profile = CLASSICAL_KEY_PROFILES[config["parent"]].copy()

    for first, second in config["swaps"]:
        profile[first], profile[second] = profile[second], profile[first]

    return profile


def rank_classical_keys(chroma_profile):
    """Rank the 24 canonical Krumhansl major/minor candidates."""
    profile = validate_key_profile(chroma_profile)
    candidates = []

    for root_index, root in INDEX_TO_NOTE.items():
        for scale_type, key_profile in CLASSICAL_KEY_PROFILES.items():
            candidates.append(
                {
                    "root": root,
                    "scale_type": scale_type,
                    "correlation": pearson_profile_correlation(
                        profile,
                        np.roll(key_profile, root_index),
                    ),
                }
            )

    return sorted(candidates, key=lambda item: item["correlation"], reverse=True)


def detect_key_and_mode(chroma_profile, allow_derived_modes=True):
    """Run Krumhansl-Schmuckler with conservative same-tonic mode promotion."""
    profile = validate_key_profile(chroma_profile)
    classical_candidates = rank_classical_keys(profile)
    classical_best = classical_candidates[0]
    selected = classical_best
    runner_up = classical_candidates[1]
    root_index = NOTE_TO_INDEX[classical_best["root"]]
    viable_modes = []

    if allow_derived_modes:
        for mode, config in DERIVED_MODE_CONFIG.items():
            if config["parent"] != classical_best["scale_type"]:
                continue

            correlation = pearson_profile_correlation(
                profile,
                np.roll(derived_mode_profile(mode), root_index),
            )
            has_characteristic_evidence = all(
                profile[(root_index + altered) % 12]
                > profile[(root_index + displaced) % 12]
                for altered, displaced in config["evidence"]
            )

            if has_characteristic_evidence:
                viable_modes.append(
                    {
                        "root": classical_best["root"],
                        "scale_type": mode,
                        "correlation": correlation,
                    }
                )

        if viable_modes:
            modal_best = max(viable_modes, key=lambda item: item["correlation"])
            if (
                modal_best["correlation"] >= MIN_KEY_CORRELATION
                and modal_best["correlation"] - classical_best["correlation"]
                >= MIN_MODE_CORRELATION_ADVANTAGE
            ):
                selected = modal_best
                runner_up = max(
                    [classical_best, *[item for item in viable_modes if item is not modal_best]],
                    key=lambda item: item["correlation"],
                )

    return {
        **selected,
        "correlation_margin": float(
            max(0.0, selected["correlation"] - runner_up["correlation"])
        ),
        "algorithm": "krumhansl_schmuckler_extended_v1",
        "profile_type": (
            "derived_mode"
            if selected["scale_type"] in DERIVED_MODE_CONFIG
            else "canonical"
        ),
    }


def trimmed_mean(values, trim_fraction=CHROMA_TRIM_FRACTION, axis=-1):
    """Aggregate an array while discarding equal low/high transient tails."""
    values = np.asarray(values, dtype=float)

    if values.shape[axis] == 0:
        output_shape = list(values.shape)
        del output_shape[axis]
        return np.full(output_shape, np.nan)

    sorted_values = np.sort(values, axis=axis)
    trim_count = int(np.floor(values.shape[axis] * trim_fraction))

    if trim_count == 0 or trim_count * 2 >= values.shape[axis]:
        return np.mean(sorted_values, axis=axis)

    keep_indices = np.arange(trim_count, values.shape[axis] - trim_count)
    return np.mean(np.take(sorted_values, keep_indices, axis=axis), axis=axis)


def preprocess_harmonic_chroma(chroma):
    """Normalize chroma per frame and favor pitch classes sustained over time."""
    chroma = np.clip(np.nan_to_num(chroma, nan=0.0), 0.0, None)
    frame_totals = np.sum(chroma, axis=0, keepdims=True)
    normalized = np.divide(
        chroma,
        frame_totals,
        out=np.zeros_like(chroma, dtype=float),
        where=frame_totals > 1e-12,
    )
    active = normalized >= ACTIVE_PITCH_CLASS_THRESHOLD
    sustain_support = scipy.ndimage.uniform_filter1d(
        active.astype(float),
        size=CHROMA_SUSTAIN_FRAMES,
        axis=1,
        mode="nearest",
    )
    sustain_weighted = normalized * (0.65 + 0.70 * sustain_support)
    weighted_totals = np.sum(sustain_weighted, axis=0, keepdims=True)
    return np.divide(
        sustain_weighted,
        weighted_totals,
        out=np.zeros_like(sustain_weighted),
        where=weighted_totals > 1e-12,
    )


def aggregate_chroma_profile(chroma):
    """Return a normalized trimmed-mean pitch-class profile."""
    if chroma.shape[1] == 0:
        return np.zeros(12)

    profile = np.nan_to_num(trimmed_mean(chroma, axis=1), nan=0.0)
    total = np.sum(profile)
    return profile / total if total > 1e-12 else np.zeros(12)


def estimate_voicing_density(chroma):
    """Estimate simultaneous pitch-class count separately from chromaticity."""
    if chroma.shape[1] == 0:
        return {
            "voicing_density": None,
            "estimated_active_pitch_classes": None,
            "threshold_active_pitch_classes": None,
        }

    frame_totals = np.sum(chroma, axis=0)
    valid = frame_totals > 1e-12

    if not np.any(valid):
        return {
            "voicing_density": None,
            "estimated_active_pitch_classes": None,
            "threshold_active_pitch_classes": None,
        }

    local = chroma[:, valid]
    frame_max = np.max(local, axis=0, keepdims=True)
    active = (local >= ACTIVE_PITCH_CLASS_THRESHOLD) & (local >= 0.25 * frame_max)
    active_counts = np.maximum(1.0, np.sum(active, axis=0).astype(float))
    entropy = -np.sum(local * np.log(np.maximum(local, 1e-12)), axis=0)
    effective_counts = np.exp(entropy)
    estimated_counts = 0.65 * active_counts + 0.35 * effective_counts
    estimated_count = float(trimmed_mean(estimated_counts))
    threshold_count = float(trimmed_mean(active_counts))

    return {
        "voicing_density": float(np.clip((estimated_count - 1.0) / 7.0, 0.0, 1.0)),
        "estimated_active_pitch_classes": estimated_count,
        "threshold_active_pitch_classes": threshold_count,
    }


def build_chord_templates():
    """Create normalized triad, seventh, added-note, and altered templates."""
    templates = []

    for root_index, root in INDEX_TO_NOTE.items():
        for quality, configuration in CHORD_QUALITIES.items():
            template = np.zeros(12)

            for interval, weight in configuration["intervals"]:
                template[(root_index + interval) % 12] = weight

            template /= np.linalg.norm(template)
            templates.append(
                {
                    "root": root,
                    "quality": quality,
                    "label": f"{root}:{quality}",
                    "movement_family": chord_movement_family(quality),
                    "movement_label": f"{root}:{chord_movement_family(quality)}",
                    "color_complexity": configuration["color"],
                    "template": template,
                }
            )

    return templates


CHORD_TEMPLATES = build_chord_templates()


def estimate_chord_region(chroma_profile):
    """Estimate one chord region with guarded quality and color evidence."""
    profile = np.asarray(chroma_profile, dtype=float)
    magnitude = np.linalg.norm(profile)

    if profile.shape != (12,) or magnitude <= 1e-12:
        return {
            "label": None,
            "root": None,
            "quality": None,
            "similarity": 0.0,
            "margin": 0.0,
            "quality_confidence": 0.0,
            "color_complexity": 0.0,
            "color_evidence": 0.0,
            "ambiguous": True,
        }

    normalized = profile / magnitude
    candidates = sorted(
        (
            {
                **{key: value for key, value in candidate.items() if key != "template"},
                "similarity": float(np.dot(normalized, candidate["template"])),
                "selection_score": float(
                    np.dot(normalized, candidate["template"])
                    - CHORD_COLOR_SELECTION_PENALTY
                    * candidate["color_complexity"]
                ),
            }
            for candidate in CHORD_TEMPLATES
        ),
        key=lambda item: item["selection_score"],
        reverse=True,
    )
    best, runner_up = candidates[:2]
    margin = float(max(0.0, best["selection_score"] - runner_up["selection_score"]))
    ambiguous = (
        best["similarity"] < MIN_CHORD_SIMILARITY
        or margin < MIN_CHORD_MARGIN
    )
    similarity_confidence = float(
        np.clip(
            (best["similarity"] - MIN_CHORD_SIMILARITY)
            / max(1e-12, 1.0 - MIN_CHORD_SIMILARITY),
            0.0,
            1.0,
        )
    )
    margin_confidence = float(np.clip(margin / 0.08, 0.0, 1.0))
    quality_confidence = float(
        0.65 * similarity_confidence + 0.35 * margin_confidence
    )
    color_evidence = (
        float(best["color_complexity"] * (0.40 + 0.60 * quality_confidence))
        if not ambiguous
        else 0.0
    )
    return {
        **best,
        "margin": margin,
        "quality_confidence": quality_confidence,
        "color_evidence": color_evidence,
        "ambiguous": ambiguous,
    }


def build_chord_regions(chroma, chroma_times, beat_times, duration):
    """Estimate and lightly deglitch beat-synchronous chord regions."""
    boundaries = np.concatenate(
        (
            np.array([0.0]),
            np.asarray(beat_times, dtype=float),
            np.array([float(duration)]),
        )
    )
    boundaries = np.unique(np.clip(boundaries, 0.0, float(duration)))

    if len(boundaries) < 2:
        boundaries = np.array([0.0, float(duration)])

    regions = []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        if end - start <= 1e-4:
            continue

        in_region = (chroma_times >= start) & (chroma_times < end)
        estimate = estimate_chord_region(aggregate_chroma_profile(chroma[:, in_region]))
        regions.append(
            {
                "start": float(start),
                "end": float(end),
                **estimate,
                "smoothed": False,
            }
        )

    stabilized = [dict(region) for region in regions]
    for index in range(1, len(regions) - 1):
        previous = regions[index - 1]
        current = regions[index]
        following = regions[index + 1]

        if (
            not previous["ambiguous"]
            and not following["ambiguous"]
            and previous["label"] == following["label"]
            and current["label"] != previous["label"]
            and (
                current["ambiguous"]
                or current["margin"] < max(previous["margin"], following["margin"])
            )
        ):
            stabilized[index].update(
                {
                    "label": previous["label"],
                    "root": previous["root"],
                    "quality": previous["quality"],
                    "movement_family": previous["movement_family"],
                    "movement_label": previous["movement_label"],
                    "similarity": min(previous["similarity"], following["similarity"]),
                    "margin": min(previous["margin"], following["margin"]),
                    "quality_confidence": min(
                        previous["quality_confidence"],
                        following["quality_confidence"],
                    ),
                    "color_complexity": previous["color_complexity"],
                    "color_evidence": min(
                        previous["color_evidence"],
                        following["color_evidence"],
                    ),
                    "ambiguous": False,
                    "smoothed": True,
                }
            )

    return stabilized


def chord_transitions(chord_regions):
    """Return confident changes between adjacent chord regions."""
    transitions = []

    for previous, current in zip(chord_regions[:-1], chord_regions[1:]):
        if previous["ambiguous"] or current["ambiguous"]:
            continue

        previous_label = previous.get("movement_label", previous["label"])
        current_label = current.get("movement_label", current["label"])
        if previous_label != current_label:
            transitions.append((previous_label, current_label))

    return transitions


def summarize_harmonic_movement(chord_regions, transition_counts):
    """Measure chord changes, transition novelty, and chord-quality color."""
    transitions = chord_transitions(chord_regions)
    change_count = len(transitions)
    bar_equivalents = max(len(chord_regions) / BEATS_PER_HARMONY_WINDOW, 0.25)
    changes_per_bar = float(change_count / bar_equivalents)
    novel_count = sum(transition_counts.get(transition, 0) == 1 for transition in transitions)
    novel_ratio = float(novel_count / change_count) if change_count else 0.0
    repeated_ratio = float(1.0 - novel_ratio) if change_count else 0.0
    rate_score = float(
        np.clip(changes_per_bar / MAX_HARMONIC_CHANGES_PER_BAR, 0.0, 1.0)
    )
    movement = float(0.75 * rate_score + 0.25 * novel_ratio)
    confident_labels = [
        region.get("movement_label", region["label"])
        for region in chord_regions
        if not region["ambiguous"]
    ]
    confident_regions = [
        region for region in chord_regions if not region["ambiguous"]
    ]
    confident_duration = sum(
        max(0.0, region["end"] - region["start"])
        for region in confident_regions
    )
    mean_quality_color = (
        float(
            sum(
                region.get("color_evidence", 0.0)
                * max(0.0, region["end"] - region["start"])
                for region in confident_regions
            )
            / confident_duration
        )
        if confident_duration > 0
        else 0.0
    )
    colored_duration = sum(
        max(0.0, region["end"] - region["start"])
        for region in confident_regions
        if region.get("color_complexity", 0.0) >= 0.24
    )
    altered_duration = sum(
        max(0.0, region["end"] - region["start"])
        for region in confident_regions
        if region.get("color_complexity", 0.0) >= 0.80
    )
    quality_counts = {}
    for region in confident_regions:
        quality = region.get("quality")
        if quality:
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
    colored_chord_ratio = (
        float(colored_duration / confident_duration)
        if confident_duration > 0
        else 0.0
    )
    altered_chord_ratio = (
        float(altered_duration / confident_duration)
        if confident_duration > 0
        else 0.0
    )
    altered_salience = float(np.clip(altered_chord_ratio / 0.03, 0.0, 1.0))
    harmonic_color = float(
        np.clip(
            0.25 * mean_quality_color
            + 0.10 * colored_chord_ratio
            + 0.65 * altered_salience,
            0.0,
            1.0,
        )
    )

    return {
        "harmonic_movement": movement,
        "harmonic_color": harmonic_color,
        "mean_quality_color": mean_quality_color,
        "colored_chord_ratio": colored_chord_ratio,
        "altered_chord_ratio": altered_chord_ratio,
        "altered_salience": altered_salience,
        "chord_quality_counts": quality_counts,
        "chord_change_count": int(change_count),
        "changes_per_bar": changes_per_bar,
        "novel_transition_ratio": novel_ratio,
        "repeated_transition_ratio": repeated_ratio,
        "unique_chord_count": int(len(set(confident_labels))),
        "chord_regions": [
            {
                "start": region["start"],
                "end": region["end"],
                "label": region["label"],
                "quality": region.get("quality"),
                "movement_label": region.get("movement_label", region["label"]),
                "similarity": region["similarity"],
                "margin": region["margin"],
                "quality_confidence": region.get("quality_confidence", 0.0),
                "color_complexity": region.get("color_complexity", 0.0),
                "color_evidence": region.get("color_evidence", 0.0),
                "ambiguous": region["ambiguous"],
                "smoothed": region["smoothed"],
            }
            for region in chord_regions
        ],
    }


def key_confidence_metadata(local_key, global_key):
    """Describe local key strength relative to full-track evidence."""
    correlation = float(local_key.get("correlation", 0.0))
    margin = float(local_key.get("correlation_margin", 0.0))
    global_correlation = float(global_key.get("correlation", 0.0))
    global_margin = float(global_key.get("correlation_margin", 0.0))
    correlation_reference = max(global_correlation, 0.40)
    margin_reference = max(global_margin, 0.02)
    required_correlation = min(
        MIN_LOCAL_KEY_CORRELATION,
        max(0.40, global_correlation * 0.75),
    )
    required_margin = min(
        MIN_LOCAL_KEY_MARGIN,
        max(0.02, global_margin * 0.75),
    )
    relative_correlation = float(np.clip(correlation / correlation_reference, 0.0, 1.0))
    relative_margin = float(np.clip(margin / margin_reference, 0.0, 1.0))
    score = float(0.70 * relative_correlation + 0.30 * relative_margin)
    ambiguous = (
        correlation < required_correlation
        or margin < required_margin
    )

    if ambiguous:
        level = "low"
    elif correlation >= 0.70 and margin >= MIN_KEY_CORRELATION_MARGIN:
        level = "high"
    else:
        level = "medium"

    return {
        "correlation": correlation,
        "margin": margin,
        "relative_correlation": relative_correlation,
        "relative_margin": relative_margin,
        "score": score,
        "level": level,
        "ambiguous": ambiguous,
        "required_correlation": required_correlation,
        "required_margin": required_margin,
    }


def harmonic_mode_family(scale_type):
    """Group related modes when measuring continuity of one tonal center."""
    if scale_type in {"major", "lydian", "mixolydian"}:
        return "major_family"

    if scale_type in {
        "minor",
        "dorian",
        "phrygian",
        "locrian",
        "harmonic_minor",
        "melodic_minor",
    }:
        return "minor_family"

    return scale_type


def modulation_confidence(window):
    """Map correlation and margin above modulation thresholds to 0-1."""
    correlation_strength = np.clip(
        (window["local_key_correlation"] - MIN_KEY_CORRELATION)
        / max(1e-12, 1.0 - MIN_KEY_CORRELATION),
        0.0,
        1.0,
    )
    margin_strength = np.clip(
        (window["local_key_correlation_margin"] - MIN_KEY_CORRELATION_MARGIN)
        / 0.20,
        0.0,
        1.0,
    )
    return float(0.65 * correlation_strength + 0.35 * margin_strength)


def classify_modulation_windows(harmony_windows, root, scale_type):
    """Find confident root-or-mode changes and their transition neighborhoods."""
    main_state = (root, scale_type)
    runs = []
    run_start = None
    run_state = None

    def finish_run(end_index):
        if run_start is None:
            return

        run_windows = harmony_windows[run_start:end_index]
        if len(run_windows) < MIN_MODULATION_WINDOWS:
            return

        # A different short-window key label that mostly remains compatible
        # with the global center is tonicization/chord movement, not enough
        # evidence for a modulation without cadence-aware analysis.
        noncentered_ratio = float(
            np.mean(
                [not window.get("tonally_centered", False) for window in run_windows]
            )
        )
        if noncentered_ratio < MIN_MODULATION_NONCENTERED_RATIO:
            return

        confidence = float(
            np.mean([modulation_confidence(window) for window in run_windows])
        )

        if confidence < MIN_MODULATION_CONFIDENCE:
            return

        runs.append(
            {
                "start_index": run_start,
                "end_index": end_index - 1,
                "root": run_state[0],
                "scale_type": run_state[1],
                "confidence": confidence,
                "noncentered_window_ratio": noncentered_ratio,
            }
        )

    for index, window in enumerate(harmony_windows):
        state = (window["local_root"], window["local_scale_type"])
        confident_change = (
            not window["ambiguous"]
            and state != main_state
            and window["local_key_correlation"] >= MIN_KEY_CORRELATION
            and window["local_key_correlation_margin"] >= MIN_KEY_CORRELATION_MARGIN
        )
        candidate_state = state if confident_change else None

        if candidate_state == run_state and candidate_state is not None:
            continue

        finish_run(index)
        run_start = index if candidate_state is not None else None
        run_state = candidate_state

    finish_run(len(harmony_windows))

    modulation_numbers = set()
    transition_numbers = set()
    confidence_by_window = {}

    for run in runs:
        for index in range(run["start_index"], run["end_index"] + 1):
            window_number = harmony_windows[index]["window"]
            modulation_numbers.add(window_number)
            confidence_by_window[window_number] = run["confidence"]

        for index in {
            run["start_index"] - 1,
            run["start_index"],
            run["end_index"],
            run["end_index"] + 1,
        }:
            if 0 <= index < len(harmony_windows):
                window_number = harmony_windows[index]["window"]
                transition_numbers.add(window_number)
                confidence_by_window[window_number] = max(
                    confidence_by_window.get(window_number, 0.0),
                    run["confidence"],
                )

    return {
        "modulation_windows": modulation_numbers,
        "transition_windows": transition_numbers,
        "confidence_by_window": confidence_by_window,
        "runs": [
            {
                "start_window": harmony_windows[run["start_index"]]["window"],
                "end_window": harmony_windows[run["end_index"]]["window"],
                "root": run["root"],
                "scale_type": run["scale_type"],
                "confidence": run["confidence"],
                "noncentered_window_ratio": run["noncentered_window_ratio"],
            }
            for run in runs
        ],
    }


def detect_sustained_modulations(harmony_windows, root, scale_type):
    """Compatibility helper returning only sustained modulation window numbers."""
    return classify_modulation_windows(harmony_windows, root, scale_type)[
        "modulation_windows"
    ]


def summarize_modulation_load(harmony_windows, modulation):
    """Measure how much confident, repeated key movement a track contains."""
    confident_windows = [
        window for window in harmony_windows if not window["ambiguous"]
    ]
    confident_duration = sum(
        max(0.0, window["end"] - window["start"])
        for window in confident_windows
    )
    modulation_duration = 0.0
    confidence_weighted_duration = 0.0

    for window in confident_windows:
        if window["window"] not in modulation["modulation_windows"]:
            continue

        duration = max(0.0, window["end"] - window["start"])
        confidence = modulation["confidence_by_window"].get(window["window"], 0.0)
        modulation_duration += duration
        confidence_weighted_duration += duration * confidence

    duration_ratio = (
        float(modulation_duration / confident_duration)
        if confident_duration > 0
        else 0.0
    )
    confidence_weighted_ratio = (
        float(confidence_weighted_duration / confident_duration)
        if confident_duration > 0
        else 0.0
    )
    run_count = len(modulation["runs"])
    run_opportunities = max(len(confident_windows) / 16.0, 1.0)
    run_density = float(np.clip(run_count / run_opportunities, 0.0, 1.0))
    mean_run_confidence = (
        float(np.mean([run["confidence"] for run in modulation["runs"]]))
        if modulation["runs"]
        else 0.0
    )
    confidence_breadth = float(
        mean_run_confidence * min(1.0, run_count / 4.0)
    )
    modulation_load = float(
        np.clip(
            0.45 * run_density
            + 0.30 * confidence_weighted_ratio
            + 0.25 * confidence_breadth,
            0.0,
            1.0,
        )
    )

    return {
        "modulation_load": modulation_load,
        "run_count": int(run_count),
        "run_density": run_density,
        "duration_ratio": duration_ratio,
        "confidence_weighted_duration_ratio": confidence_weighted_ratio,
        "mean_run_confidence": mean_run_confidence,
        "confidence_breadth": confidence_breadth,
    }


def normalized_harmonic_sigmoid(score):
    """Map evidence to a perceptual 0-1 scale while preserving both endpoints."""
    if score is None or not np.isfinite(score):
        return None

    def logistic(value):
        return 1.0 / (1.0 + np.exp(-value))

    score = float(np.clip(score, 0.0, 1.0))
    lower = logistic(-HARMONIC_SIGMOID_CENTER / HARMONIC_SIGMOID_SCALE)
    upper = logistic(
        (1.0 - HARMONIC_SIGMOID_CENTER) / HARMONIC_SIGMOID_SCALE
    )
    mapped = logistic(
        (score - HARMONIC_SIGMOID_CENTER) / HARMONIC_SIGMOID_SCALE
    )
    return float(np.clip((mapped - lower) / (upper - lower), 0.0, 1.0))


def harmonic_evidence_score(
    diatonic_deviation,
    harmonic_movement,
    tonal_stability,
    voicing_density,
    modulation_load,
    harmonic_color,
):
    """Combine harmonic evidence before perceptual range calibration."""
    values = (
        diatonic_deviation,
        harmonic_movement,
        tonal_stability,
        voicing_density,
        modulation_load,
        harmonic_color,
    )

    if any(value is None or not np.isfinite(value) for value in values):
        return None

    tonal_instability = 1.0 - float(tonal_stability)
    return float(
        np.clip(
            HARMONIC_COMPLEXITY_WEIGHTS["diatonic_deviation"]
            * float(diatonic_deviation)
            + HARMONIC_COMPLEXITY_WEIGHTS["harmonic_movement"]
            * float(harmonic_movement)
            + HARMONIC_COMPLEXITY_WEIGHTS["tonal_instability"]
            * tonal_instability
            + HARMONIC_COMPLEXITY_WEIGHTS["voicing_density"]
            * float(voicing_density)
            + HARMONIC_COMPLEXITY_WEIGHTS["modulation_load"]
            * float(modulation_load)
            + HARMONIC_COMPLEXITY_WEIGHTS["harmonic_color"]
            * float(harmonic_color),
            0.0,
            1.0,
        )
    )


def harmonic_composite_score(
    diatonic_deviation,
    harmonic_movement,
    tonal_stability,
    voicing_density,
    modulation_load,
    harmonic_color,
):
    """Return the perceptually calibrated 0-1 harmonic-complexity score."""
    evidence_score = harmonic_evidence_score(
        diatonic_deviation,
        harmonic_movement,
        tonal_stability,
        voicing_density,
        modulation_load,
        harmonic_color,
    )
    return normalized_harmonic_sigmoid(evidence_score)


def summarize_tonal_stability(harmony_windows):
    """Summarize centered duration, longest centered run, and local confidence."""
    confident_windows = [window for window in harmony_windows if not window["ambiguous"]]
    total_duration = sum(max(0.0, window["end"] - window["start"]) for window in harmony_windows)
    confident_duration = sum(
        max(0.0, window["end"] - window["start"])
        for window in confident_windows
    )
    centered_duration = sum(
        max(0.0, window["end"] - window["start"])
        for window in confident_windows
        if window["tonally_centered"]
    )
    longest_centered_run = 0.0
    current_run = 0.0

    for window in harmony_windows:
        duration = max(0.0, window["end"] - window["start"])
        if not window["ambiguous"] and window["tonally_centered"]:
            current_run += duration
            longest_centered_run = max(longest_centered_run, current_run)
        else:
            current_run = 0.0

    centered_ratio = (
        float(centered_duration / confident_duration) if confident_duration > 0 else 0.0
    )
    longest_ratio = (
        float(longest_centered_run / confident_duration) if confident_duration > 0 else 0.0
    )
    mean_local_stability = (
        float(np.mean([window["tonal_stability"] for window in confident_windows]))
        if confident_windows
        else None
    )
    tonal_stability = (
        float(0.50 * centered_ratio + 0.30 * longest_ratio + 0.20 * mean_local_stability)
        if mean_local_stability is not None
        else None
    )

    return {
        "tonal_stability": tonal_stability,
        "tonal_instability": (
            float(1.0 - tonal_stability) if tonal_stability is not None else None
        ),
        "centered_duration_ratio": centered_ratio,
        "longest_centered_run_ratio": longest_ratio,
        "analyzable_duration_ratio": (
            float(confident_duration / total_duration) if total_duration > 0 else 0.0
        ),
    }


def analyze_harmonic_complexity(
    y,
    sr,
    beat_times,
    duration,
    root_override=None,
    scale_override=None,
    harmonic_signal=None,
    detected_key=None,
):
    """Analyze chromaticism, movement, tonal stability, and voicing density."""
    y_harm = (
        harmonic_signal
        if harmonic_signal is not None
        else librosa.effects.harmonic(y=y, margin=8)
    )
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, bins_per_octave=36)
    chroma = np.minimum(
        chroma,
        librosa.decompose.nn_filter(
            chroma,
            aggregate=np.median,
            metric="cosine",
        ),
    )
    chroma = scipy.ndimage.median_filter(chroma, size=(1, 9))
    chroma = preprocess_harmonic_chroma(chroma)
    chroma_times = librosa.times_like(chroma, sr=sr)
    chord_chroma = librosa.feature.chroma_cqt(
        y=y_harm,
        sr=sr,
        bins_per_octave=36,
        fmin=librosa.note_to_hz(CHORD_CHROMA_FMIN),
        n_octaves=CHORD_CHROMA_OCTAVES,
    )
    chord_chroma = np.minimum(
        chord_chroma,
        librosa.decompose.nn_filter(
            chord_chroma,
            aggregate=np.median,
            metric="cosine",
        ),
    )
    chord_chroma = scipy.ndimage.median_filter(chord_chroma, size=(1, 9))
    chord_chroma = preprocess_harmonic_chroma(chord_chroma)
    chord_chroma_times = librosa.times_like(chord_chroma, sr=sr)
    chroma_profile = aggregate_chroma_profile(chroma)
    detected_key = detected_key or detect_key_and_mode(build_key_chroma_profile(y, sr))
    root = root_override or USER_ROOT or detected_key["root"]
    scale_type = scale_override or USER_SCALE_TYPE or detected_key["scale_type"]
    analysis_key_fit = key_fit(chroma_profile, root, scale_type)
    scale_mask = get_scale_mask(root, scale_type)
    windows = beat_windows(beat_times, duration, BEATS_PER_HARMONY_WINDOW)
    chord_regions = build_chord_regions(
        chord_chroma,
        chord_chroma_times,
        beat_times,
        duration,
    )
    all_transitions = chord_transitions(chord_regions)
    transition_counts = {
        transition: all_transitions.count(transition)
        for transition in set(all_transitions)
    }
    global_movement_summary = summarize_harmonic_movement(
        chord_regions,
        transition_counts,
    )

    harmony_windows = []
    for window_number, start_time, end_time, label in windows:
        in_window = (chroma_times >= start_time) & (chroma_times < end_time)
        local_chroma = chroma[:, in_window]
        valid_frames = np.sum(local_chroma, axis=0) > 1e-12
        frame_deviation = (
            np.sum(local_chroma[:, valid_frames] * (1 - scale_mask[:, None]), axis=0)
            if np.any(valid_frames)
            else np.array([])
        )
        diatonic_deviation = (
            float(trimmed_mean(frame_deviation)) if len(frame_deviation) else None
        )
        window_duration = max(0.0, end_time - start_time)
        context_span = HARMONY_KEY_CONTEXT_WINDOWS * window_duration
        in_key_context = (
            (chroma_times >= max(0.0, start_time - context_span))
            & (chroma_times < min(duration, end_time + context_span))
        )
        local_profile = aggregate_chroma_profile(chroma[:, in_key_context])
        try:
            local_key = detect_key_and_mode(
                local_profile,
                allow_derived_modes=True,
            )
        except AnalysisInputError:
            local_key = {
                "root": root,
                "scale_type": (
                    scale_type if scale_type in CLASSICAL_KEY_PROFILES else "major"
                ),
                "correlation": 0.0,
                "correlation_margin": 0.0,
            }
        confidence = key_confidence_metadata(local_key, detected_key)
        local_regions = [
            region
            for region in chord_regions
            if start_time <= (region["start"] + region["end"]) / 2 < end_time
        ]
        movement = summarize_harmonic_movement(local_regions, transition_counts)
        density = estimate_voicing_density(local_chroma)
        exact_center = (
            local_key["root"] == root and local_key["scale_type"] == scale_type
        )
        same_tonic = local_key["root"] == root
        same_family = (
            harmonic_mode_family(local_key["scale_type"])
            == harmonic_mode_family(scale_type)
        )
        center_factor = (
            1.0
            if exact_center
            else 0.85
            if same_tonic and same_family
            else 0.55
            if same_tonic
            else 0.0
        )
        local_analysis_key_fit = key_fit(local_profile, root, scale_type)
        tonal_center_threshold = min(0.85, max(0.65, analysis_key_fit * 0.90))
        tonally_centered = local_analysis_key_fit >= tonal_center_threshold
        fit_strength = (
            float(
                np.clip(
                    (local_analysis_key_fit - tonal_center_threshold)
                    / max(1e-12, 1.0 - tonal_center_threshold),
                    0.0,
                    1.0,
                )
            )
            if tonally_centered
            else 0.0
        )
        tonal_stability = float(
            fit_strength
            * (0.75 + 0.15 * confidence["score"] + 0.10 * center_factor)
        )

        harmony_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "diatonic_deviation": diatonic_deviation,
                # Temporary compatibility alias for older saved-project consumers.
                "raw_complexity": diatonic_deviation,
                "local_root": local_key["root"],
                "local_scale_type": local_key["scale_type"],
                "local_key_correlation": local_key["correlation"],
                "local_key_correlation_margin": local_key["correlation_margin"],
                "local_key_confidence": confidence,
                "ambiguous": confidence["ambiguous"],
                "harmonic_evidence": (
                    "low-confidence harmonic evidence"
                    if confidence["ambiguous"]
                    else "confident harmonic evidence"
                ),
                "tonally_centered": tonally_centered,
                "tonal_center_strength": center_factor,
                "local_analysis_key_fit": local_analysis_key_fit,
                "tonal_center_threshold": tonal_center_threshold,
                "tonal_stability": tonal_stability,
                "tonal_instability": float(1.0 - tonal_stability),
                **movement,
                **density,
            }
        )

    modulation = classify_modulation_windows(
        harmony_windows,
        root,
        scale_type,
    )
    modulation_summary = summarize_modulation_load(harmony_windows, modulation)

    for window in harmony_windows:
        window_number = window["window"]
        is_modulation = window_number in modulation["modulation_windows"]
        is_transition = window_number in modulation["transition_windows"]
        confidence = modulation["confidence_by_window"].get(window_number, 0.0)
        window["sustained_modulation"] = is_modulation
        window["modulation_transition"] = is_transition
        window["modulation_confidence"] = confidence
        window["modulation_state"] = (
            "ambiguous"
            if window["ambiguous"]
            else "modulation"
            if is_modulation
            else "transition"
            if is_transition
            else "centered"
        )
        reduction_strength = confidence * (1.0 if is_modulation else 0.5 if is_transition else 0.0)
        adjustment = 1.0 - MAX_MODULATION_DEVIATION_REDUCTION * reduction_strength
        window["modulation_adjustment"] = float(adjustment)
        window["modulation_load"] = float(
            confidence
            * (1.0 if is_modulation else 0.5 if is_transition else 0.0)
        )
        window["adjusted_diatonic_deviation"] = (
            float(window["diatonic_deviation"] * adjustment)
            if window["diatonic_deviation"] is not None and not window["ambiguous"]
            else None
        )
        window["harmonic_complexity"] = (
            harmonic_composite_score(
                window["adjusted_diatonic_deviation"],
                window["harmonic_movement"],
                window["tonal_stability"],
                window["voicing_density"],
                window["modulation_load"],
                window["harmonic_color"],
            )
            if not window["ambiguous"]
            else None
        )
        window["harmonic_evidence_score"] = (
            harmonic_evidence_score(
                window["adjusted_diatonic_deviation"],
                window["harmonic_movement"],
                window["tonal_stability"],
                window["voicing_density"],
                window["modulation_load"],
                window["harmonic_color"],
            )
            if not window["ambiguous"]
            else None
        )
        # Temporary compatibility alias used by older frontend chart payloads.
        window["adjusted_complexity"] = window["harmonic_complexity"]

    tonal_summary = summarize_tonal_stability(harmony_windows)
    confident_windows = [window for window in harmony_windows if not window["ambiguous"]]
    raw_values = [
        window["diatonic_deviation"]
        for window in harmony_windows
        if window["diatonic_deviation"] is not None
    ]
    adjusted_values = [
        window["adjusted_diatonic_deviation"]
        for window in confident_windows
        if window["adjusted_diatonic_deviation"] is not None
    ]
    movement_values = [window["harmonic_movement"] for window in confident_windows]
    density_values = [
        window["voicing_density"]
        for window in confident_windows
        if window["voicing_density"] is not None
    ]
    diatonic_deviation = float(np.mean(raw_values)) if raw_values else None
    adjusted_diatonic_deviation = (
        float(np.mean(adjusted_values)) if adjusted_values else None
    )
    mean_window_movement = float(np.mean(movement_values)) if movement_values else None
    unique_transition_ratio = (
        float(len(set(all_transitions)) / len(all_transitions))
        if all_transitions
        else 0.0
    )
    harmonic_movement = (
        float(0.40 * mean_window_movement + 0.60 * unique_transition_ratio)
        if mean_window_movement is not None
        else None
    )
    voicing_density = float(np.mean(density_values)) if density_values else None
    harmonic_color = global_movement_summary["harmonic_color"]
    modulation_load = modulation_summary["modulation_load"]
    evidence_score = harmonic_evidence_score(
        adjusted_diatonic_deviation,
        harmonic_movement,
        tonal_summary["tonal_stability"],
        voicing_density,
        modulation_load,
        harmonic_color,
    )
    overall_score = harmonic_composite_score(
        adjusted_diatonic_deviation,
        harmonic_movement,
        tonal_summary["tonal_stability"],
        voicing_density,
        modulation_load,
        harmonic_color,
    )
    high_complexity_windows = [
        window
        for window in harmony_windows
        if window["harmonic_complexity"] is not None
        and window["harmonic_complexity"] > HARMONIC_HOTSPOT_THRESHOLD
    ]
    ambiguous_count = sum(window["ambiguous"] for window in harmony_windows)
    weighted_contributions = {
        "chromaticism": (
            HARMONIC_COMPLEXITY_WEIGHTS["diatonic_deviation"]
            * adjusted_diatonic_deviation
            if adjusted_diatonic_deviation is not None
            else None
        ),
        "harmonic_movement": (
            HARMONIC_COMPLEXITY_WEIGHTS["harmonic_movement"] * harmonic_movement
            if harmonic_movement is not None
            else None
        ),
        "tonal_instability": (
            HARMONIC_COMPLEXITY_WEIGHTS["tonal_instability"]
            * tonal_summary["tonal_instability"]
            if tonal_summary["tonal_instability"] is not None
            else None
        ),
        "voicing_density": (
            HARMONIC_COMPLEXITY_WEIGHTS["voicing_density"] * voicing_density
            if voicing_density is not None
            else None
        ),
        "modulation_load": (
            HARMONIC_COMPLEXITY_WEIGHTS["modulation_load"] * modulation_load
        ),
        "harmonic_color": (
            HARMONIC_COMPLEXITY_WEIGHTS["harmonic_color"] * harmonic_color
        ),
    }
    dominant_factors = [
        name
        for name, value in sorted(
            (
                (name, value)
                for name, value in weighted_contributions.items()
                if value is not None
            ),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return {
        "overall_score": overall_score,
        "evidence_score": evidence_score,
        "raw_score": diatonic_deviation,
        "diatonic_deviation": diatonic_deviation,
        "adjusted_diatonic_deviation": adjusted_diatonic_deviation,
        "harmonic_movement": harmonic_movement,
        "tonal_stability": tonal_summary["tonal_stability"],
        "tonal_instability": tonal_summary["tonal_instability"],
        "voicing_density": voicing_density,
        "modulation_load": modulation_load,
        "harmonic_color": harmonic_color,
        "weighted_contributions": weighted_contributions,
        "dominant_factors": dominant_factors,
        "weights": dict(HARMONIC_COMPLEXITY_WEIGHTS),
        "normalization": {
            "algorithm": "endpoint_normalized_sigmoid_v1",
            "center": HARMONIC_SIGMOID_CENTER,
            "scale": HARMONIC_SIGMOID_SCALE,
        },
        "windows": harmony_windows,
        "high_complexity_windows": high_complexity_windows,
        "ambiguous_windows": [window for window in harmony_windows if window["ambiguous"]],
        "detected_key": detected_key,
        "analysis_key": {
            "root": root,
            "scale_type": scale_type,
            "fit": analysis_key_fit,
        },
        "confidence": {
            "global_key_correlation": detected_key["correlation"],
            "global_key_correlation_margin": detected_key["correlation_margin"],
            "ambiguous_window_count": int(ambiguous_count),
            "ambiguous_window_ratio": (
                float(ambiguous_count / len(harmony_windows)) if harmony_windows else 0.0
            ),
            **tonal_summary,
        },
        "modulation": {
            "runs": modulation["runs"],
            "window_count": int(len(modulation["modulation_windows"])),
            "transition_window_count": int(len(modulation["transition_windows"])),
            **modulation_summary,
        },
        "movement": {
            "chord_region_count": int(len(chord_regions)),
            "chord_change_count": int(len(all_transitions)),
            "mean_window_movement": mean_window_movement,
            "unique_transition_ratio": unique_transition_ratio,
            "repeated_transition_ratio": (
                float(1.0 - unique_transition_ratio) if all_transitions else 0.0
            ),
            "harmonic_color": harmonic_color,
            "mean_quality_color": global_movement_summary["mean_quality_color"],
            "colored_chord_ratio": global_movement_summary["colored_chord_ratio"],
            "altered_chord_ratio": global_movement_summary["altered_chord_ratio"],
            "altered_salience": global_movement_summary["altered_salience"],
            "chord_quality_counts": global_movement_summary["chord_quality_counts"],
        },
        "polyphony": detect_polyphonic_density(chroma),
    }


# ---------------------------------------------------------------------------
# Text formatting and prompt helpers
# ---------------------------------------------------------------------------

def lowest_scored_windows(windows, score_key, limit=3):
    """Pick the lowest-scoring windows for feedback and summaries."""
    scored_windows = [window for window in windows if window.get(score_key) is not None]
    return sorted(scored_windows, key=lambda window: window[score_key])[:limit]


def highest_scored_windows(windows, score_key, limit=3):
    """Pick the highest-scoring windows when high values are notable."""
    scored_windows = [window for window in windows if window.get(score_key) is not None]
    return sorted(
        scored_windows,
        key=lambda window: window[score_key],
        reverse=True,
    )[:limit]


def format_score(score):
    """Format nullable numeric scores for prompt text and CLI output."""
    return "N/A" if score is None else f"{score:.3f}"


def format_window_summary(windows, score_key, limit=3, high_is_notable=False):
    """Turn selected analysis windows into compact bullet text."""
    selected_windows = (
        highest_scored_windows(windows, score_key, limit)
        if high_is_notable
        else lowest_scored_windows(windows, score_key, limit)
    )

    if not selected_windows:
        return "No usable windows found."

    return "\n".join(
        f"- {window['time_range']}: {score_key}={format_score(window[score_key])}"
        for window in selected_windows
    )


def build_prompt(
    tempo_analysis,
    pitch_analysis,
    harmony_analysis,
    dynamics_analysis,
    extra_prompt="",
):
    """Build the instruction prompt sent to the OpenAI API.

    Local signal metrics are treated as primary evidence. When supported, the
    attached audio input gives the model additional listening context, but the
    computed metrics keep
    the feedback grounded and easier to justify.
    """
    tempo_summary = format_window_summary(
        tempo_analysis["windows"],
        "score",
    )
    pitch_summary = format_window_summary(
        pitch_analysis["windows"],
        "score",
    )
    harmony_summary = format_window_summary(
        harmony_analysis["windows"],
        "harmonic_complexity",
        high_is_notable=True,
    )
    dynamics_summary = format_window_summary(
        dynamics_analysis["windows"],
        "score",
    )
    analysis_key = harmony_analysis["analysis_key"]
    pitch_reliability = pitch_analysis["reliability"]
    if pitch_reliability in {"insufficient", "low"}:
        if pitch_analysis["source"] == "full_mix_harmonic":
            pitch_warning = (
                "This is low-reliability monophonic evidence from a full mix and may follow "
                "bass or another dominant source; do not describe it as a confident vocal "
                "measurement."
            )
        else:
            pitch_warning = (
                "The separated vocal stem has insufficient pitch evidence; do not describe "
                "the result as a confident vocal measurement."
            )
    else:
        pitch_warning = (
            "The pYIN evidence has enough effective voiced coverage to discuss cautiously."
        )
    harmonic_drivers = ", ".join(
        factor.replace("_", " ")
        for factor in harmony_analysis["dominant_factors"][:3]
    ) or "insufficient confident evidence"
    ambiguity_note = (
        f"{harmony_analysis['confidence']['ambiguous_window_count']} of "
        f"{len(harmony_analysis['windows'])} harmonic windows contain low-confidence "
        "evidence and must not be interpreted as definite complexity."
    )
    quality_counts = harmony_analysis["movement"].get("chord_quality_counts", {})
    quality_summary = ", ".join(
        f"{quality.replace('_', ' ')}={count}"
        for quality, count in sorted(
            quality_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:6]
    ) or "no confident chord-quality evidence"
    extra_prompt_section = (
        f"\nAdditional user request:\n{extra_prompt.strip()}\n"
        if extra_prompt and extra_prompt.strip()
        else ""
    )

    return f"""You are a music analysis assistant. Interpret the metrics and provide concise, actionable songwriting feedback.

When an audio input is attached, it is the actual song being analyzed. Use the computed metrics as the primary evidence, and use the audio only as supporting context.

Metrics:

1. Tempo Stability (0-1)

* Measures proportional consistency of consecutive beat intervals against the global BPM.
* Higher values indicate a stable beat rate inside eight-beat windows.
* It does not judge onset phase, syncopation, subdivisions, or swing.

2. Pitch Accuracy (0-1)

* Measures probability-weighted monophonic pitch accuracy relative to equal-tempered tuning.
* The calculation smooths short vibrato and softens penalties during bend-like motion.
* Reliability and effective voiced coverage determine how strongly this evidence may be used.

3. Harmonic Complexity (0-1)

* Endpoint-normalized composite of confidence-adjusted diatonic deviation, chord-region movement, tonal instability, voicing density, modulation load, and harmonic color.
* Confident sustained root or mode changes reduce the chromaticity contribution proportionally while remaining visible as tonal movement.
* Harmonic color is conservative quality evidence for sevenths, added notes, ninths, diminished sonorities, and altered dominants; it is not guaranteed chord transcription.
* Ambiguous windows have no composite score and are only low-confidence harmonic evidence.

4. Dynamics Contour (0-1)

* Measures how cleanly local RMS energy follows a simple linear contour inside beat-synchronous windows.
* Higher values indicate controlled steady loudness, fade-ins, fade-outs, or smooth ramps.
* Lower values indicate energy movement that jumps around rather than following a clear contour.

Guidelines:

* Focus on the 1-2 most important areas for improvement.
* Keep feedback under 140 words.
* Explain what the metrics imply musically, not technically.
* Give practical suggestions that a musician can immediately apply.
* Avoid overwhelming the user with multiple recommendations.
* Do not discuss signal processing, chroma features, Fourier transforms, or implementation details.
* Acknowledge strengths before discussing weaknesses.
* If all metrics are strong, focus on refinement rather than criticism.
* Never frame insufficient or low-reliability pitch evidence as a confident vocal diagnosis.
* State whether audible harmonic interest is most consistent with chromaticism, modulation, chord movement, chord color/extensions, or dense voicing.
* Interpret what the harmonic behavior means musically; do not explain feature extraction or confidence math.
* Never describe an ambiguous harmonic window as a definite chord, modulation, or complexity hotspot.
* Write in plain text only. Do not use LaTeX, math delimiters, markdown tables, or symbolic equations.
{extra_prompt_section}

Measured scores:

Tempo Stability Score: {format_score(tempo_analysis["overall_score"])}
Tempo Tracking BPM: {format_score(tempo_analysis["global_bpm"])}
Tempo Median Local BPM: {format_score(tempo_analysis["median_bpm"])}
Pitch Accuracy Score: {format_score(pitch_analysis["overall_score"])}
Pitch Tracking Source: {pitch_analysis["source"]}
Pitch Reliability: {pitch_reliability}
Pitch Voiced Frame Ratio: {format_score(pitch_analysis["voiced_frame_ratio"])}
Pitch Effective Voiced Ratio: {format_score(pitch_analysis["effective_voiced_ratio"])}
Harmonic Complexity Composite: {format_score(harmony_analysis["overall_score"])}
Pre-Normalization Harmonic Evidence: {format_score(harmony_analysis["evidence_score"])}
Diatonic Deviation: {format_score(harmony_analysis["diatonic_deviation"])}
Confidence-Adjusted Diatonic Deviation: {format_score(harmony_analysis["adjusted_diatonic_deviation"])}
Harmonic Movement: {format_score(harmony_analysis["harmonic_movement"])}
Tonal Stability: {format_score(harmony_analysis["tonal_stability"])}
Tonal Instability: {format_score(harmony_analysis["tonal_instability"])}
Voicing Density: {format_score(harmony_analysis["voicing_density"])}
Modulation Load: {format_score(harmony_analysis["modulation_load"])}
Harmonic Color: {format_score(harmony_analysis["harmonic_color"])}
Confident Chord-Quality Counts: {quality_summary}
Primary Harmonic Drivers: {harmonic_drivers}
Detected Modulation Runs: {len(harmony_analysis["modulation"]["runs"])}
Harmonic Confidence Note: {ambiguity_note}
Dynamics Contour Score: {format_score(dynamics_analysis["overall_score"])}
Detected Key/Mode: {analysis_key["root"]} {analysis_key["scale_type"]} (fit={analysis_key["fit"]:.3f})
Pitch Evidence Note: {pitch_warning}

Least stable tempo windows:
{tempo_summary}

Weakest pitch windows:
{pitch_summary}

Most complex confident harmony windows:
{harmony_summary}

Least controlled dynamics windows:
{dynamics_summary}

Output format:

Strengths:

* ...

Suggested Improvement:

* ...

Action Step:

* ...
"""


# ---------------------------------------------------------------------------
# Frontend visualization payload helpers
# ---------------------------------------------------------------------------

def build_chart_points(windows, score_key):
    """Convert metric windows into x/y points for React visualizations."""
    points = []

    for window in windows:
        score = window.get(score_key)

        if score is None:
            continue

        start = window.get("start")
        end = window.get("end")
        points.append(
            {
                "x": float(start if start is not None else window["time_range"].split("-", 1)[0]),
                "y": float(score),
                "start": float(start) if start is not None else None,
                "end": float(end) if end is not None else None,
                "label": window["time_range"],
            }
        )

    return points


def build_harmonic_chart_points(windows):
    """Include composite components and ambiguous regions in the harmony lane."""
    points = []

    for window in windows:
        components = {
            "diatonic_deviation": window.get("diatonic_deviation"),
            "harmonic_movement": window.get("harmonic_movement"),
            "tonal_instability": window.get("tonal_instability"),
            "voicing_density": window.get("voicing_density"),
            "modulation_load": window.get("modulation_load"),
            "harmonic_color": window.get("harmonic_color"),
        }
        tooltip = (
            "Low-confidence harmonic evidence"
            if window.get("ambiguous")
            else " · ".join(
                f"{name.replace('_', ' ')} {format_score(value)}"
                for name, value in components.items()
            )
        )
        points.append(
            {
                "x": float(window["start"]),
                "y": window.get("harmonic_complexity"),
                "start": float(window["start"]),
                "end": float(window["end"]),
                "label": window["time_range"],
                "ambiguous": bool(window.get("ambiguous")),
                "evidence_label": window.get("harmonic_evidence"),
                "modulation_state": window.get("modulation_state"),
                "components": components,
                "tooltip": tooltip,
            }
        )

    return points


def downsample_matrix(matrix, target_rows, target_cols):
    """Shrink spectrogram/chroma matrices so API responses stay lightweight."""
    row_idx = np.linspace(0, matrix.shape[0] - 1, min(target_rows, matrix.shape[0])).astype(int)
    col_idx = np.linspace(0, matrix.shape[1] - 1, min(target_cols, matrix.shape[1])).astype(int)
    sampled = matrix[np.ix_(row_idx, col_idx)]

    if sampled.size == 0:
        return []

    sampled = sampled - np.min(sampled)
    max_value = np.max(sampled)

    if max_value > 0:
        sampled = sampled / max_value

    return sampled.tolist()


def enhanced_chroma(y, sr, harmonic_signal=None):
    """Build a cleaned chroma matrix for pitch-class lane visualization."""
    y_harm = (
        harmonic_signal
        if harmonic_signal is not None
        else librosa.effects.harmonic(y=y, margin=8)
    )
    chroma = librosa.feature.chroma_cqt(
        y=y_harm,
        sr=sr,
        bins_per_octave=12 * 3,
    )
    chroma = np.minimum(
        chroma,
        librosa.decompose.nn_filter(
            chroma,
            aggregate=np.median,
            metric="cosine",
        ),
    )
    chroma = scipy.ndimage.median_filter(chroma, size=(1, 9))
    chroma = chroma - np.min(chroma)
    max_value = np.max(chroma)

    if max_value > 0:
        chroma = chroma / max_value

    return chroma


def build_waveform_points(y, duration, max_points=260):
    """Sample waveform min/max/RMS values for the main signal deck."""
    if len(y) == 0:
        return []

    chunk_count = min(max_points, len(y))
    chunks = np.array_split(y, chunk_count)
    points = []

    for index, chunk in enumerate(chunks):
        if len(chunk) == 0:
            continue

        points.append(
            {
                "x": float((index / max(1, chunk_count - 1)) * duration),
                "min": float(np.min(chunk)),
                "max": float(np.max(chunk)),
                "rms": float(np.sqrt(np.mean(chunk**2))),
            }
        )

    return points


def build_signal_visuals(y, sr, duration, harmonic_signal=None):
    """Create waveform, spectrogram, and chroma payloads for the UI."""
    mel = librosa.feature.melspectrogram(
        y=y,
        sr=sr,
        n_mels=64,
        fmax=min(10000, sr / 2),
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    chroma = enhanced_chroma(y, sr, harmonic_signal=harmonic_signal)

    return {
        "waveform": build_waveform_points(y, duration),
        "spectrogram": {
            "rows": downsample_matrix(mel_db, 48, 120),
            "time_bins": min(120, mel_db.shape[1]),
            "frequency_bins": min(48, mel_db.shape[0]),
        },
        "chroma": {
            "rows": downsample_matrix(chroma, 12, 120),
            "labels": ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"],
            "duration": float(duration),
        },
    }


# ---------------------------------------------------------------------------
# User-facing summaries and OpenAI follow-up helpers
# ---------------------------------------------------------------------------

def build_topline_summary(
    tempo_analysis,
    pitch_analysis,
    harmony_analysis,
    dynamics_analysis,
):
    """Choose a performance weakness or a genuinely notable harmony result."""
    scores = {
        "tempo": tempo_analysis["overall_score"],
        "dynamics": dynamics_analysis["overall_score"],
    }

    if pitch_analysis.get("reliability") in {"medium", "high"}:
        scores["pitch"] = pitch_analysis["overall_score"]

    scores = {name: score for name, score in scores.items() if score is not None}

    if not scores:
        return "The recording did not provide enough reliable metric evidence for a topline diagnosis."

    weakest_metric = min(scores, key=scores.get)
    harmony_score = harmony_analysis.get("overall_score")
    if (
        harmony_score is not None
        and harmony_score >= HARMONIC_HOTSPOT_THRESHOLD
        and scores[weakest_metric] >= 0.70
    ):
        weakest_metric = "harmony"

    if weakest_metric == "tempo":
        return "Timing consistency is the main area to inspect; use the tempo window map to locate unstable sections."

    if weakest_metric == "pitch":
        return "Pitch accuracy is the main diagnostic focus, especially in the lowest-scoring phrase windows."

    if weakest_metric == "harmony":
        driver = harmony_analysis.get("dominant_factors", ["harmonic evidence"])[0]
        return (
            f"The harmonic composite is led by {driver.replace('_', ' ')}; compare "
            "its component panel with confident local windows and modulation boundaries."
        )

    return "Dynamics contour is the main area to inspect; look for windows where RMS energy does not follow a steady line, fade, or smooth ramp."


def ask_follow_up(project_context, question):
    """Answer a project-specific follow-up using the saved analysis context."""
    prompt = f"""You are Interlude's music diagnostics assistant.

Use this saved analysis context to answer the user's follow-up question. Be specific, concise, and practical.
Write in plain text only. Do not use LaTeX, math delimiters, markdown tables, or symbolic equations.

Saved analysis context:
{project_context}

Question:
{question}
"""

    try:
        response = get_client().responses.create(
            model=get_text_feedback_model(),
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
        )
        return {"response": response.output_text, "api_error": None}
    except Exception as exc:
        return {
            "response": f"The follow-up request could not reach the OpenAI API: {exc}",
            "api_error": str(exc),
        }


def vocal_separation_available():
    """Report whether the optional Demucs package can be imported."""
    try:
        return importlib.util.find_spec("demucs") is not None
    except (ImportError, ValueError):
        return False


def separate_vocal_stem(song_path, duration, target_sr=None):
    """Run Demucs two-stem separation and load only the temporary vocal stem."""
    if not vocal_separation_available():
        raise VocalSeparationError(
            "Vocal separation is unavailable. Install requirements-vocal.txt and restart Interlude."
        )

    timeout_seconds = max(600.0, 4.0 * float(duration))

    try:
        with tempfile.TemporaryDirectory(prefix="interlude-vocals-") as output_dir:
            command = [
                sys.executable,
                "-m",
                "demucs",
                "--two-stems",
                "vocals",
                "-n",
                VOCAL_SEPARATION_MODEL,
                "-o",
                output_dir,
                str(song_path),
            ]
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            vocal_stems = list(Path(output_dir).rglob("vocals.wav"))

            if len(vocal_stems) != 1 or vocal_stems[0].stat().st_size == 0:
                raise VocalSeparationError(
                    "Vocal separation completed without producing a usable vocal stem."
                )

            vocal_y, vocal_sr = librosa.load(
                vocal_stems[0],
                sr=target_sr,
                mono=True,
            )

            if not len(vocal_y) or np.max(np.abs(vocal_y)) <= 1e-8:
                raise VocalSeparationError(
                    "Vocal separation produced an empty or silent vocal stem."
                )

            return vocal_y, vocal_sr
    except subprocess.TimeoutExpired as exc:
        raise VocalSeparationError(
            f"Vocal separation timed out after {timeout_seconds:.0f} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        suffix = f" ({detail[-1]})" if detail else ""
        raise VocalSeparationError(f"Vocal separation failed{suffix}.") from exc
    except VocalSeparationError:
        raise
    except (OSError, ValueError) as exc:
        raise VocalSeparationError(
            "Vocal separation did not produce readable audio."
        ) from exc


# ---------------------------------------------------------------------------
# Main analysis orchestration
# ---------------------------------------------------------------------------

def run_interlude_analysis(
    song_path,
    root=None,
    scale_type=None,
    extra_prompt="",
    separate_vocals=False,
):
    """Run the complete Interlude analysis pipeline for one uploaded song.

    This is the main function called by app.py. It returns one dictionary with
    metadata, scores, window traces, visualization data, and OpenAI feedback.
    """
    # 1. Decode audio once, then reuse the waveform for every local metric.
    y, sr = librosa.load(song_path, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    key_profile = build_key_chroma_profile(y, sr)
    detected_key = detect_key_and_mode(key_profile)
    onset_envelope = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sr,
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 0.0
    harmonic_signal = librosa.effects.harmonic(y=y, margin=8)

    # 2. Compute all local metrics before contacting the OpenAI API.
    tempo_analysis = analyze_tempo_stability(beat_times, duration, bpm)
    harmony_analysis = analyze_harmonic_complexity(
        y,
        sr,
        beat_times,
        duration,
        root_override=root,
        scale_override=scale_type,
        harmonic_signal=harmonic_signal,
        detected_key=detected_key,
    )
    if separate_vocals:
        pitch_signal, pitch_sr = separate_vocal_stem(
            song_path,
            duration,
            target_sr=sr,
        )
        pitch_source = "vocal_stem"
    else:
        pitch_signal, pitch_sr = harmonic_signal, sr
        pitch_source = "full_mix_harmonic"

    pitch_analysis = analyze_pitch_accuracy(
        pitch_signal,
        pitch_sr,
        beat_times,
        duration,
        source=pitch_source,
    )
    pitch_analysis = cap_pitch_reliability_for_polyphony(
        pitch_analysis,
        harmony_analysis["polyphony"]["warning"],
    )
    dynamics_analysis = analyze_dynamics(y, sr, beat_times, duration)

    # 3. Build a compact evidence prompt from the local analysis.
    prompt = build_prompt(
        tempo_analysis,
        pitch_analysis,
        harmony_analysis,
        dynamics_analysis,
        extra_prompt=extra_prompt,
    )
    try:
        # 4. Send supported song audio as audio input, not as a document file.
        response_text = request_music_feedback(prompt, song_path)
        api_error = None
    except Exception as exc:
        # Keep the local analysis usable even if credentials/network/API fail.
        response_text = (
            "The local analysis completed, but the OpenAI API request failed: "
            f"{exc}"
        )
        api_error = str(exc)

    analysis_key = harmony_analysis["analysis_key"]
    song_path = Path(song_path)
    project_title = song_path.stem
    created_at = datetime.now(timezone.utc).isoformat()
    topline_summary = build_topline_summary(
        tempo_analysis,
        pitch_analysis,
        harmony_analysis,
        dynamics_analysis,
    )

    # 5. Shape the response for the frontend: metadata, readouts, charts, visuals.
    return {
        "response": response_text,
        "api_error": api_error,
        "project": {
            "title": project_title,
            "filename": song_path.name,
            "created_at": created_at,
            "duration": float(duration),
            "sample_rate": int(sr),
            "bpm": bpm,
        },
        "summary": topline_summary,
        "scores": {
            "tempo_stability": tempo_analysis["overall_score"],
            "pitch_accuracy": pitch_analysis["overall_score"],
            "harmonic_complexity": harmony_analysis["overall_score"],
            "harmonic_evidence_score": harmony_analysis["evidence_score"],
            "raw_harmonic_complexity": harmony_analysis["raw_score"],
            "diatonic_deviation": harmony_analysis["diatonic_deviation"],
            "harmonic_movement": harmony_analysis["harmonic_movement"],
            "tonal_stability": harmony_analysis["tonal_stability"],
            "tonal_instability": harmony_analysis["tonal_instability"],
            "voicing_density": harmony_analysis["voicing_density"],
            "modulation_load": harmony_analysis["modulation_load"],
            "harmonic_color": harmony_analysis["harmonic_color"],
            "dynamics_variation": dynamics_analysis["overall_score"],
        },
        "key": {
            "root": analysis_key["root"],
            "scale_type": analysis_key["scale_type"],
            "fit": analysis_key["fit"],
            "mode": "manual" if root and scale_type else "auto",
            "detection": {
                "algorithm": detected_key["algorithm"],
                "root": detected_key["root"],
                "scale_type": detected_key["scale_type"],
                "correlation": detected_key["correlation"],
                "runner_up_margin": detected_key["correlation_margin"],
                "profile_type": detected_key["profile_type"],
            },
        },
        "tempo_tracking": {
            "global_bpm": tempo_analysis["global_bpm"],
            "median_bpm": tempo_analysis["median_bpm"],
            "target_interval": tempo_analysis["target_interval"],
            "mean_log_interval_error": tempo_analysis["mean_log_interval_error"],
            "interval_count": tempo_analysis["beat_interval_count"],
            "log_tolerance": tempo_analysis["log_tolerance"],
        },
        "pitch_tracking": {
            "source": pitch_analysis["source"],
            "reliability": pitch_analysis["reliability"],
            "voiced_frame_ratio": pitch_analysis["voiced_frame_ratio"],
            "mean_voiced_probability": pitch_analysis["mean_voiced_probability"],
            "effective_voiced_ratio": pitch_analysis["effective_voiced_ratio"],
            "valid_pitch_frames": pitch_analysis["valid_pitch_frames"],
            "effective_voiced_frames": pitch_analysis["effective_voiced_frames"],
            "mean_abs_cents_error": pitch_analysis["mean_abs_cents_error"],
            "polyphony_limited": pitch_analysis["polyphony_limited"],
        },
        "harmonic_analysis": {
            "components": {
                "diatonic_deviation": harmony_analysis["diatonic_deviation"],
                "adjusted_diatonic_deviation": harmony_analysis[
                    "adjusted_diatonic_deviation"
                ],
                "harmonic_movement": harmony_analysis["harmonic_movement"],
                "tonal_stability": harmony_analysis["tonal_stability"],
                "tonal_instability": harmony_analysis["tonal_instability"],
                "voicing_density": harmony_analysis["voicing_density"],
                "modulation_load": harmony_analysis["modulation_load"],
                "harmonic_color": harmony_analysis["harmonic_color"],
            },
            "evidence_score": harmony_analysis["evidence_score"],
            "normalization": harmony_analysis["normalization"],
            "weights": harmony_analysis["weights"],
            "weighted_contributions": harmony_analysis["weighted_contributions"],
            "dominant_factors": harmony_analysis["dominant_factors"],
            "confidence": harmony_analysis["confidence"],
            "modulation": harmony_analysis["modulation"],
            "movement": harmony_analysis["movement"],
        },
        "polyphony": harmony_analysis["polyphony"],
        "charts": {
            "tempo": build_chart_points(tempo_analysis["windows"], "score"),
            "pitch": build_chart_points(pitch_analysis["windows"], "score"),
            "harmony": build_harmonic_chart_points(harmony_analysis["windows"]),
            "diatonic_deviation": build_chart_points(
                harmony_analysis["windows"],
                "diatonic_deviation",
            ),
            "harmonic_movement": build_chart_points(
                harmony_analysis["windows"],
                "harmonic_movement",
            ),
            "tonal_stability": build_chart_points(
                harmony_analysis["windows"],
                "tonal_stability",
            ),
            "voicing_density": build_chart_points(
                harmony_analysis["windows"],
                "voicing_density",
            ),
            "modulation_load": build_chart_points(
                harmony_analysis["windows"],
                "modulation_load",
            ),
            "harmonic_color": build_chart_points(
                harmony_analysis["windows"],
                "harmonic_color",
            ),
            "dynamics": build_chart_points(dynamics_analysis["windows"], "score"),
        },
        "windows": {
            "tempo": tempo_analysis["windows"],
            "pitch": pitch_analysis["windows"],
            "harmony": harmony_analysis["windows"],
            "dynamics": dynamics_analysis["windows"],
        },
        "visuals": build_signal_visuals(
            y,
            sr,
            duration,
            harmonic_signal=harmonic_signal,
        ),
        "prompt": prompt,
    }


def main():
    """Manual CLI entry point for quick local testing without the web app."""
    result = run_interlude_analysis(filename)
    scores = result["scores"]
    analysis_key = result["key"]

    print("Tempo Stability Score:", format_score(scores["tempo_stability"]))
    print("Pitch Accuracy Score:", format_score(scores["pitch_accuracy"]))
    print(
        "Adjusted Harmonic Complexity Score:",
        format_score(scores["harmonic_complexity"]),
    )
    print("Raw Harmonic Complexity Score:", format_score(scores["raw_harmonic_complexity"]))
    print("Dynamics Contour Score:", format_score(scores["dynamics_variation"]))
    print(
        "Detected Key/Mode:",
        analysis_key["root"],
        analysis_key["scale_type"],
    )

    print(result["response"])


if __name__ == "__main__":
    main()
