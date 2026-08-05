"""
evaluator_termux.py -- pure-numpy twin of evaluator.py for Android/Termux.

Identical scoring logic and identical seeds to evaluator.py, but every
scipy dependency is reimplemented in numpy so nothing needs compilation:
  - scipy.signal.welch   -> manual segmented periodogram (Hann, 50% overlap)
  - scipy.signal.butter/filtfilt -> zero-phase windowed-sinc FIR (np.convolve)

Use this on Termux (pip install scipy fails there); use evaluator.py where
scipy exists. The fitness ladder must still hold: naive MA < baseline < good
bandpass, and --selftest must show baseline clearly above naive MA.

OpenEvolve entry point: evaluate(program_path) -> dict with combined_score.
"""
import importlib.util
import sys

import numpy as np

# ---------- configuration (identical to evaluator.py) ----------
FS = 1000.0
T_TRIAL = 20.0
F_SIGNAL = 5.0
TRAIN_SEEDS = [11, 23, 37, 53, 71]
HELDOUT_SEEDS = [101, 203, 307, 409, 503]
CANDIDATE_FN_NAMES = ["apply_filter", "evolve_filter", "filter_signal", "denoise"]


# ---------- synthetic data (identical to evaluator.py) ----------
def make_trial(seed, fs=FS, t=T_TRIAL, f_signal=F_SIGNAL):
    rng = np.random.default_rng(seed)
    n = int(fs * t)
    time = np.arange(n) / fs
    amp = rng.uniform(0.5, 2.0)
    clean = amp * np.sin(2 * np.pi * f_signal * time + rng.uniform(0, 2 * np.pi))
    white = rng.normal(0, 1.0, n)
    pink = np.convolve(rng.normal(0, 1, n), np.ones(8) / 8, mode="same")
    line = 0.5 * np.sin(2 * np.pi * 60.0 * time)
    drift = np.linspace(0, rng.uniform(-1, 1), n)
    noisy = clean + 0.8 * white + 1.5 * pink + line + drift
    return time, clean, noisy


# ---------- numpy-only DSP helpers ----------
def welch_psd(x, fs, nperseg):
    """Minimal Welch: Hann window, 50% overlap, averaged |FFT|^2."""
    nperseg = int(nperseg)
    step = nperseg // 2
    w = np.hanning(nperseg)
    w_power = np.sum(w ** 2)
    segs = [x[i:i + nperseg] for i in range(0, len(x) - nperseg + 1, step)]
    ps = np.zeros(nperseg // 2 + 1)
    for s in segs:
        X = np.fft.rfft(s * w)
        ps += (np.abs(X) ** 2) / (fs * w_power)
    ps /= len(segs)
    freqs = np.fft.rfftfreq(nperseg, 1 / fs)
    return freqs, ps


def fir_lowpass_kernel(fc, fs, numtaps=801):
    """Windowed-sinc lowpass kernel, unity gain at DC."""
    m = np.arange(numtaps) - (numtaps - 1) / 2.0
    h = np.sinc(2 * fc / fs * m) * np.hamming(numtaps)
    return h / h.sum()


def zero_phase_fir(x, kernel):
    """Forward + backward convolution => zero phase, squared magnitude response
    (numpy equivalent of filtfilt)."""
    y = np.convolve(x, kernel, mode="same")
    return np.convolve(y[::-1], kernel, mode="same")[::-1]


# ---------- metrics (same math as evaluator.py) ----------
def band_snr_db(x, fs, f_signal):
    f, P = welch_psd(x, fs, nperseg=int(fs * 4))
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
            return None
        gains.append(band_snr_db(out, FS, F_SIGNAL) - band_snr_db(noisy, FS, F_SIGNAL))
        attens.append(attenuation_db(out, clean, FS, F_SIGNAL))
    gains, attens = np.array(gains), np.array(attens)
    distortion_pen = np.sum(np.maximum(0, -(attens + 3.0)))
    robust_gain = np.median(gains) - 0.5 * np.std(gains)
    return float(robust_gain - distortion_pen)


# ---------- reference baselines (numpy-only) ----------
_LP12_KERNEL = fir_lowpass_kernel(12.0, FS)


def naive_moving_average(x, fs):
    return np.convolve(x, np.ones(25) / 25, mode="same")


def engineer_baseline(x, fs):
    """Competent human baseline (FIR lowpass @ 12 Hz, zero-phase)."""
    return zero_phase_fir(x, _LP12_KERNEL)


def evaluate(program_path):
    """OpenEvolve entry point: higher combined_score = better."""
    try:
        fn = load_candidate(program_path)
        score = evaluate_with_seeds(fn, TRAIN_SEEDS)
        if score is None:
            return {"combined_score": -100.0, "error": "invalid output"}
        baseline = evaluate_with_seeds(engineer_baseline, TRAIN_SEEDS)
        return {
            "combined_score": float(score - baseline),
            "raw_fitness_db": score,
            "baseline_fitness_db": baseline,
        }
    except Exception as e:
        return {"combined_score": -100.0, "error": str(e)[:200]}


def validate_heldout(program_path):
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
