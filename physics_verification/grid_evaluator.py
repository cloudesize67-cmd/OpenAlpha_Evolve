#!/usr/bin/env python3
"""Champion scorer for the quantum-gravity entanglement-phase scaling task.

The companion task (``examples/quantum_gravity_scaling_v2.yaml``) asks for a
``calculate_entanglement_phase(mass, separation, time, method)`` that models two
toy regimes -- ``classical_qft`` (falls off ~1/r^2) and ``post_newtonian``
(falls off ~1/r^3) -- and makes them **as numerically distinguishable as
possible** without breaking physical sanity.

A single function call, as the framework's fixed test suite sees it, cannot
score that objective: distinguishability is a property of how the outputs
*scale* across many inputs. This evaluator measures exactly that, on a grid:

  1. **Scaling exponents.** For each method it samples the phase across a
     geometric grid of separations and fits ``log|phase|`` vs ``log(r)`` by
     least squares. The slope is the scaling exponent; the fit R^2 rewards a
     clean power law.
  2. **Divergence objective.** The two regimes separate across the grid at a
     rate set by the *gap* between their exponents. The objective is that gap
     times the grid's dynamic range -- the number of e-folds by which the two
     methods pull apart. It is prefactor-independent, so it rewards genuine
     scaling structure, not a trivially huge constant offset.

Hard constraints (any failure disqualifies with score ``-inf``):

  * every output finite and real on valid inputs;
  * ``mass == 0`` gives ~0 phase for both methods;
  * ``classical_qft`` exponent near -2 and ``post_newtonian`` exponent near -3,
    with post_newtonian genuinely steeper. A constant (or separation-independent)
    program has exponent ~0 and hard-fails here -- it cannot be scored.

The **band-edge strategy** is a legitimate way to win: push the post_newtonian
falloff to the steep edge of the allowed exponent band to widen the divergence,
without leaving the band. ``--heldout`` re-scores on a disjoint separation
range; because the objective is scale-free a real power law generalises, while a
grid-memorising cheat does not.

Usage:
    python grid_evaluator.py --selftest              # reference >> cheats
    python grid_evaluator.py champion.py             # score on the training grid
    python grid_evaluator.py champion.py --heldout   # score on the held-out grid
    python grid_evaluator.py champion.py --json
"""
import argparse
import importlib.util
import sys

import numpy as np

G = 6.67430e-11
HBAR = 1.054571817e-34

# Grids. Training and held-out separation ranges are disjoint geometric spans.
TRAIN_SEPARATIONS = np.geomspace(1e-6, 1e-4, 24)
HELDOUT_SEPARATIONS = np.geomspace(1e-4, 1e-2, 24)
PROBE_MASS = 1.0e-12
PROBE_TIME = 1.0

# Allowed exponent bands (hard constraints).
QFT_EXP, PN_EXP = -2.0, -3.0
EXP_TOL = 0.35             # half-width of each allowed band
MIN_GAP = 0.5             # post_newtonian must be steeper than classical_qft by this

SCORE_SCALE = 8.60        # maps divergence e-folds -> reported score
ZERO_MASS_TOL = 1e-9


class Disqualified(Exception):
    """Raised when a program violates a hard constraint."""


def _phase(fn, mass, separation, time, method):
    val = fn(mass, separation, time, method)
    if isinstance(val, bool) or not isinstance(val, (int, float, np.floating)):
        raise Disqualified(f"non-real output {val!r} for method={method}")
    val = float(val)
    if not np.isfinite(val):
        raise Disqualified(f"non-finite output for method={method}")
    return val


def _check_zero_mass(fn):
    for method in ("classical_qft", "post_newtonian"):
        v = _phase(fn, 0.0, 1e-5, 1.0, method)
        if abs(v) > ZERO_MASS_TOL:
            raise Disqualified(f"mass=0 gave phase {v} for {method} (must be ~0)")


def _fit_exponent(fn, separations, method):
    """Least-squares slope and R^2 of log|phase| vs log(separation)."""
    xs = np.log(separations)
    ys = []
    for r in separations:
        v = _phase(fn, PROBE_MASS, r, PROBE_TIME, method)
        if v == 0.0:
            raise Disqualified(f"phase is identically 0 across the grid for {method}")
        ys.append(np.log(abs(v)))
    ys = np.array(ys)
    slope, intercept = np.polyfit(xs, ys, 1)
    resid = ys - (slope * xs + intercept)
    ss_res = np.sum(resid ** 2)
    ss_tot = np.sum((ys - ys.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float(slope), float(r2)


def _score(fn, separations):
    """Score a program on a separation grid. Returns a result dict.

    Raises Disqualified on any hard-constraint violation.
    """
    _check_zero_mass(fn)
    qft_slope, qft_r2 = _fit_exponent(fn, separations, "classical_qft")
    pn_slope, pn_r2 = _fit_exponent(fn, separations, "post_newtonian")

    if abs(qft_slope - QFT_EXP) > EXP_TOL:
        raise Disqualified(
            f"classical_qft exponent {qft_slope:.3f} outside [-2±{EXP_TOL}]")
    if abs(pn_slope - PN_EXP) > EXP_TOL:
        raise Disqualified(
            f"post_newtonian exponent {pn_slope:.3f} outside [-3±{EXP_TOL}]")
    gap = qft_slope - pn_slope   # positive when post_newtonian is steeper
    if gap < MIN_GAP:
        raise Disqualified(
            f"post_newtonian ({pn_slope:.3f}) not steeper than classical_qft "
            f"({qft_slope:.3f}) by >= {MIN_GAP}")

    dynamic_range = np.log(separations.max()) - np.log(separations.min())
    divergence = gap * dynamic_range       # e-folds the two methods pull apart
    mean_r2 = 0.5 * (qft_r2 + pn_r2)
    score = SCORE_SCALE * divergence * mean_r2
    return {
        "ok": True,
        "score": round(float(score), 3),
        "qft_exponent": round(qft_slope, 4),
        "pn_exponent": round(pn_slope, 4),
        "exponent_gap": round(float(gap), 4),
        "divergence_efolds": round(float(divergence), 4),
        "mean_r2": round(float(mean_r2), 5),
    }


# --- reference and probe implementations (for --selftest) -----------------
def reference_phase(mass, separation, time, method):
    """The task's reference toy model: qft ~ 1/r^2, post_newtonian ~ 1/r^3."""
    if method == "classical_qft":
        return (G ** 2 * mass ** 3 * time) / (HBAR * separation ** 2)
    if method == "post_newtonian":
        return (G * (mass * 1.0) * 0.5 * time) / (HBAR * separation ** 3)
    raise ValueError(f"unknown method: {method}")


def constants_cheat_phase(mass, separation, time, method):
    """A separation-independent 'cheat': returns 0 at mass=0 (passing that
    check) but ignores separation entirely, so its scaling exponent is ~0 and it
    hard-fails the exponent constraint."""
    return G * mass * time  # no dependence on separation -> slope 0


def band_edge_phase(mass, separation, time, method):
    """Legitimate improvement: keep classical_qft at 1/r^2 but push the
    post_newtonian falloff to the steep edge of the allowed band (~1/r^3.15),
    widening the divergence without leaving the exponent band."""
    if method == "classical_qft":
        return (G ** 2 * mass ** 3 * time) / (HBAR * separation ** 2)
    if method == "post_newtonian":
        return (G * (mass * 1.0) * 0.5 * time) / (HBAR * separation ** 3.15)
    raise ValueError(f"unknown method: {method}")


def load_program(path):
    spec = importlib.util.spec_from_file_location("champion", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "calculate_entanglement_phase"):
        raise AttributeError(
            f"{path} does not define calculate_entanglement_phase(...)")
    return module.calculate_entanglement_phase


def evaluate(program_path, heldout=False):
    seps = HELDOUT_SEPARATIONS if heldout else TRAIN_SEPARATIONS
    try:
        fn = load_program(program_path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"load failed: {exc}", "score": float("-inf")}
    try:
        result = _score(fn, seps)
    except Disqualified as exc:
        return {"ok": False, "error": f"disqualified: {exc}", "score": float("-inf")}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"error during scoring: {exc}",
                "score": float("-inf")}
    result["split"] = "heldout" if heldout else "train"
    return result


def _score_callable(fn, seps):
    try:
        return _score(fn, seps)
    except Disqualified as exc:
        return {"ok": False, "error": str(exc), "score": float("-inf")}


def selftest():
    """reference passes and scores > 0; constants-cheat hard-fails;
    the band-edge strategy scores strictly higher than the reference."""
    seps = TRAIN_SEPARATIONS
    ref = _score_callable(reference_phase, seps)
    cheat = _score_callable(constants_cheat_phase, seps)
    edge = _score_callable(band_edge_phase, seps)

    print("Reference ladder (training grid):")
    print(f"  reference        score={ref.get('score')}  "
          f"(gap {ref.get('exponent_gap')}, R2 {ref.get('mean_r2')})")
    print(f"  constants-cheat  {'HARD-FAIL' if not cheat['ok'] else cheat['score']}"
          f"  ({cheat.get('error', '')})")
    print(f"  band-edge        score={edge.get('score')}  "
          f"(gap {edge.get('exponent_gap')}, R2 {edge.get('mean_r2')})")

    checks = {
        "reference passes": ref["ok"],
        "reference score > 0": ref["ok"] and ref["score"] > 0,
        "constants-cheat hard-fails": not cheat["ok"],
        "band-edge beats reference": edge["ok"] and ref["ok"] and edge["score"] > ref["score"],
    }
    print()
    ok = True
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("  self-test passed." if ok else "  self-test FAILED.")
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("champion", nargs="?",
                        help="path to a program defining "
                             "calculate_entanglement_phase(mass, separation, time, method)")
    parser.add_argument("--selftest", action="store_true",
                        help="verify the reference/cheat ladder and exit")
    parser.add_argument("--heldout", action="store_true",
                        help="score on the held-out separation grid")
    parser.add_argument("--json", action="store_true",
                        help="print the result dict as JSON")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.champion:
        parser.error("a champion path is required unless --selftest is given")

    result = evaluate(args.champion, heldout=args.heldout)
    if args.json:
        import json
        print(json.dumps(result))
        return 0 if result.get("ok") else 1

    if not result.get("ok"):
        print(f"DISQUALIFIED: {result.get('error')}")
        return 1
    print(f"[{result['split']}] score {result['score']}  "
          f"(qft exp {result['qft_exponent']}, pn exp {result['pn_exponent']}, "
          f"gap {result['exponent_gap']}, {result['divergence_efolds']} e-folds, "
          f"R2 {result['mean_r2']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
