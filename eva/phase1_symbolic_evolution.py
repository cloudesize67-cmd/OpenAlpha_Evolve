#!/usr/bin/env python3
"""
Evolutionary Verifier Prototype
===============================

A minimal, runnable skeleton of an AlphaEvolve-style training loop for
verifiable domains:

    generate candidates -> deterministic verifier scores them ->
    select / mutate / crossover a population -> harvest verified winners

The loop is LLM-agnostic: `llm_propose()` is a stub where you plug in any
LLM (Kimi API, OpenAI-compatible endpoint, local model). Without an LLM it
falls back to AST-based mutation, so the file runs standalone as a demo.

Demo task: symbolic regression. The population evolves a Python expression
`f(x)` that must match a hidden ground-truth function. This is deliberately
simple so the *machinery* is visible:

  * VerifierHarness   - deterministic scoring + anti-gaming checks
                        (time budget, hardcode detection, complexity cap,
                        evaluator self-test / canary probe)
  * Calibration split - train / validation / held-out test sets, with a
                        DCPO-style penalty for overconfident-but-wrong
                        candidates (calibration degeneration guard)
  * EvolutionLoop     - tournament selection, elitism, novelty archive
                        (diversity preservation against mode collapse)

Usage:
    python3 evolutionary_verifier_prototype.py [--out DIR] [--gens N] [--pop N] [--seed N]
"""

import argparse
import ast
import copy
import hashlib
import json
import math
import os
import random
import time
from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------
# 0. Optional LLM hook (AlphaEvolve's "generator")
# --------------------------------------------------------------------------

def llm_propose(parent_code: str, task_description: str) -> str | None:
    """
    Plug in an LLM here to mutate/propose candidate programs.
    Return a Python expression string, or None to fall back to AST mutation.

    Example (OpenAI-compatible client, e.g. Kimi API):

        # from openai import OpenAI
        # client = OpenAI(api_key=os.environ["MOONSHOT_API_KEY"],
        #                 base_url="https://api.moonshot.ai/v1")
        # resp = client.chat.completions.create(
        #     model="kimi-k2-0905-preview",
        #     messages=[{"role": "user", "content":
        #         f"Task: {task_description}\\n"
        #         f"Improve this candidate, return ONLY a python expression in x:\\n"
        #         f"{parent_code}"}],
        #     temperature=1.0)
        # return resp.choices[0].message.content.strip()
    """
    return None


# --------------------------------------------------------------------------
# 1. Candidate representation + AST mutation engine (fallback generator)
# --------------------------------------------------------------------------

BIN_OPS = [ast.Add, ast.Sub, ast.Mult]
CONST_POOL = list(range(0, 10))


def random_expr(depth: int) -> ast.expr:
    """Generate a small random expression tree over {x, constants, +,-,*,**2, unary -}."""
    if depth == 0 or random.random() < 0.30:
        if random.random() < 0.60:
            return ast.Name(id="x", ctx=ast.Load())
        return ast.Constant(value=random.choice(CONST_POOL))
    r = random.random()
    if r < 0.75:
        return ast.BinOp(left=random_expr(depth - 1), op=random.choice(BIN_OPS)(),
                         right=random_expr(depth - 1))
    if r < 0.90:
        # square a sub-expression: e ** 2  (bounded exponent => no overflow blowups)
        return ast.BinOp(left=random_expr(depth - 1), op=ast.Pow(),
                         right=ast.Constant(value=2))
    return ast.UnaryOp(op=ast.USub(), operand=random_expr(depth - 1))


def expr_to_str(node: ast.expr) -> str:
    return ast.unparse(node)


def compile_expr(node: ast.expr):
    tree = ast.fix_missing_locations(ast.Expression(body=node))
    return compile(tree, "<candidate>", "eval")


def _expr_nodes(tree: ast.expr):
    return [n for n in ast.walk(tree) if isinstance(n, ast.expr)]


class _Replacer(ast.NodeTransformer):
    """Replace the node that *is* target (identity match) with new."""
    def __init__(self, target, new):
        self.target, self.new = target, new

    def visit(self, node):
        node = self.generic_visit(node)
        return self.new if node is self.target else node


def mutate(node: ast.expr) -> ast.expr:
    """One random structural mutation."""
    tree = copy.deepcopy(node)
    nodes = _expr_nodes(tree)
    target = random.choice(nodes)
    op = random.random()

    if op < 0.35:                                   # subtree replacement
        new = random_expr(depth=2)
    elif op < 0.60:                                 # constant perturbation
        consts = [n for n in nodes if isinstance(n, ast.Constant)]
        if not consts:
            new = random_expr(depth=1)
        else:
            c = random.choice(consts)
            new = ast.Constant(value=max(0, min(20, c.value + random.choice([-2, -1, 1, 2]))))
            target = c
    elif op < 0.80:                                 # operator swap
        binops = [n for n in nodes if isinstance(n, ast.BinOp) and not isinstance(n.op, ast.Pow)]
        if not binops:
            new = random_expr(depth=1)
        else:
            b = random.choice(binops)
            new = copy.deepcopy(b)
            new.op = random.choice(BIN_OPS)()
            target = b
    else:                                           # grow: wrap node in new op
        new = ast.BinOp(left=copy.deepcopy(target), op=random.choice(BIN_OPS)(),
                        right=random_expr(depth=1))

    tree = _Replacer(target, new).visit(tree)
    ast.fix_missing_locations(tree)
    return tree


def crossover(a: ast.expr, b: ast.expr) -> ast.expr:
    """Swap a random subtree of a with a random subtree of b."""
    child, donor = copy.deepcopy(a), copy.deepcopy(b)
    target = random.choice(_expr_nodes(child))
    new = random.choice(_expr_nodes(donor))
    child = _Replacer(target, copy.deepcopy(new)).visit(child)
    ast.fix_missing_locations(child)
    return child


def structure_hash(node: ast.expr) -> str:
    """Structural fingerprint with constants normalized -> diversity archive key."""
    def norm(n):
        if isinstance(n, ast.Constant):
            return "C"
        if isinstance(n, ast.Name):
            return "x"
        return type(n).__name__
    skeleton = ast.dump(node, annotate_fields=False)
    for tok in ("Constant", "Name"):
        pass  # skeleton normalization handled below via dump of mapped tree
    class Norm(ast.NodeTransformer):
        def visit_Constant(self, n): return ast.Constant(value=0)
    normed = Norm().visit(copy.deepcopy(node))
    return hashlib.md5(ast.dump(normed).encode()).hexdigest()[:12]


# --------------------------------------------------------------------------
# 2. The verifier harness — deterministic, tamper-aware scoring
# --------------------------------------------------------------------------

@dataclass
class EvalResult:
    code: str
    fitness: float                # primary score in [0, 1], higher is better
    confidence: float             # candidate's self-consistency on train split
    calibration_penalty: float    # DCPO-style penalty for overconfidence
    adjusted_fitness: float       # fitness - penalty (what selection uses)
    checks: dict = field(default_factory=dict)   # anti-gaming check outcomes
    error: str | None = None


class VerifierHarness:
    """
    Deterministic evaluator for the symbolic-regression demo.

    Mirrors a production verifier: unit tests (train split), a validation
    split the selection loop may *penalize* on but never *train* on, and a
    held-out split used only for final reporting — the classic defense
    against "hacking the visible tests".
    """

    def __init__(self, target_fn, xs_train, xs_val, xs_heldout,
                 tol=1.0, time_budget_s=0.05, lambda_calib=0.5):
        self.target_fn = target_fn
        self.splits = {
            "train":   [(x, target_fn(x)) for x in xs_train],
            "val":     [(x, target_fn(x)) for x in xs_val],
            "heldout": [(x, target_fn(x)) for x in xs_heldout],
        }
        self.tol = tol
        self.time_budget = time_budget_s
        self.lambda_calib = lambda_calib

    # -- canary / self-test: verify the *evaluator* itself is intact -------
    def self_test(self) -> bool:
        """A reference solution must score near-perfect. If it doesn't,
        the evaluator (not the candidate) is broken or has been tampered with."""
        ref = "x**2 + 3*x - 5"
        probe = self._run_code(ref, self.splits["train"])
        return probe is not None and all(
            abs(p - y) <= 1e-6 for p, (_, y) in zip(probe, self.splits["train"]))

    # -- safe execution ----------------------------------------------------
    @staticmethod
    def _run_code(code_str, cases):
        """Evaluate candidate expression on cases. Returns list of preds or None."""
        try:
            node = ast.parse(code_str, mode="eval").body
            # whitelist: no calls, no attributes, no names other than x
            for n in ast.walk(node):
                if isinstance(n, (ast.Call, ast.Attribute, ast.Subscript,
                                  ast.ListComp, ast.Lambda, ast.IfExp)):
                    return None
                if isinstance(n, ast.Name) and n.id != "x":
                    return None
                if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
                    if not (isinstance(n.right, ast.Constant) and n.right.value in (2, 3)):
                        return None
            fn = compile(ast.fix_missing_locations(ast.Expression(body=node)),
                         "<candidate>", "eval")
            preds = []
            for x, _ in cases:
                v = eval(fn, {"__builtins__": {}}, {"x": x})
                if not isinstance(v, (int, float)) or isinstance(v, bool) or math.isinf(v):
                    return None
                preds.append(v)
            return preds
        except Exception:
            return None

    @staticmethod
    def _accuracy(preds, cases, tol):
        hits = sum(1 for p, (_, y) in zip(preds, cases) if abs(p - y) <= tol)
        return hits / len(cases)

    @staticmethod
    def _rmse(preds, cases):
        return math.sqrt(sum((p - y) ** 2 for p, (_, y) in zip(preds, cases)) / len(cases))

    def evaluate(self, code_str: str) -> EvalResult:
        checks = {}

        # check 1: runs at all + sandbox whitelist
        t0 = time.perf_counter()
        preds_train = self._run_code(code_str, self.splits["train"])
        elapsed = time.perf_counter() - t0
        checks["runs_safely"] = preds_train is not None
        if preds_train is None:
            return EvalResult(code_str, 0.0, 0.0, 0.0, 0.0, checks, "exec_failed")

        # check 2: time budget (blocks trivial DoS / pathological code)
        checks["within_time_budget"] = elapsed <= self.time_budget

        # check 3: hardcode detection — large magic literals are how
        # candidates memorize targets instead of learning the function
        try:
            node = ast.parse(code_str, mode="eval").body
            lits = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant)]
        except Exception:
            lits = []
        checks["no_hardcoded_literals"] = all(abs(v) <= 20 for v in lits)
        n_nodes = len(list(ast.walk(node)))
        checks["complexity_ok"] = n_nodes <= 60

        # primary score on TRAIN split
        rmse = self._rmse(preds_train, self.splits["train"])
        fit = 1.0 / (1.0 + rmse)
        fit *= math.exp(-0.002 * max(0, n_nodes - 15))          # anti-bloat
        if not checks["no_hardcoded_literals"]:
            fit *= 0.5
        if not checks["within_time_budget"]:
            fit *= 0.5

        # calibration: confidence from train, *verified* on val split
        conf = self._accuracy(preds_train, self.splits["train"], self.tol)
        preds_val = self._run_code(code_str, self.splits["val"])
        acc_val = self._accuracy(preds_val, self.splits["val"], self.tol) if preds_val else 0.0
        calib_pen = self.lambda_calib * max(0.0, conf - acc_val)  # overconfidence tax
        checks["generalizes_to_val"] = acc_val >= conf - 0.01

        return EvalResult(code_str, round(fit, 6), round(conf, 4),
                          round(calib_pen, 6), round(fit - calib_pen, 6), checks)

    def heldout_report(self, code_str: str) -> dict:
        """Final, selection-invisible evaluation — the honesty check."""
        preds = self._run_code(code_str, self.splits["heldout"])
        if preds is None:
            return {"heldout_accuracy": 0.0, "heldout_rmse": None}
        return {"heldout_accuracy": round(self._accuracy(preds, self.splits["heldout"], self.tol), 4),
                "heldout_rmse": round(self._rmse(preds, self.splits["heldout"]), 6)}


# --------------------------------------------------------------------------
# 3. The evolutionary loop
# --------------------------------------------------------------------------

@dataclass
class Candidate:
    node: ast.expr
    code: str
    generation: int
    result: EvalResult | None = None


class EvolutionLoop:
    def __init__(self, harness: VerifierHarness, task_description: str,
                 pop_size=50, elite=4, tournament=3, novelty_bonus=0.02,
                 llm_fraction=0.0):
        self.h = harness
        self.task = task_description
        self.pop_size, self.elite = pop_size, elite
        self.tournament = tournament
        self.novelty_bonus = novelty_bonus
        self.llm_fraction = llm_fraction      # fraction of children proposed by LLM
        self.archive = set()                  # structure hashes seen (diversity)
        self.cache = {}                       # code -> EvalResult
        self.history = []

    def _eval(self, cand: Candidate) -> Candidate:
        if cand.code in self.cache:
            cand.result = self.cache[cand.code]
        else:
            cand.result = self.h.evaluate(cand.code)
            # novelty bonus keeps the population from collapsing onto one shape
            h = structure_hash(cand.node)
            if h not in self.archive:
                self.archive.add(h)
                cand.result.adjusted_fitness = round(
                    cand.result.adjusted_fitness + self.novelty_bonus, 6)
            self.cache[cand.code] = cand.result
        return cand

    def _make_child(self, pop, gen) -> Candidate:
        # --- parent selection: tournament on adjusted fitness ---
        def tourney():
            return max(random.sample(pop, min(self.tournament, len(pop))),
                       key=lambda c: c.result.adjusted_fitness)

        if random.random() < self.llm_fraction:
            parent = tourney()
            proposal = llm_propose(parent.code, self.task)
            if proposal:
                try:
                    node = ast.parse(proposal, mode="eval").body
                    return Candidate(node, expr_to_str(node), gen)
                except Exception:
                    pass  # fall through to AST operators

        if random.random() < 0.25:                       # crossover
            a, b = tourney(), tourney()
            node = crossover(a.node, b.node)
        else:                                            # mutation
            node = mutate(tourney().node)
        return Candidate(node, expr_to_str(node), gen)

    def run(self, generations: int):
        assert self.h.self_test(), "verifier self-test failed — do not trust this run"

        pop = [Candidate(random_expr(3), "", 0) for _ in range(self.pop_size)]
        for c in pop:
            c.code = expr_to_str(c.node)
            self._eval(c)

        for gen in range(1, generations + 1):
            pop.sort(key=lambda c: c.result.adjusted_fitness, reverse=True)
            best = pop[0]
            mean_fit = sum(c.result.adjusted_fitness for c in pop) / len(pop)
            self.history.append({
                "gen": gen, "best_code": best.code,
                "best_fitness": best.result.fitness,
                "best_adjusted": best.result.adjusted_fitness,
                "mean_adjusted": round(mean_fit, 4),
                "distinct_structures": len(self.archive),
            })
            if gen % 10 == 0 or gen == 1:
                print(f"gen {gen:>3} | best adj {best.result.adjusted_fitness:.4f} "
                      f"| mean {mean_fit:.4f} | structures {len(self.archive):>3} "
                      f"| {best.code[:60]}")

            # perfect + generalizing solution found -> stop
            if best.result.fitness >= 0.9999 and best.result.checks.get("generalizes_to_val"):
                print(f"converged at generation {gen}")
                break

            elites = [copy.deepcopy(c) for c in pop[:self.elite]]
            children = [self._eval(self._make_child(pop, gen))
                        for _ in range(self.pop_size - self.elite)]
            pop = elites + children

        pop.sort(key=lambda c: c.result.adjusted_fitness, reverse=True)
        return pop[0]


# --------------------------------------------------------------------------
# 4. Demo task + CLI
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./evolution_results")
    ap.add_argument("--gens", type=int, default=120)
    ap.add_argument("--pop", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--llm-fraction", type=float, default=0.0,
                    help="fraction of children proposed by the LLM hook (0 = pure AST demo)")
    args = ap.parse_args()

    random.seed(args.seed)

    # Hidden ground truth. Candidates must *discover* this, not memorize outputs.
    target = lambda x: x ** 2 + 3 * x - 5
    xs_train   = list(range(-5, 6))                      # visible to selection
    xs_val     = [x + 0.5 for x in range(-6, 7)]         # calibration check only
    xs_heldout = [-12, -9.25, 7.5, 11, 15]               # selection-invisible

    harness = VerifierHarness(target, xs_train, xs_val, xs_heldout)
    task = ("Find a python expression f(x) matching hidden test data. "
            "Operators allowed: + - * and **2, integer constants 0-9.")

    loop = EvolutionLoop(harness, task, pop_size=args.pop, llm_fraction=args.llm_fraction)
    best = loop.run(args.gens)

    report = {
        "seed": args.seed,
        "best_solution": best.code,
        "verifier": asdict(best.result),
        "held_out": harness.heldout_report(best.code),
        "history_tail": loop.history[-5:],
        "stats": {"generations_run": loop.history[-1]["gen"] if loop.history else 0,
                  "distinct_structures_explored": len(loop.archive),
                  "unique_candidates_evaluated": len(loop.cache)},
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "evolution_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(args.out, "best_solution.py"), "w") as f:
        f.write(f"# Evolved solution (generation {best.generation})\n")
        f.write(f"def f(x):\n    return {best.code}\n")
    with open(os.path.join(args.out, "evolution_history.json"), "w") as f:
        json.dump(loop.history, f, indent=2)

    print("\n=== RESULT ===")
    print(f"best expression     : {best.code}")
    print(f"train fitness       : {best.result.fitness}")
    print(f"calibration penalty : {best.result.calibration_penalty}")
    print(f"held-out accuracy   : {report['held_out']['heldout_accuracy']}")
    print(f"anti-gaming checks  : {best.result.checks}")
    print(f"report written to   : {args.out}/")


if __name__ == "__main__":
    main()
