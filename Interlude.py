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
import os

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
MIN_MODULATION_WINDOWS = 2

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

RHYTHM_GRID = np.array([0.0, 0.25, 1 / 3, 0.5, 2 / 3, 0.75, 1.0])


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


def score_from_errors(errors, tolerance):
    """Convert an array of timing/pitch errors into a 0-1 score."""
    if len(errors) == 0:
        return None

    return float(1 / (1 + np.mean(errors) / tolerance))


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


def filter_spurious_onsets(onset_frames, onset_env, sr, hop_length):
    """Remove weak or duplicate onset detections before tempo scoring."""
    if len(onset_frames) == 0:
        return np.array([])

    onset_frames = np.asarray(onset_frames)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
    onset_strengths = onset_env[onset_frames]
    strength_floor = np.percentile(onset_strengths, 35)

    keep = onset_strengths >= strength_floor
    filtered_times = onset_times[keep]
    filtered_strengths = onset_strengths[keep]

    if len(filtered_times) <= 1:
        return filtered_times

    deduped_times = []
    deduped_strengths = []
    min_gap_seconds = 0.045

    for onset_time, strength in zip(filtered_times, filtered_strengths):
        if not deduped_times or onset_time - deduped_times[-1] >= min_gap_seconds:
            deduped_times.append(float(onset_time))
            deduped_strengths.append(float(strength))
            continue

        if strength > deduped_strengths[-1]:
            deduped_times[-1] = float(onset_time)
            deduped_strengths[-1] = float(strength)

    return np.asarray(deduped_times)


def onset_grid_errors(onsets, beat_times):
    """Measure how far each onset lands from the nearest beat subdivision."""
    errors = []

    for onset in onsets:
        beat_idx = np.searchsorted(beat_times, onset) - 1

        if beat_idx < 0 or beat_idx >= len(beat_times) - 1:
            continue

        beat_start = beat_times[beat_idx]
        beat_end = beat_times[beat_idx + 1]
        beat_duration = beat_end - beat_start

        if beat_duration <= 0:
            continue

        beat_position = (onset - beat_start) / beat_duration
        errors.append(float(np.min(np.abs(RHYTHM_GRID - beat_position))))

    return np.asarray(errors)


# ---------------------------------------------------------------------------
# Metric analyzers
# ---------------------------------------------------------------------------

def analyze_tempo_stability(y, sr, beat_times, duration, hop_length=512):
    """Score timing stability in beat-synchronous windows.

    The metric detects note attacks, filters noisy detections, and measures how
    close each attack is to a rhythm grid inside the current beat. Syncopated
    and swung subdivisions are included in RHYTHM_GRID so complexity is not
    automatically treated as bad timing.
    """
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        units="frames",
        # Backtracking moves detections to the pre-attack energy minimum.
        # That is useful for slicing, but it makes tight drums look early when
        # the goal is timing displacement from a beat grid.
        backtrack=False,
        pre_max=3,
        post_max=3,
        pre_avg=3,
        post_avg=5,
        delta=0.2,
        wait=2,
    )
    onsets = filter_spurious_onsets(onset_frames, onset_env, sr, hop_length)
    windows = beat_windows(beat_times, duration, BEATS_PER_TEMPO_WINDOW)

    tempo_windows = []
    all_errors = []

    for window_number, start_time, end_time, label in windows:
        # Each score represents a local musical region, not the whole song.
        local_onsets = onsets[(onsets >= start_time) & (onsets < end_time)]
        local_errors = onset_grid_errors(local_onsets, beat_times)
        all_errors.extend(local_errors)
        score = score_from_errors(local_errors, tolerance=0.055)

        tempo_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "score": score,
                "onset_count": int(len(local_onsets)),
                "mean_grid_error": (
                    float(np.mean(local_errors)) if len(local_errors) > 0 else None
                ),
            }
        )

    overall_score = score_from_errors(np.asarray(all_errors), tolerance=0.055)
    unstable_windows = [
        window
        for window in tempo_windows
        if window["score"] is not None and window["score"] < 0.72
    ]

    return {
        "overall_score": overall_score,
        "windows": tempo_windows,
        "unstable_windows": unstable_windows,
        "onset_count": int(len(onsets)),
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


def analyze_pitch_accuracy(y, sr, beat_times, duration):
    """Score monophonic pitch accuracy over phrase-sized beat windows."""
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
    )
    frame_times = librosa.times_like(f0, sr=sr)
    valid = (~np.isnan(f0)) & voiced_flag & (voiced_prob > 0.7)
    pitch_errors = vibrato_tolerant_pitch_errors(f0)
    pitch_scores = np.full_like(pitch_errors, np.nan, dtype=float)
    pitch_scores[valid] = np.exp(-pitch_errors[valid] / 100)
    windows = beat_windows(beat_times, duration, BEATS_PER_PITCH_WINDOW)

    pitch_windows = []
    for window_number, start_time, end_time, label in windows:
        # pYIN is most reliable on voiced monophonic material, so gate by confidence.
        in_window = (frame_times >= start_time) & (frame_times < end_time) & valid
        valid_count = int(np.sum(in_window))
        score = float(np.nanmean(pitch_scores[in_window])) if valid_count > 0 else None

        pitch_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "score": score,
                "valid_pitch_frames": valid_count,
                "mean_abs_cents_error": (
                    float(np.nanmean(pitch_errors[in_window]))
                    if valid_count > 0
                    else None
                ),
            }
        )

    overall_score = (
        float(np.nanmean(pitch_scores[valid])) if np.any(valid) else None
    )
    weak_windows = [
        window
        for window in pitch_windows
        if window["score"] is not None and window["score"] < 0.72
    ]

    return {
        "overall_score": overall_score,
        "windows": pitch_windows,
        "weak_windows": weak_windows,
        "valid_pitch_frames": int(np.sum(valid)),
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


def detect_key_and_mode(chroma_profile):
    """Search all supported roots and modes for the best chroma fit."""
    best = {
        "root": "C",
        "scale_type": "major",
        "fit": -1.0,
    }

    for root in INDEX_TO_NOTE.values():
        for scale_type in SCALE_PATTERNS:
            fit = key_fit(chroma_profile, root, scale_type)

            if fit > best["fit"]:
                best = {
                    "root": root,
                    "scale_type": scale_type,
                    "fit": fit,
                }

    return best


def detect_sustained_modulations(harmony_windows, root, scale_type):
    """Find runs of windows that confidently settle into another key/mode."""
    run_start = None
    run_key = None
    sustained_window_numbers = set()

    for index, window in enumerate(harmony_windows):
        local_key = (window["local_root"], window["local_scale_type"])
        is_different_key = local_key != (root, scale_type)
        is_confident = window["local_key_fit"] >= 0.72

        if is_different_key and is_confident:
            if run_key == local_key:
                pass
            else:
                run_start = index
                run_key = local_key
        else:
            if run_start is not None and index - run_start >= MIN_MODULATION_WINDOWS:
                for modulated_index in range(run_start, index):
                    sustained_window_numbers.add(harmony_windows[modulated_index]["window"])
            run_start = None
            run_key = None

    if run_start is not None and len(harmony_windows) - run_start >= MIN_MODULATION_WINDOWS:
        for modulated_index in range(run_start, len(harmony_windows)):
            sustained_window_numbers.add(harmony_windows[modulated_index]["window"])

    return sustained_window_numbers


def analyze_harmonic_complexity(y, sr, beat_times, duration, root_override=None, scale_override=None):
    """Measure non-diatonic harmonic energy in bar-sized beat windows.

    The score is based on how much local chroma energy falls outside the
    detected or manually selected key/mode. Sustained modulations are softened
    so they do not read as accidental harmonic messiness.
    """
    y_harm = librosa.effects.harmonic(y=y, margin=8)
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
    chroma_times = librosa.times_like(chroma, sr=sr)
    chroma_profile = np.sum(chroma, axis=1)
    detected_key = detect_key_and_mode(chroma_profile)
    root = root_override or USER_ROOT or detected_key["root"]
    scale_type = scale_override or USER_SCALE_TYPE or detected_key["scale_type"]
    analysis_key_fit = key_fit(chroma_profile, root, scale_type)
    scale_mask = get_scale_mask(root, scale_type)[:, None]
    windows = beat_windows(beat_times, duration, BEATS_PER_HARMONY_WINDOW)

    harmony_windows = []
    for window_number, start_time, end_time, label in windows:
        # Local chroma windows let the UI show where harmonic density changes.
        in_window = (chroma_times >= start_time) & (chroma_times < end_time)

        if not np.any(in_window):
            continue

        local_chroma = chroma[:, in_window]
        frame_total = np.sum(local_chroma, axis=0)
        frame_non_diatonic = np.sum(local_chroma * (1 - scale_mask), axis=0)
        valid_frames = frame_total > 0

        if not np.any(valid_frames):
            continue

        frame_ratio = frame_non_diatonic[valid_frames] / frame_total[valid_frames]
        local_profile = np.sum(local_chroma, axis=1)
        local_key = detect_key_and_mode(local_profile)

        harmony_windows.append(
            {
                "window": window_number,
                "time_range": label,
                "start": start_time,
                "end": end_time,
                "raw_complexity": float(np.mean(frame_ratio)),
                "local_root": local_key["root"],
                "local_scale_type": local_key["scale_type"],
                "local_key_fit": local_key["fit"],
            }
        )

    modulation_windows = detect_sustained_modulations(
        harmony_windows,
        root,
        scale_type,
    )

    for window in harmony_windows:
        is_modulation = window["window"] in modulation_windows
        window["sustained_modulation"] = is_modulation
        # Modulations are musically meaningful, so reduce their complexity penalty.
        window["adjusted_complexity"] = (
            window["raw_complexity"] * 0.45 if is_modulation else window["raw_complexity"]
        )

    adjusted_values = [window["adjusted_complexity"] for window in harmony_windows]
    raw_values = [window["raw_complexity"] for window in harmony_windows]
    high_complexity_windows = [
        window for window in harmony_windows if window["adjusted_complexity"] > 0.35
    ]

    return {
        "overall_score": float(np.mean(adjusted_values)) if adjusted_values else None,
        "raw_score": float(np.mean(raw_values)) if raw_values else None,
        "windows": harmony_windows,
        "high_complexity_windows": high_complexity_windows,
        "detected_key": detected_key,
        "analysis_key": {
            "root": root,
            "scale_type": scale_type,
            "fit": analysis_key_fit,
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
        "adjusted_complexity",
        high_is_notable=True,
    )
    dynamics_summary = format_window_summary(
        dynamics_analysis["windows"],
        "score",
    )
    analysis_key = harmony_analysis["analysis_key"]
    polyphony_warning = (
        "Likely polyphonic sections were detected, so pYIN pitch accuracy may be less reliable."
        if harmony_analysis["polyphony"]["warning"]
        else "The pitch tracker did not detect heavy polyphonic density."
    )
    extra_prompt_section = (
        f"\nAdditional user request:\n{extra_prompt.strip()}\n"
        if extra_prompt and extra_prompt.strip()
        else ""
    )

    return f"""You are a music analysis assistant. Interpret the metrics and provide concise, actionable songwriting feedback.

When an audio input is attached, it is the actual song being analyzed. Use the computed metrics as the primary evidence, and use the audio only as supporting context.

Metrics:

1. Tempo Stability (0-1)

* Measures how closely note attacks align to local beat, subdivision, and swing-aware timing grids.
* Higher values indicate stable timing inside beat-synchronous windows.
* Lower local values identify sections where timing may feel unstable.
* Syncopation and swing should not be treated as timing mistakes by themselves.

2. Pitch Accuracy (0-1)

* Measures pitch accuracy relative to equal-tempered tuning in phrase-sized windows.
* The calculation smooths short vibrato and softens penalties during bend-like motion.
* Lower local values identify phrases that may need tuning attention.

3. Harmonic Complexity (0-1)

* Measures local non-diatonic harmonic energy against the detected key/mode.
* The calculation uses bar-based windows and reduces the penalty for sustained modulations.
* Higher values suggest chromaticism, borrowed tones, modulation, or harmonic density.

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
{extra_prompt_section}

Measured scores:

Tempo Stability Score: {format_score(tempo_analysis["overall_score"])}
Pitch Accuracy Score: {format_score(pitch_analysis["overall_score"])}
Adjusted Harmonic Complexity Score: {format_score(harmony_analysis["overall_score"])}
Raw Harmonic Complexity Score: {format_score(harmony_analysis["raw_score"])}
Dynamics Contour Score: {format_score(dynamics_analysis["overall_score"])}
Detected Key/Mode: {analysis_key["root"]} {analysis_key["scale_type"]} (fit={analysis_key["fit"]:.3f})
Polyphony Note: {polyphony_warning}

Least stable tempo windows:
{tempo_summary}

Weakest pitch windows:
{pitch_summary}

Most complex harmony windows:
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


def enhanced_chroma(y, sr):
    """Build a cleaned chroma matrix for pitch-class lane visualization."""
    y_harm = librosa.effects.harmonic(y=y, margin=8)
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


def build_signal_visuals(y, sr, duration):
    """Create waveform, spectrogram, and chroma payloads for the UI."""
    mel = librosa.feature.melspectrogram(
        y=y,
        sr=sr,
        n_mels=64,
        fmax=min(10000, sr / 2),
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    chroma = enhanced_chroma(y, sr)

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
    """Choose a short summary based on whichever metric is weakest."""
    scores = {
        "tempo": tempo_analysis["overall_score"] or 0,
        "pitch": pitch_analysis["overall_score"] or 0,
        "harmony": harmony_analysis["overall_score"] or 0,
        "dynamics": dynamics_analysis["overall_score"] or 0,
    }
    weakest_metric = min(scores, key=scores.get)

    if weakest_metric == "tempo":
        return "Timing consistency is the main area to inspect; use the tempo window map to locate unstable sections."

    if weakest_metric == "pitch":
        return "Pitch accuracy is the main diagnostic focus, especially in the lowest-scoring phrase windows."

    if weakest_metric == "harmony":
        return "Harmonic movement is the densest signal; compare the complexity map with the detected key and local modulation windows."

    return "Dynamics contour is the main area to inspect; look for windows where RMS energy does not follow a steady line, fade, or smooth ramp."


def ask_follow_up(project_context, question):
    """Answer a project-specific follow-up using the saved analysis context."""
    prompt = f"""You are Interlude's music diagnostics assistant.

Use this saved analysis context to answer the user's follow-up question. Be specific, concise, and practical.

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


# ---------------------------------------------------------------------------
# Main analysis orchestration
# ---------------------------------------------------------------------------

def run_interlude_analysis(song_path, root=None, scale_type=None, extra_prompt=""):
    """Run the complete Interlude analysis pipeline for one uploaded song.

    This is the main function called by app.py. It returns one dictionary with
    metadata, scores, window traces, visualization data, and OpenAI feedback.
    """
    # 1. Decode audio once, then reuse the waveform for every local metric.
    y, sr = librosa.load(song_path, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # 2. Compute all local metrics before contacting the OpenAI API.
    tempo_analysis = analyze_tempo_stability(y, sr, beat_times, duration)
    pitch_analysis = analyze_pitch_accuracy(y, sr, beat_times, duration)
    harmony_analysis = analyze_harmonic_complexity(
        y,
        sr,
        beat_times,
        duration,
        root_override=root,
        scale_override=scale_type,
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
    bpm = float(np.atleast_1d(tempo)[0])
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
            "raw_harmonic_complexity": harmony_analysis["raw_score"],
            "dynamics_variation": dynamics_analysis["overall_score"],
        },
        "key": {
            "root": analysis_key["root"],
            "scale_type": analysis_key["scale_type"],
            "fit": analysis_key["fit"],
            "mode": "manual" if root and scale_type else "auto",
        },
        "polyphony": harmony_analysis["polyphony"],
        "charts": {
            "tempo": build_chart_points(tempo_analysis["windows"], "score"),
            "pitch": build_chart_points(pitch_analysis["windows"], "score"),
            "harmony": build_chart_points(
                harmony_analysis["windows"],
                "adjusted_complexity",
            ),
            "dynamics": build_chart_points(dynamics_analysis["windows"], "score"),
        },
        "windows": {
            "tempo": tempo_analysis["windows"],
            "pitch": pitch_analysis["windows"],
            "harmony": harmony_analysis["windows"],
            "dynamics": dynamics_analysis["windows"],
        },
        "visuals": build_signal_visuals(y, sr, duration),
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
