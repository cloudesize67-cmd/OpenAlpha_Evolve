"""Tests for the torsion-filter evaluator (examples/torsion_filter/evaluator.py).

Verifies the reference fitness ladder is correctly ordered, that the seed
program scores below the human baseline while a well-designed bandpass beats it,
and that invalid programs are rejected rather than silently scored.

Uses unittest to match the test style already in this repo.
"""
import importlib.util
import os
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EVAL_PATH = os.path.join(_REPO_ROOT, "examples", "torsion_filter", "evaluator.py")
_SEED_PATH = os.path.join(_REPO_ROOT, "examples", "torsion_filter",
                          "initial_program.py")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = _load("torsion_evaluator", _EVAL_PATH)


class TorsionLadderTests(unittest.TestCase):
    def test_selftest_passes(self):
        self.assertEqual(ev.selftest(), 0)

    def test_reference_ladder_ordering(self):
        naive, _ = ev._raw_snr(ev.naive_moving_average, ev.TRAIN_SEEDS)
        base, _ = ev._raw_snr(ev.baseline_bandpass, ev.TRAIN_SEEDS)
        strong, _ = ev._raw_snr(ev.strong_bandpass, ev.TRAIN_SEEDS)
        # baseline >> naive MA, and strong beats baseline
        self.assertLess(naive, base)
        self.assertLess(base, strong)
        self.assertGreater(base - naive, 1.0)
        self.assertGreater(strong - base, 0.5)

    def test_signal_is_deterministic(self):
        a1, m1 = ev._make_signal(3)
        a2, m2 = ev._make_signal(3)
        self.assertTrue((a1 == a2).all() and (m1 == m2).all())
        # a different seed gives a different measurement
        _, m3 = ev._make_signal(4)
        self.assertFalse((m1 == m3).all())


class TorsionScoringTests(unittest.TestCase):
    def test_seed_scores_below_baseline(self):
        result = ev.evaluate(_SEED_PATH, heldout=False)
        self.assertTrue(result["ok"], result)
        self.assertLess(result["score_db"], 0.0)
        self.assertFalse(result["beats_baseline"])

    def test_seed_scores_below_baseline_on_heldout(self):
        result = ev.evaluate(_SEED_PATH, heldout=True)
        self.assertTrue(result["ok"], result)
        self.assertLess(result["score_db"], 0.0)

    def test_strong_bandpass_program_beats_baseline(self):
        prog = (
            "import numpy as np\n"
            "def filter_signal(x, fs):\n"
            "    x = np.asarray(x, float); numtaps = 255\n"
            "    n = np.arange(numtaps) - (numtaps - 1) / 2\n"
            "    fl, fh = 9.2 / (fs / 2), 15.8 / (fs / 2)\n"
            "    h = fh * np.sinc(fh * n) - fl * np.sinc(fl * n)\n"
            "    h *= np.blackman(numtaps)\n"
            "    k = np.arange(numtaps)\n"
            "    h /= np.abs(np.sum(h * np.exp(-1j * 2 * np.pi * 12.5 / fs * k)))\n"
            "    return np.convolve(x, h, mode='same')\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "champ.py")
            with open(path, "w") as fh:
                fh.write(prog)
            result = ev.evaluate(path, heldout=True)
        self.assertTrue(result["ok"], result)
        self.assertGreater(result["score_db"], 0.0)
        self.assertTrue(result["beats_baseline"])

    def test_wrong_length_output_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.py")
            with open(path, "w") as fh:
                fh.write("def filter_signal(x, fs):\n    return x[:10]\n")
            result = ev.evaluate(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["score_db"], float("-inf"))

    def test_missing_function_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "empty.py")
            with open(path, "w") as fh:
                fh.write("x = 1\n")
            result = ev.evaluate(path)
        self.assertFalse(result["ok"])
        self.assertIn("load failed", result["error"])


if __name__ == "__main__":
    unittest.main()
