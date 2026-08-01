#!/usr/bin/env python3
"""Deterministic evaluator for the torsion-pendulum signal-recovery task.

The task: a weak periodic "torsion" signal (a few tones in a narrow science
band) is buried in a realistic mix of noise -- Brownian low-frequency drift,
broadband white noise, and out-of-band mains interference. An evolved program
implements ``filter_signal(x, fs)`` and must recover the clean signal.

Scoring (all in decibels):

  * The primary quality metric is the recovered SNR:
        snr_db = 10*log10( power(signal) / power(filtered - signal) )
    computed after trimming filter transients, and made robust by averaging
    across many random-noise seeds and subtracting a stability penalty for
    seed-to-seed variance.
  * A distortion penalty is subtracted: on a *noise-free* probe the filter must
    return the signal itself; any passband distortion (over-smoothing,
    band-edge attenuation) is charged against the score even if it happens to
    suppress noise well.
  * The reported fitness is **relative to a competent human baseline**
    (a hand-tuned FIR bandpass): ``score = snr_program - snr_baseline``, so a
    positive score means the evolved filter beats the engineer.

The scoring is fully deterministic (fixed seed sets, numpy only) so a given
program always earns the same score. ``--heldout`` scores on a disjoint seed
set to expose filters that overfit the training noise realisations.

Reference ladder (``--selftest``), absolute recovered SNR in dB:

    naive moving average  <  human baseline bandpass  <  strong bandpass

Usage:
    python evaluator.py --selftest              # sanity: baseline >> naive MA
    python evaluator.py program.py              # score on training seeds
    python evaluator.py --heldout program.py    # score on held-out seeds
    python evaluator.py program.py --json       # machine-readable result
"""
import argparse
import importlib.util
import sys

import numpy as np

# --- signal / acquisition model -------------------------------------------
FS = 256.0                 # sample rate (Hz)
N = 4096                   # samples (16 s record)
SCIENCE_TONES = (10.0, 12.5, 15.0)   # torsion oscillation lines (Hz)
MAINS = (50.0, 60.0)       # out-of-band interference lines (Hz)
TRIM = 300                 # samples dropped at each edge before scoring

SIGMA_WHITE = 2.10         # broadband noise std
DRIFT_SCALE = 0.012        # Brownian drift strength
MAINS_AMP = 4.0            # interference amplitude

TRAIN_SEEDS = tuple(range(12))
HELDOUT_SEEDS = tuple(range(1000, 1016))

STABILITY_K = 0.5          # penalty weight on seed-to-seed std (dB)
DISTORTION_K = 1.0         # penalty weight on passband distortion (dB)


def _make_signal(seed):
    """Return (clean, measured) for a given seed. Deterministic per seed."""
    rng = np.random.default_rng(seed)
    t = np.arange(N) / FS
    # The clean torsion signal: fixed tones, seed-varied phase and amplitude.
    clean = np.zeros(N)
    for f in SCIENCE_TONES:
        amp = 0.8 + 0.4 * rng.random()
        phase = 2 * np.pi * rng.random()
        clean += amp * np.sin(2 * np.pi * f * t + phase)

    # Brownian (1/f^2) low-frequency drift -- strong where an MA cannot reach.
    drift = np.cumsum(rng.standard_normal(N)) * DRIFT_SCALE
    drift -= drift.mean()
    # Broadband white noise.
    white = SIGMA_WHITE * rng.standard_normal(N)
    # Out-of-band mains interference with seed-varied phase.
    lines = np.zeros(N)
    for f in MAINS:
        lines += MAINS_AMP * np.sin(2 * np.pi * f * t + 2 * np.pi * rng.random())

    measured = clean + drift + white + lines
    return clean, measured


# --- FIR helpers (numpy only, no scipy) -----------------------------------
def _fir_bandpass(f_lo, f_hi, numtaps, window):
    """Windowed-sinc FIR bandpass, normalised to unit gain at band centre."""
    n = np.arange(numtaps) - (numtaps - 1) / 2.0
    fl = f_lo / (FS / 2.0)
    fh = f_hi / (FS / 2.0)
    h = fh * np.sinc(fh * n) - fl * np.sinc(fl * n)
    h *= window(numtaps)
    # Normalise so a tone at the band centre passes with unit gain.
    fc = (f_lo + f_hi) / 2.0
    k = np.arange(numtaps)
    resp = np.abs(np.sum(h * np.exp(-1j * 2 * np.pi * fc / FS * k)))
    if resp > 0:
        h = h / resp
    return h


def _apply_fir(x, h):
    return np.convolve(x, h, mode="same")


# --- reference filters (the fitness ladder) -------------------------------
def naive_moving_average(x, fs):
    """A boxcar smoother: leaves the drift untouched, so it scores poorly."""
    k = 7
    kernel = np.ones(k) / k
    return np.convolve(x, kernel, mode="same")


def baseline_bandpass(x, fs):
    """Competent hand-tuned FIR bandpass -- the human engineer's reference."""
    h = _fir_bandpass(6.5, 19.0, numtaps=129, window=np.hamming)
    return _apply_fir(x, h)


def strong_bandpass(x, fs):
    """A sharper, better-matched bandpass that beats the baseline.

    Its passband hugs the science tones (10-15 Hz) more tightly than the
    baseline, so it admits less broadband noise while a longer Blackman-windowed
    kernel keeps the stopband clean.
    """
    h = _fir_bandpass(9.2, 15.8, numtaps=255, window=np.blackman)
    return _apply_fir(x, h)


# --- scoring ---------------------------------------------------------------
def _snr_db(filtered, clean):
    """Recovered SNR after trimming filter transients."""
    sl = slice(TRIM, N - TRIM)
    resid = filtered[sl] - clean[sl]
    sig_p = np.sum(clean[sl] ** 2)
    err_p = np.sum(resid ** 2)
    if err_p <= 0:
        return 120.0
    return 10.0 * np.log10(sig_p / err_p)


def _distortion_db(filter_fn):
    """Penalty (dB) for distorting the signal on a noise-free probe.

    Uses a fixed, seedless probe of the science tones so the penalty depends
    only on the filter's passband shape, not on any noise realisation.
    """
    t = np.arange(N) / FS
    probe = np.zeros(N)
    for f in SCIENCE_TONES:
        probe += np.sin(2 * np.pi * f * t)
    out = np.asarray(filter_fn(probe, FS), dtype=float)
    sl = slice(TRIM, N - TRIM)
    err = np.sum((out[sl] - probe[sl]) ** 2)
    ref = np.sum(probe[sl] ** 2)
    frac = err / ref if ref > 0 else 1.0
    # Convert the residual energy fraction into a dB-scale penalty.
    return -10.0 * np.log10(max(1e-12, 1.0 - min(0.999999, frac)))


def _raw_snr(filter_fn, seeds):
    vals = []
    for s in seeds:
        clean, measured = _make_signal(s)
        out = np.asarray(filter_fn(measured, FS), dtype=float)
        if out.shape != clean.shape or not np.all(np.isfinite(out)):
            return None, None
        vals.append(_snr_db(out, clean))
    vals = np.array(vals)
    return float(vals.mean()), float(vals.std())


def _robust_snr(filter_fn, seeds):
    """Mean recovered SNR minus a stability penalty and a distortion penalty."""
    mean, std = _raw_snr(filter_fn, seeds)
    if mean is None:
        return None
    dist = _distortion_db(filter_fn)
    return mean - STABILITY_K * std - DISTORTION_K * dist


def load_program(path):
    """Load ``filter_signal`` from a program file."""
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "filter_signal"):
        raise AttributeError(f"{path} does not define filter_signal(x, fs)")
    return module.filter_signal


def evaluate(program_path, heldout=False):
    """Score a program file. Returns a result dict.

    ``score_db`` is the recovered SNR relative to the human baseline on the same
    seeds; positive means the program beats the engineer.
    """
    seeds = HELDOUT_SEEDS if heldout else TRAIN_SEEDS
    baseline = _robust_snr(baseline_bandpass, seeds)
    try:
        filter_fn = load_program(program_path)
    except Exception as exc:  # noqa: BLE001 - report load/exec failures as scores
        return {"ok": False, "error": f"load failed: {exc}",
                "score_db": float("-inf")}

    prog = _robust_snr(filter_fn, seeds)
    if prog is None:
        return {"ok": False, "error": "filter returned wrong shape or non-finite",
                "score_db": float("-inf")}

    return {
        "ok": True,
        "split": "heldout" if heldout else "train",
        "program_snr_db": round(float(prog), 3),
        "baseline_snr_db": round(float(baseline), 3),
        "score_db": round(float(prog - baseline), 3),
        "beats_baseline": bool(prog > baseline),
    }


def selftest():
    """Verify the reference ladder: naive MA < baseline < strong bandpass."""
    ladder = [
        ("naive moving average", naive_moving_average),
        ("human baseline bandpass", baseline_bandpass),
        ("strong bandpass", strong_bandpass),
    ]
    print("Reference ladder (absolute recovered SNR, dB, train seeds):")
    snrs = []
    for name, fn in ladder:
        mean, std = _raw_snr(fn, TRAIN_SEEDS)
        dist = _distortion_db(fn)
        snrs.append(mean)
        print(f"  {name:26s} {mean:6.2f} dB   (std {std:4.2f}, distortion {dist:4.2f} dB)")

    naive, baseline, strong = snrs
    ok = naive < baseline < strong
    margin = 0.5
    ok = ok and (baseline - naive) > margin and (strong - baseline) > margin
    print(f"\nOrdering naive < baseline < strong: {'PASS' if ok else 'FAIL'}")
    if not ok:
        print("  self-test FAILED: reference ladder is not correctly ordered")
        return 1
    print("  self-test passed.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("program", nargs="?",
                        help="path to a program defining filter_signal(x, fs)")
    parser.add_argument("--selftest", action="store_true",
                        help="verify the reference filter ladder and exit")
    parser.add_argument("--heldout", action="store_true",
                        help="score on the held-out seed set")
    parser.add_argument("--json", action="store_true",
                        help="print the result dict as JSON")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.program:
        parser.error("a program path is required unless --selftest is given")

    result = evaluate(args.program, heldout=args.heldout)
    if args.json:
        import json
        print(json.dumps(result))
        return 0 if result.get("ok") else 1

    if not result.get("ok"):
        print(f"INVALID: {result.get('error')}")
        return 1
    print(f"[{result['split']}] program {result['program_snr_db']} dB  "
          f"vs baseline {result['baseline_snr_db']} dB  ->  "
          f"score {result['score_db']:+} dB "
          f"({'beats' if result['beats_baseline'] else 'below'} baseline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
