"""Tests for the quantum-gravity grid evaluator (grid_evaluator.py).

Verifies that the reference toy model passes and scores positively, that a
separation-independent 'constants cheat' is hard-disqualified by the scaling
constraint, and that a legitimate band-edge strategy scores strictly higher.

Uses unittest to match the test style already in physics_verification/.
"""
import importlib.util
import os
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_GE_PATH = os.path.join(_HERE, "grid_evaluator.py")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ge = _load("grid_evaluator", _GE_PATH)


class GridLadderTests(unittest.TestCase):
    def test_selftest_passes(self):
        self.assertEqual(ge.selftest(), 0)

    def test_reference_scores_positive(self):
        res = ge._score(ge.reference_phase, ge.TRAIN_SEPARATIONS)
        self.assertTrue(res["ok"])
        self.assertGreater(res["score"], 0.0)
        self.assertAlmostEqual(res["qft_exponent"], -2.0, places=3)
        self.assertAlmostEqual(res["pn_exponent"], -3.0, places=3)

    def test_constants_cheat_hard_fails(self):
        with self.assertRaises(ge.Disqualified):
            ge._score(ge.constants_cheat_phase, ge.TRAIN_SEPARATIONS)

    def test_band_edge_beats_reference(self):
        ref = ge._score(ge.reference_phase, ge.TRAIN_SEPARATIONS)
        edge = ge._score(ge.band_edge_phase, ge.TRAIN_SEPARATIONS)
        self.assertGreater(edge["score"], ref["score"])

    def test_reference_generalises_to_heldout(self):
        res = ge._score(ge.reference_phase, ge.HELDOUT_SEPARATIONS)
        self.assertTrue(res["ok"])
        self.assertGreater(res["score"], 0.0)


class GridDisqualificationTests(unittest.TestCase):
    def test_nonzero_mass_zero_check(self):
        # A program that returns a nonzero constant fails the mass=0 check.
        def bad(mass, separation, time, method):
            return 1.0
        with self.assertRaises(ge.Disqualified):
            ge._score(bad, ge.TRAIN_SEPARATIONS)

    def test_non_finite_output_disqualified(self):
        def bad(mass, separation, time, method):
            if mass == 0:
                return 0.0
            return float("inf")
        with self.assertRaises(ge.Disqualified):
            ge._score(bad, ge.TRAIN_SEPARATIONS)

    def test_evaluate_reports_disqualification(self):
        prog = ("G=6.67430e-11\n"
                "def calculate_entanglement_phase(mass, separation, time, method):\n"
                "    return G*mass*time\n")  # no separation dependence
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cheat.py")
            with open(path, "w") as fh:
                fh.write(prog)
            result = ge.evaluate(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["score"], float("-inf"))
        self.assertIn("disqualified", result["error"])


if __name__ == "__main__":
    unittest.main()
