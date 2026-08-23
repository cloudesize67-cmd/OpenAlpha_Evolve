"""
run_evolution.py -- Milestone B evolution loop for the NOESIS
coordination-detection task. Self-contained: needs ONLY numpy.
No openevolve install, no openai package.

Engine: the shared $0 fallback chain in examples/free_engine.py
(SPEC Module 1). Any subset of provider keys works; with zero keys the
chain is down and the loop waits/retries. FREE_ENGINE_MOCK=1 runs the
whole loop offline with real deterministic scoring.

THE LAW is enforced here:
  * evaluator.py (deterministic F1 + ARI judge) is the ONLY judge of fitness
  * seeds / evaluator code / generator code / reference detectors are NEVER
    sent to the LLM -- the prompt describes the general problem only
  * held-out scoring is NEVER run by this script -- you run it yourself at
    the end, and the held-out number is the only number you publish

Every (candidate, score) pair is logged to traces/ as JSONL (with the
provider that wrote each candidate). Those verifier-scored traces are the
future RLVR fine-tuning dataset -- do not delete them.

Setup (Termux):
    export GROQ_API_KEY="..."          # any one free key is enough
    cd ~/OpenAlpha_Evolve/examples/noesis_coordination
    python run_evolution.py --preflight-only     # gate first
    python run_evolution.py --iterations 60      # the real run
    FREE_ENGINE_MOCK=1 python run_evolution.py --iterations 6  # offline check
"""
import argparse
import ast
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # examples/ on path for the shared engine
from free_engine import complete, report, EngineDownError  # noqa: E402

EVALUATOR = HERE / "evaluator.py"
SEED_PROGRAM = HERE / "initial_program.py"
CHECKPOINTS = HERE / "checkpoints"
TRACES = HERE / "traces"

TEMPERATURE = 0.7
EVAL_TIMEOUT = 120     # seconds per candidate evaluation (pairwise signals O(n^2))
POP_CAP = 16

REQUIRED_FNS = ["detect_campaign", "detect", "flag_coordinated"]
# Extraction hygiene: candidates must be pure stdlib + numpy, sandbox-safe.
BANNED_SUBSTRINGS = [
    "open(", "import os", "import sys", "subprocess", "socket", "urllib",
    "__import__", "eval(", "exec(", "import importlib",
]

# Preflight ladder (sandbox-verified 2026-08-06), tolerance +/- 0.15,
# strict ordering naive < baseline < strong required.
LADDER = [("naive frequency", "naive_detector", -0.147),
          ("engineer baseline", "engineer_baseline", 0.668),
          ("strong fusion", "strong_detector", 1.489)]
LADDER_TOL = 0.15

# ----------------------------- prompt (no leaks) -----------------------------
# This text is the ONLY task knowledge the model gets. It never contains
# seed values, TRAIN/HELDOUT kwargs, generator code, evaluator code, or the
# reference detectors' thresholds/weights. General problem description only.
SYSTEM_MSG = (
    "You are improving a detector for coordinated inauthentic behavior in a "
    "stream of social-media posts. Define detect_campaign(posts) -> list of "
    "clusters, where each post is a dict "
    '{"account": int, "t": float, "tokens": tuple[int, ...], '
    '"tags": tuple[int, ...]} and each cluster is a list of account ids. '
    "Clusters of size >= 2 count as flagged accounts. Signals that may help: "
    "near-duplicate content across accounts, synchronized posting times, and "
    "shared hashtag signatures. Organic decoy communities exist (loud, "
    "hashtag-sharing, but not truly coordinated), so single-signal rules "
    "misfire; fusing weak evidence helps. Robustness across different worlds "
    "and difficulty levels matters more than any single score. Pure stdlib + "
    "numpy only -- no pandas, no networkx, no scipy. Any community detection "
    "must be deterministic (fixed thresholds, connected components). Do NOT "
    "try to read, import, or infer anything about the test harness; optimize "
    "the general problem, not the test. Reply with only the Python program "
    "in one code fence."
)

USER_TEMPLATE = """Task: detect clusters of coordinated inauthentic accounts in a post
stream. Posts arrive as dicts {"account": int, "t": float,
"tokens": tuple[int, ...], "tags": tuple[int, ...]}. Return clusters as
lists of account ids; clusters of size >= 2 are treated as flagged.

Current best candidate (score {score} vs a competent human-engineered
detector, higher is better, 0 means you merely tie it):

```python
{parent_code}
```

Write an improved `detect_campaign(posts)`. Pure stdlib + numpy only,
deterministic, robust across worlds of varying difficulty. Return ONLY the
complete program inside one ```python fence."""


# ----------------------------- pre-flight gate -------------------------------
def preflight():
    """Reproduce the sandbox-verified ladder (2026-08-06) in-process.
    Fail = stop, do not evolve. Held-out is never scored here."""
    sys.path.insert(0, str(HERE))
    import evaluator as ev

    values = []
    for label, fn_name, expected in LADDER:
        metric, _ = ev.evaluate_with(getattr(ev, fn_name),
                                     ev.TRAIN_SEEDS, ev.TRAIN_KW)
        values.append(metric)
        print(f"{label:18s}: {metric:+.3f}  (want {expected:+.3f} "
              f"+/- {LADDER_TOL})")
    naive, baseline, strong = values
    ok = (all(abs(m - e) <= LADDER_TOL
              for m, (_, _, e) in zip(values, LADDER))
          and naive < baseline < strong)
    # Known ladder fact, informational only -- held-out is NEVER scored here.
    print("held-out context : the content-only engineer baseline collapses "
          "to ~ 0.0 on held-out difficulty (known ladder fact, "
          "informational only)")
    print("PRE-FLIGHT:", "PASS" if ok else
          "FAIL -- fix evaluator before running")
    return ok


# ----------------------------- code handling ---------------------------------
def extract_block(response):
    """Pull the evolved program out of the model's reply. None if bad."""
    m = re.search(r"```python\s*(.*?)```", response, re.S)
    code = m.group(1).strip() if m else response.strip()
    if not any(f"def {name}" in code for name in REQUIRED_FNS):
        return None
    if any(bad in code for bad in BANNED_SUBSTRINGS):
        return None  # sandbox hygiene: no file/network/dynamic-import access
    try:
        ast.parse(code)
    except SyntaxError:
        return None
    return code


def build_program(code):
    """Candidates are complete self-contained programs; wrap into a file."""
    return code.rstrip() + "\n"


def score_candidate(program_text):
    """Deterministic evaluation in a subprocess (isolated + timed).
    Last stdout line of `python evaluator.py <candidate>` is a dict;
    combined_score (candidate metric minus engineer-baseline metric on
    train seeds) is the fitness."""
    tmp = CHECKPOINTS / "_candidate_tmp.py"
    tmp.write_text(program_text)
    try:
        out = subprocess.run(
            [sys.executable, str(EVALUATOR), str(tmp)],
            capture_output=True, text=True, timeout=EVAL_TIMEOUT,
        )
        line = [l for l in out.stdout.strip().splitlines() if l.strip()]
        result = ast.literal_eval(line[-1]) if line else {}
        if not isinstance(result, dict):
            result = {"combined_score": -100.0, "error": "bad evaluator output"}
    except (subprocess.TimeoutExpired, ValueError, SyntaxError, IndexError):
        result = {"combined_score": -100.0, "error": "timeout/parse"}
    return result


def save_best(best):
    (CHECKPOINTS / "best_program.py").write_text(build_program(best["code"]))


# ----------------------------- evolution loop --------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=60)
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--router-status", action="store_true",
                    help="print the $0 engine provider table and exit")
    args = ap.parse_args()

    if args.router_status:
        print(report())
        return

    CHECKPOINTS.mkdir(exist_ok=True)
    TRACES.mkdir(exist_ok=True)

    if not preflight():
        sys.exit(1)
    if args.preflight_only:
        return

    # Population: list of {"id", "code", "score"}; resume from checkpoint if any
    ckpt_file = CHECKPOINTS / "population.json"
    if ckpt_file.exists():
        state = json.loads(ckpt_file.read_text())
        pop, start_it, best = state["pop"], state["iteration"], state["best"]
        print(f"Resuming at iteration {start_it}; best so far "
              f"{best['score']:+.3f}")
        if not (CHECKPOINTS / "best_program.py").exists():
            save_best(best)
    else:
        seed_code = build_program(SEED_PROGRAM.read_text())
        seed_result = score_candidate(seed_code)
        pop = [{"id": 0, "code": seed_code,
                "score": seed_result.get("combined_score", -100.0)}]
        start_it, best = 0, pop[0]
        save_best(best)  # champion file always exists, even pre-improvement
        print(f"Seed score: {pop[0]['score']:+.3f} (combined vs engineer "
              f"baseline; 0 ties the human engineer, negative is below)")

    trace_path = TRACES / f"run_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    trace = trace_path.open("a")

    cand_id = max(p["id"] for p in pop) + 1
    for it in range(start_it, args.iterations):
        # Parent: 70% current best, 30% random from the better half
        ranked = sorted(pop, key=lambda p: p["score"], reverse=True)
        parent = ranked[0] if random.random() < 0.7 else random.choice(
            ranked[: max(1, len(ranked) // 2)])

        prompt = USER_TEMPLATE.replace("{score}", f"{parent['score']:+.3f}") \
                              .replace("{parent_code}", parent["code"])
        # Free tiers recover: on a dead chain, wait and retry the SAME
        # iteration -- never fake a result.
        while True:
            try:
                reply, provider = complete(prompt, system=SYSTEM_MSG,
                                           temperature=TEMPERATURE)
                break
            except EngineDownError:
                print(f"[{it}] engine chain down; sleeping 60s and retrying")
                time.sleep(60)

        code = extract_block(reply)
        if code is None:
            print(f"[{it}] unusable reply; skipping")
            trace.write(json.dumps({"iteration": it, "parent_id": parent["id"],
                                    "provider": provider,
                                    "rejected": True}) + "\n")
            trace.flush()
            continue

        result = score_candidate(build_program(code))
        score = result.get("combined_score", -100.0)
        cand = {"id": cand_id, "code": code, "score": score}
        cand_id += 1
        pop.append(cand)
        pop = sorted(pop, key=lambda p: p["score"], reverse=True)[:POP_CAP]

        if score > best["score"]:
            best = cand
            save_best(best)
            print(f"[{it}] NEW BEST: {score:+.3f} (id {cand['id']}, "
                  f"provider {provider})")
        else:
            print(f"[{it}] {score:+.3f} (best {best['score']:+.3f}, "
                  f"provider {provider})")

        trace.write(json.dumps({
            "iteration": it, "id": cand["id"], "parent_id": parent["id"],
            "provider": provider, "code": code, "combined_score": score,
            "raw_metric": result.get("raw_metric"),
            "error": result.get("error"),
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
    print(f"Best TRAIN combined_score: {best['score']:+.3f} "
          f"(>0 beats the competent engineer)")
    print(f"Champion saved: {CHECKPOINTS / 'best_program.py'}")
    print(f"Traces (RLVR dataset): {trace_path}")
    print("\nThe ONLY number you may publish is the held-out one. "
          "Run it yourself:")
    print("  python evaluator.py --heldout checkpoints/best_program.py")


if __name__ == "__main__":
    main()
