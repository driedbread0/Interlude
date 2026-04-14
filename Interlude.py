import librosa
import numpy as np
import matplotlib.pyplot as plt

# filename = librosa.example('trumpet')
filename = ("/Users/27PranT/Desktop/Billie Jean (Long Version) - Michael Jackson (128k).wav")

y, sr = librosa.load(filename)

tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time')
y, sr = librosa.load(librosa.ex('trumpet'))
f0, voiced_flag, voiced_prob = librosa.pyin(
    y,
    fmin=librosa.note_to_hz("C2"),
    fmax=librosa.note_to_hz("C7")
)
times = librosa.times_like(f0, sr=sr)


expected_interval = 60 / tempo.item()
intervals = np.diff(onsets)

normalized_tempo = intervals / expected_interval

valid_tempo = np.array([1, 0.5, 0.25, 0.125])

diffs_tempo = np.abs(normalized_tempo[:, None] - valid_tempo)
closest_tempo = valid_tempo[np.argmin(diffs_tempo, axis=1)]

error = np.abs(normalized_tempo - closest_tempo)
weight = 1 / closest_tempo

weighted_error = error * weight
MAE_Tempo = np.mean(weighted_error)

score_tempo = 1 / (1 + MAE_Tempo)

import math

ET_notes = []
A4 = 440.0

# ts the generation of frequencies
for n in range(-33, 28):
    ET_freq = A4 * (2 ** (n / 12))
    ET_notes.append(ET_freq)

valid_pitch = np.array([ET_notes])

diffs_pitch = np.abs(f0[:, None] - valid_pitch)
closest_pitch = valid_pitch[np.argmin(diffs_pitch, axis=1)]

error_cents = 1200 * np.log2(f0 / closest_pitch)
abs_error_cents = np.abs(error_cents)
mean_cents_error = np.mean(abs_error_cents)

print("Tempo Score:", score_tempo)
print(mean_cents_error)

plt.plot(weighted_error)
plt.title("Timing Error Over Time")
plt.xlabel("Event Index")
plt.ylabel("Weighted Error")
plt.show()