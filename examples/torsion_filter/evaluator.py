"""
evaluator.py -- research-grade evaluator for evolving torsion-balance noise filters.

Deterministic. No LLM anywhere near the fitness function.

Scoring philosophy (fixes applied vs. naive scaffold evaluator):
  1. The objective (SNR gain at the known target frequency) is computed
     directly from data -- never delegated to prose or an LLM judge.
  2. combined_score is reported RELATIVE to a tuned Butterworth lowpass
     baseline: combined_score > 0 means the candidate beats a competent
     human-engineered filter. Non-saturating by construction.
  3. Distortion penalty: a candidate that "improves SNR" by destroying the
     signal (e.g. zeroing everything) is penalized via >3 dB attenuation
     at the target frequency.
  4. Robust fitness: median over fixed seeds minus 0.5 * std, so lucky
     single-seed results don't dominate.
  5. Held-out mode: validate_heldout() scores a champion on seeds the
     evolution never saw. Train seeds must never appear in prompts.

OpenEvolve entry point: evaluate(program_path) -> dict with combined_score.
"""
import importlib.util
import sys

import numpy as np
from scipy import signal

# ---------- configuration ----------
FS = 1000.0          # Hz, sample rate (toy scale; drop to real rate for real data)
T_TRIAL = 20.0       # seconds per trial
F_SIGNAL = 5.0       # Hz, known target frequency
TRAIN_SEEDS = [11, 23, 37, 53, 71]          # used during evolution
HELDOUT_SEEDS = [101, 203, 307, 409, 503]   # final validation only
CANDIDATE_FN_NAMES = ["apply_filter", "evolve_filter", "filter_signal", "denoise"]


# ---------- synthetic data (deterministic given seed) ----------
def make_trial(seed, fs=FS, t=T_TRIAL, f_signal=F_SIGNAL):
    rng = np.random.default_rng(seed)
    n = int(fs * t)
    time = np.arange(n) / fs
    amp = rng.uniform(0.5, 2.0)  # unknown signal amplitude
    clean = amp * np.sin(2 * np.pi * f_signal * time + rng.uniform(0, 2 * np.pi))
    white = rng.normal(0, 1.0, n)
    pink = np.convolve(rng.normal(0, 1, n), np.ones(8) / 8, mode="same")  # cheap 1/f-ish
    line = 0.5 * np.sin(2 * np.pi * 60.0 * time)                          # line interference
    drift = np.linspace(0, rng.uniform(-1, 1), n)                         # slow baseline drift
    noisy = clean + 0.8 * white + 1.5 * pink + line + drift
    return time, clean, noisy


# ---------- metrics ----------
def band_snr_db(x, fs, f_signal):
    f, P = signal.welch(x, fs=fs, nperseg=int(fs * 4))
    sig = (f >= f_signal - 0.4) & (f <= f_signal + 0.4)
    guard = (f >= f_signal - 1.0) & (f <= f_signal + 1.0)
    noise_band = (f >= 1.0) & (f <= 50.0) & ~guard & (np.abs(f - 60) > 2)
    ps = np.trapezoid(P[sig], f[sig])
    pn = np.trapezoid(P[noise_band], f[noise_band])
    return 10 * np.log10(max(ps, 1e-20) / max(pn, 1e-20))


def attenuation_db(candidate_out, clean, fs, f_signal):
    def amp_at(x):
        n = len(x)
        w = np.hanning(n)
        X = np.abs(np.fft.rfft(x * w))
        freqs = np.fft.rfftfreq(n, 1 / fs)
        return X[np.argmin(np.abs(freqs - f_signal))] * 2 / w.sum()
    return 20 * np.log10(max(amp_at(candidate_out), 1e-12) / max(amp_at(clean), 1e-12))


# ---------- candidate loading ----------
def load_candidate(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in CANDIDATE_FN_NAMES:
        if hasattr(mod, name):
            return getattr(mod, name)
    raise AttributeError(f"No filter function found (tried {CANDIDATE_FN_NAMES})")


# ---------- core evaluation ----------
def evaluate_with_seeds(fn, seeds):
    gains, attens = [], []
    for s in seeds:
        _, clean, noisy = make_trial(s)
        out = np.asarray(fn(noisy.copy(), FS), dtype=float)
        if out.shape != noisy.shape or not np.all(np.isfinite(out)):
            return None  # hard fail: bad shape or NaN/Inf
        gains.append(band_snr_db(out, FS, F_SIGNAL) - band_snr_db(noisy, FS, F_SIGNAL))
        attens.append(attenuation_db(out, clean, FS, F_SIGNAL))
    gains, attens = np.array(gains), np.array(attens)
    distortion_pen = np.sum(np.maximum(0, -(attens + 3.0)))  # >3 dB signal loss penalized
    robust_gain = np.median(gains) - 0.5 * np.std(gains)     # reward consistency
    return float(robust_gain - distortion_pen)


# ---------- reference baselines ----------
def naive_moving_average(x, fs):
    return np.convolve(x, np.ones(25) / 25, mode="same")


def engineer_baseline(x, fs):
    """Competent human baseline: 4th-order Butterworth lowpass at 12 Hz,
    from an engineer who knows the 5 Hz target. Verified fitness ladder on
    TRAIN_SEEDS: LP45Hz 0.79 < naive MA 3.85 < THIS BASELINE 6.12
    < strong bandpass (2-8 Hz) 8.81. Beating it is meaningful."""
    b, a = signal.butter(4, 12.0, btype="lowpass", fs=fs)
    return signal.filtfilt(b, a, x)


def evaluate(program_path):
    """OpenEvolve entry point: higher combined_score = better."""
    try:
        fn = load_candidate(program_path)
        score = evaluate_with_seeds(fn, TRAIN_SEEDS)
        if score is None:
            return {"combined_score": -100.0, "error": "invalid output"}
        baseline = evaluate_with_seeds(engineer_baseline, TRAIN_SEEDS)
        return {
            "combined_score": float(score - baseline),  # >0 beats engineered baseline
            "raw_fitness_db": score,
            "baseline_fitness_db": baseline,
        }
    except Exception as e:
        return {"combined_score": -100.0, "error": str(e)[:200]}


def validate_heldout(program_path):
    """Run ONCE on a champion, with seeds evolution never saw."""
    fn = load_candidate(program_path)
    return evaluate_with_seeds(fn, HELDOUT_SEEDS)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        print("naive MA        :", round(evaluate_with_seeds(naive_moving_average, TRAIN_SEEDS), 3))
        print("engineer baseline:", round(evaluate_with_seeds(engineer_baseline, TRAIN_SEEDS), 3))
    elif len(sys.argv) > 1 and sys.argv[1] == "--heldout":
        print(validate_heldout(sys.argv[2]))
    else:
        print(evaluate(sys.argv[1]))
