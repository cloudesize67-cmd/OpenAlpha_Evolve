"""Tests for the torsion-filter evaluator (examples/torsion_filter/evaluator.py).

Verifies the engineered Butterworth baseline beats a naive moving average
("baseline >> naive MA"), that the seed program scores below the baseline while
a well-designed bandpass beats it (on both train and held-out seeds), and that
invalid candidates hard-fail with combined_score -100.

Uses unittest to match the test style already in this repo.
"""
import importlib.util
import os
import subprocess
import sys
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

# A numerically stable bandpass champion (sos form) that beats the baseline.
_CHAMP = (
    "from scipy import signal\n"
    "def filter_signal(x, fs):\n"
    "    sos = signal.butter(6, [4.0, 6.0], btype='bandpass', fs=fs, output='sos')\n"
    "    return signal.sosfiltfilt(sos, x)\n"
)


class BaselineLadderTests(unittest.TestCase):
    def test_baseline_beats_naive_moving_average(self):
        naive = ev.evaluate_with_seeds(ev.naive_moving_average, ev.TRAIN_SEEDS)
        baseline = ev.evaluate_with_seeds(ev.butter_notch, ev.TRAIN_SEEDS)
        self.assertGreater(baseline, naive)
        self.assertGreater(baseline - naive, 1.0)  # baseline >> naive MA

    def test_selftest_cli_passes(self):
        proc = subprocess.run([sys.executable, _EVAL_PATH, "--selftest"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PASS", proc.stdout)

    def test_make_trial_is_deterministic(self):
        _, c1, n1 = ev.make_trial(23)
        _, c2, n2 = ev.make_trial(23)
        self.assertTrue((c1 == c2).all() and (n1 == n2).all())
        _, _, n3 = ev.make_trial(24)
        self.assertFalse((n1 == n3).all())


class ScoringTests(unittest.TestCase):
    def test_seed_scores_below_baseline(self):
        result = ev.evaluate(_SEED_PATH)
        self.assertNotIn("error", result)
        self.assertLess(result["combined_score"], 0.0)

    def test_strong_bandpass_beats_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "champ.py")
            with open(path, "w") as fh:
                fh.write(_CHAMP)
            result = ev.evaluate(path)
            heldout = ev.validate_heldout(path)
        self.assertGreater(result["combined_score"], 0.0)
        self.assertIsNotNone(heldout)
        self.assertGreater(heldout, 0.0)  # generalises to held-out seeds

    def test_alternate_candidate_name_is_accepted(self):
        # The loader also accepts apply_filter / evolve_filter / denoise.
        prog = ("from scipy import signal\n"
                "def denoise(x, fs):\n"
                "    sos = signal.butter(6, [4.0, 6.0], btype='bandpass', fs=fs, output='sos')\n"
                "    return signal.sosfiltfilt(sos, x)\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "alt.py")
            with open(path, "w") as fh:
                fh.write(prog)
            result = ev.evaluate(path)
        self.assertGreater(result["combined_score"], 0.0)

    def test_wrong_length_output_hard_fails(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.py")
            with open(path, "w") as fh:
                fh.write("def filter_signal(x, fs):\n    return x[:10]\n")
            result = ev.evaluate(path)
        self.assertEqual(result["combined_score"], -100.0)
        self.assertEqual(result["error"], "invalid output")

    def test_missing_function_hard_fails(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "empty.py")
            with open(path, "w") as fh:
                fh.write("x = 1\n")
            result = ev.evaluate(path)
        self.assertEqual(result["combined_score"], -100.0)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
