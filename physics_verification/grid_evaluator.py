"""
grid_evaluator.py -- champion evaluator for the quantum_gravity_entanglement_phase_scaling task.

Why this exists
---------------
The OpenAlpha_Evolve validation_func only ever sees ONE function call's output
(see evaluator_agent/agent.py). The task's real objective -- "maximize the
measurable divergence between the two toy regimes" -- is a property of MANY
calls across an input grid. So it was never actually scored; evolution was
rewarded for approximately copying the reference formula that was included in
expert_knowledge. This module fixes that: it loads a champion program, calls
it across swept input grids, and computes the objective directly.

What it scores (all deterministic, no LLM):
  1. HARD FAIL: NaN/Inf/complex anywhere, or mass=0 not yielding ~0.
  2. Scaling exponents via log-log regression on swept grids
     (classical_qft: mass^+3, time^+1, sep^-2; post_newtonian: mass^+1,
     time^+1, sep^-3) -- penalizes deviation.
  3. Anchor penalty: at held-out anchor points, output must stay within 3
     orders of magnitude of the public reference scale (same rule as v1,
     now enforced on ranges evolution never saw).
  4. DIVERGENCE SCORE: median |log10(phi_classical / phi_pn)| across a
     shared (mass, sep, time) grid -- the task's actual objective.

Final score = divergence_db - 3.0 * exponent_error - anchor_penalty
Higher is better. No saturation. Held-out ranges differ from prompt-visible
ranges; champions must be claimed with --heldout.

Usage:
  python grid_evaluator.py champion.py            # train ranges
  python grid_evaluator.py champion.py --heldout  # held-out ranges (publish this)
  python grid_evaluator.py --selftest             # sanity: reference >> cheats
"""
import importlib.util
import sys

import numpy as np

G = 6.67430e-11
HBAR = 1.054571817e-34

# input ranges: what the prompt-visible tests used vs. what we hold out
RANGES = {
    "train": {
        "mass": np.geomspace(5e-13, 5e-12, 6),
        "sep": np.geomspace(8e-7, 2.5e-6, 8),
        "time": np.geomspace(0.8, 2.5, 6),
    },
    "heldout": {
        "mass": np.geomspace(2e-13, 1e-11, 6),
        "sep": np.geomspace(5e-7, 5e-6, 8),
        "time": np.geomspace(0.4, 6.0, 6),
    },
}

# target scaling exponents: d(log phase) / d(log param)
TARGETS = {
    "classical_qft": {"mass": 3.0, "time": 1.0, "sep": -2.0},
    "post_newtonian": {"mass": 1.0, "time": 1.0, "sep": -3.0},
}


def reference_phase(mass, sep, time, method):
    if method == "classical_qft":
        return (G ** 2 * mass ** 3 * time) / (HBAR * sep ** 2)
    return (G * (mass * 1.0) * 0.5 * time) / (HBAR * sep ** 3)


def load_fn(path):
    spec = importlib.util.spec_from_file_location("champion", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "calculate_entanglement_phase"):
        raise AttributeError("champion must define calculate_entanglement_phase")
    return mod.calculate_entanglement_phase


def _call(fn, m, r, t, method):
    out = fn(float(m), float(r), float(t), method)
    if isinstance(out, complex) or not np.isscalar(out):
        return None
    out = float(out)
    return out if np.isfinite(out) else None


def _sweep_exponent(fn, method, param, values, fixed):
    xs, ys = [], []
    for v in values:
        args = dict(fixed)
        args[param] = v
        out = _call(fn, args["mass"], args["sep"], args["time"], method)
        if out is None or out == 0:
            return None
        xs.append(np.log10(v))
        ys.append(np.log10(abs(out)))
    slope, _ = np.polyfit(xs, ys, 1)
    return float(slope)


def score_function(fn, ranges):
    R = RANGES[ranges]
    base = {"mass": 1e-12, "sep": 1e-6, "time": 1.0}

    # 1. hard fails
    for method in ("classical_qft", "post_newtonian"):
        if (_call(fn, 0.0, 1e-6, 1.0, method) or 0.0) != 0.0:
            z = _call(fn, 0.0, 1e-6, 1.0, method)
            if z is None or abs(z) > 1e-9:
                return {"score": -1000.0, "fail": f"zero-mass violated ({method}: {z})"}
        for m in R["mass"][:3]:
            for r in R["sep"][:3]:
                if _call(fn, m, r, base["time"], method) is None:
                    return {"score": -1000.0, "fail": f"non-finite output ({method})"}

    # 2. exponent error
    exp_err, measured = 0.0, {}
    for method, targets in TARGETS.items():
        for param, target in targets.items():
            slope = _sweep_exponent(fn, method, param, R[param], base)
            if slope is None:
                return {"score": -1000.0, "fail": f"sweep failed: {method}/{param}"}
            measured[f"{method}/{param}"] = round(slope, 3)
            exp_err += abs(slope - target)

    # 3. anchor penalty (within 3 orders of reference scale)
    anchor_pen = 0.0
    for method in TARGETS:
        for m, r, t in [(R["mass"][0], R["sep"][0], base["time"]),
                        (R["mass"][-1], R["sep"][-1], R["time"][-1]),
                        (R["mass"][2], R["sep"][3], R["time"][2])]:
            out = _call(fn, m, r, t, method)
            ref = reference_phase(m, r, t, method)
            log_ratio = abs(np.log10(max(abs(out), 1e-300) / ref))
            anchor_pen += max(0.0, log_ratio - 3.0)

    # 4. divergence score on shared grid
    divs = []
    for m in R["mass"][1:4]:
        for r in R["sep"][1:5]:
            for t in R["time"][1:4]:
                c = _call(fn, m, r, t, "classical_qft")
                p = _call(fn, m, r, t, "post_newtonian")
                if c and p:
                    divs.append(abs(np.log10(max(abs(p), 1e-300) / max(abs(c), 1e-300))))
    divergence_db = float(np.median(divs)) if divs else 0.0

    score = divergence_db - 3.0 * exp_err - anchor_pen
    return {
        "score": round(score, 3),
        "divergence_db": round(divergence_db, 3),
        "exponent_error": round(exp_err, 3),
        "anchor_penalty": round(anchor_pen, 3),
        "measured_exponents": measured,
        "ranges": ranges,
    }


def _selftest():
    def reference(mass, separation, time, method):
        return reference_phase(mass, separation, time, method)

    def cheat_constant(mass, separation, time, method):
        # gaming attempt: huge constant divergence, ignores physics
        return 1e-11 if method == "classical_qft" else 1e29

    def cheat_extreme(mass, separation, time, method):
        # pushes both to the edge of the allowed anchor band
        ref = reference_phase(mass, separation, time, method)
        return ref / 1e3 if method == "classical_qft" else ref * 1e3

    for name, fn in [("reference", reference),
                     ("cheat_constant", cheat_constant),
                     ("edge_pusher", cheat_extreme)]:
        print(f"{name:16s}", score_function(fn, "train"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        _selftest()
    else:
        path = sys.argv[1]
        rng = "heldout" if "--heldout" in sys.argv[2:] else "train"
        print(score_function(load_fn(path), rng))
