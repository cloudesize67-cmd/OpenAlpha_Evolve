"""
run_evolution.py -- Milestone A evolution loop for the torsion-filter task.
Self-contained: needs ONLY numpy. No openevolve install, no openai package.
Engine: Gemini FREE tier via its OpenAI-compatible endpoint (plain HTTPS).

THE LAW is enforced here:
  * evaluator_termux.py (deterministic) is the ONLY judge of fitness
  * seeds / evaluator code / reference implementations are NEVER sent to the LLM
  * held-out scoring is NEVER run by this script -- you run it yourself at
    the end, and the held-out number is the only number you publish

Every (candidate, score) pair is logged to traces/ as JSONL. Those
verifier-scored traces are the future RLVR fine-tuning dataset -- do not
delete them.

Setup (Termux):
    export GEMINI_API_KEY="your-free-tier-key-from-aistudio.google.com/apikey"
    cd ~/OpenAlpha_Evolve/examples/torsion_filter
    python run_evolution.py --preflight-only     # gate first
    python run_evolution.py --iterations 60      # the real run
"""
import argparse
import ast
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALUATOR = HERE / "evaluator_termux.py"
SEED_PROGRAM = HERE / "initial_program.py"
CHECKPOINTS = HERE / "checkpoints"
TRACES = HERE / "traces"

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_MODEL = "gemini-3.5-flash-lite"   # free-tier breadth model (config.yaml)
TEMPERATURE = 0.7
EVAL_TIMEOUT = 60                          # seconds per candidate evaluation

BLOCK_START = "# EVOLVE-BLOCK-START"
BLOCK_END = "# EVOLVE-BLOCK-END"
REQUIRED_FNS = ["apply_filter", "evolve_filter", "filter_signal", "denoise"]

# ----------------------------- prompt (no leaks) -----------------------------
# This text is the ONLY task knowledge the model gets. It never contains
# seeds, evaluator code, baseline code, or reference implementations.
SYSTEM_MSG = (
    "You are improving a digital filter for a torsion-balance readout. "
    "Rewrite ONLY the function you are shown. Keep the signature "
    "apply_filter(noisy, fs) -> np.ndarray, returning an array of the same "
    "length. numpy only -- scipy is NOT available. Goal: maximize SNR at a "
    "known 5 Hz sinusoidal target while preserving its amplitude (<=3 dB "
    "attenuation) and staying robust across different noise realizations. "
    "The noise is a mix of white, pink (1/f-like), a 60 Hz mains line, and "
    "slow drift. Sample rate fs=1000 Hz. Do NOT try to read, import, or "
    "infer anything about the test harness; optimize the general problem, "
    "not the test. Reply with only the Python function in a code fence."
)

USER_TEMPLATE = """Task: denoise a torsion-balance readout. Signal: 5 Hz sine of unknown
amplitude/phase. Noise: white + pink + 60 Hz line + linear drift.
fs = 1000 Hz, trial length 20 s.

Current best candidate (score {score:.2f} dB vs a competent human baseline,
higher is better):

```python
{parent_code}
```

Write an improved `apply_filter(noisy, fs)`. numpy only. Return ONLY the
function inside one ```python fence."""


# ----------------------------- pre-flight gate -------------------------------
def preflight():
    """Sandbox-verified 2026-08-06 gates. Fail = stop, do not evolve."""
    sys.path.insert(0, str(HERE))
    import evaluator_termux as ev

    naive = ev.evaluate_with_seeds(ev.naive_moving_average, ev.TRAIN_SEEDS)
    base = ev.evaluate_with_seeds(ev.engineer_baseline, ev.TRAIN_SEEDS)
    print(f"naive MA        : {naive:.3f}  (want 3.847)")
    print(f"engineer baseline: {base:.3f}  (want 5.956)")
    ok = abs(naive - 3.847) < 0.3 and abs(base - 5.956) < 0.3 and base > naive
    print("PRE-FLIGHT:", "PASS" if ok else "FAIL -- fix evaluator before running")
    return ok


# ----------------------------- LLM driver ------------------------------------
def call_gemini(prompt, model, key):
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": prompt},
        ],
        "temperature": TEMPERATURE,
    }).encode()
    req = urllib.request.Request(
        GEMINI_URL, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    delay = 5
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 5:
                print(f"  [rate limit {e.code}] retry in {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
        except urllib.error.URLError:
            if attempt < 5:
                time.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise
    raise RuntimeError("unreachable")


# ----------------------------- code handling ---------------------------------
def extract_block(response):
    """Pull the evolved function out of the model's reply. Returns None if bad."""
    m = re.search(r"```python\s*(.*?)```", response, re.S)
    code = m.group(1) if m else response
    # If the model returned a full program with markers, keep only the block
    if BLOCK_START in code and BLOCK_END in code:
        code = code.split(BLOCK_START, 1)[1].split(BLOCK_END, 1)[0].strip()
    if not any(f"def {name}" in code for name in REQUIRED_FNS):
        return None
    if "scipy" in code or "import os" in code or "open(" in code:
        return None  # sandbox hygiene: no scipy, no file access
    return code


def build_program(block):
    return (f"import numpy as np\n\n\n{BLOCK_START}\n{block}\n{BLOCK_END}\n")


def score_candidate(program_text):
    """Deterministic evaluation in a subprocess (isolated + timed)."""
    tmp = CHECKPOINTS / "_candidate_tmp.py"
    tmp.write_text(program_text)
    try:
        out = subprocess.run(
            [sys.executable, str(EVALUATOR), str(tmp)],
            capture_output=True, text=True, timeout=EVAL_TIMEOUT,
        )
        line = [l for l in out.stdout.strip().splitlines() if l.strip()]
        result = ast.literal_eval(line[-1]) if line else {}
    except (subprocess.TimeoutExpired, ValueError, SyntaxError, IndexError):
        result = {"combined_score": -100.0, "error": "timeout/parse"}
    return result


# ----------------------------- evolution loop --------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=60)
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--model", default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL))
    args = ap.parse_args()

    CHECKPOINTS.mkdir(exist_ok=True)
    TRACES.mkdir(exist_ok=True)

    if not preflight():
        sys.exit(1)
    if args.preflight_only:
        return

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit('Set your free key first: export GEMINI_API_KEY="..."')

    seed_block = SEED_PROGRAM.read_text().split(BLOCK_START)[1].split(BLOCK_END)[0].strip()

    # Population: list of {"id", "code", "score"}; resume from checkpoint if any
    ckpt_file = CHECKPOINTS / "population.json"
    if ckpt_file.exists():
        state = json.loads(ckpt_file.read_text())
        pop, start_it, best = state["pop"], state["iteration"], state["best"]
        print(f"Resuming at iteration {start_it}; best so far {best['score']:.2f}")
    else:
        seed_score = score_candidate(build_program(seed_block))
        pop = [{"id": 0, "code": seed_block,
                "score": seed_score.get("combined_score", -100.0)}]
        start_it, best = 0, pop[0]
        print(f"Seed score: {pop[0]['score']:.2f} (expect about -2.1)")

    trace_path = TRACES / f"run_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    trace = trace_path.open("a")

    cand_id = max(p["id"] for p in pop) + 1
    for it in range(start_it, args.iterations):
        # Parent: 70% current best, 30% random from the better half
        ranked = sorted(pop, key=lambda p: p["score"], reverse=True)
        parent = ranked[0] if random.random() < 0.7 else random.choice(
            ranked[: max(1, len(ranked) // 2)])

        try:
            reply = call_gemini(
                USER_TEMPLATE.format(score=parent["score"],
                                     parent_code=parent["code"]),
                args.model, key)
        except Exception as e:
            print(f"[{it}] LLM error: {e}; skipping")
            time.sleep(10)
            continue

        block = extract_block(reply)
        if block is None:
            print(f"[{it}] unusable reply; skipping")
            trace.write(json.dumps({"iteration": it, "parent_id": parent["id"],
                                    "rejected": True}) + "\n")
            continue

        result = score_candidate(build_program(block))
        score = result.get("combined_score", -100.0)
        cand = {"id": cand_id, "code": block, "score": score}
        cand_id += 1
        pop.append(cand)
        pop = sorted(pop, key=lambda p: p["score"], reverse=True)[:16]

        if score > best["score"]:
            best = cand
            (CHECKPOINTS / "best_program.py").write_text(build_program(block))
            print(f"[{it}] NEW BEST: {score:+.2f} dB (id {cand['id']})")
        else:
            print(f"[{it}] {score:+.2f} dB (best {best['score']:+.2f})")

        trace.write(json.dumps({
            "iteration": it, "id": cand["id"], "parent_id": parent["id"],
            "model": args.model, "code": block, "combined_score": score,
            "raw_fitness_db": result.get("raw_fitness_db"),
            "ts": time.time(),
        }) + "\n")
        trace.flush()

        if (it + 1) % 10 == 0:
            ckpt_file.write_text(json.dumps(
                {"pop": pop, "iteration": it + 1, "best": best}))
            print(f"  checkpoint saved ({it + 1}/{args.iterations})")

        time.sleep(2)  # be gentle with free-tier rate limits

    ckpt_file.write_text(json.dumps(
        {"pop": pop, "iteration": args.iterations, "best": best}))
    trace.close()

    print("\n=== RUN COMPLETE ===")
    print(f"Best TRAIN combined_score: {best['score']:+.2f} dB "
          f"(>0 beats the competent engineer)")
    print(f"Champion saved: {CHECKPOINTS / 'best_program.py'}")
    print(f"Traces (RLVR dataset): {trace_path}")
    print("\nThe ONLY number you may publish is the held-out one. Run it yourself:")
    print("  python evaluator_termux.py --heldout checkpoints/best_program.py")


if __name__ == "__main__":
    main()
