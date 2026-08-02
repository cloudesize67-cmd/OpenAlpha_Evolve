#!/usr/bin/env python3
"""
Phase 2 — Code-Task Evolution Harness
=====================================

Upgrades the Phase 1 prototype from symbolic regression to a real
code-generation benchmark:

  * TaskBank      — programming tasks, each with a docstring spec, a reference
                    solution (canary), and THREE unit-test splits:
                    visible (train) / validation (calibration) / held-out
  * Verifier      — executes candidate functions against the unit tests in a
                    whitelisted sandbox, with anti-gaming checks:
                    - constant-output / hardcode detection
                    - banned construct rejection (imports, I/O, attribute access)
                    - complexity cap, time budget
                    - canary self-test of the evaluator itself before every run
  * LLM hook      — `llm_propose()` calls any OpenAI-compatible endpoint
                    (e.g. Kimi: MOONSHOT_API_KEY + base_url https://api.moonshot.ai/v1)
                    to mutate candidate code. Falls back to AST operators,
                    so the file runs standalone with no API key.
  * Calibration   — DCPO-style overconfidence tax: a candidate whose visible
                    pass rate exceeds its validation pass rate is penalized.

Usage:
    python3 phase2_code_evolution.py                          # all tasks, AST-only demo
    python3 phase2_code_evolution.py --task collatz_step --gens 200
    MOONSHOT_API_KEY=sk-... python3 phase2_code_evolution.py --llm-fraction 0.5
"""

import argparse
import ast
import copy
import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------
# 1. Task bank — spec, reference canary, and 3 unit-test splits
# --------------------------------------------------------------------------

def _range(a, b, step=1):
    return list(range(a, b, step))

TASKS = {
    "double_plus_one": {
        "spec": "solve(n) returns 2*n + 1 for integer n.",
        "reference": "2 * n + 1",
        "train": _range(0, 14), "val": _range(14, 22),
        "heldout": [100, 500, -37, 999],
    },
    "sum_to_n": {
        "spec": "solve(n) returns the sum 0+1+...+n (closed form, integer n >= 0).",
        "reference": "n * (n + 1) // 2",
        "train": _range(0, 12), "val": _range(12, 20),
        "heldout": [50, 100, 1000, 2500],
    },
    "is_even": {
        "spec": "solve(n) returns True if integer n is even, else False.",
        "reference": "n % 2 == 0",
        "train": _range(0, 14), "val": _range(14, 24),
        "heldout": [100, 333, 1000000, -42],
    },
    "collatz_step": {
        "spec": ("solve(n) returns one Collatz step: n//2 if n is even, "
                 "3*n+1 if n is odd (integer n >= 1)."),
        "reference": "n // 2 if n % 2 == 0 else 3 * n + 1",
        "train": _range(1, 18), "val": _range(18, 30),
        "heldout": [97, 64, 1000, 871],
    },
    "clamp_0_100": {
        "spec": "solve(n) clamps integer n into [0, 100].",
        "reference": "min(max(n, 0), 100)",
        "train": _range(-20, 140, 8), "val": _range(-15, 145, 11),
        "heldout": [-500, 1000, 250, 7],
    },
}

# --------------------------------------------------------------------------
# 2. LLM hook (AlphaEvolve's generator) — plug in any OpenAI-compatible API
# --------------------------------------------------------------------------

_CLIENT = None

def llm_propose(parent_code: str, task_spec: str) -> str | None:
    """Ask an LLM to mutate a candidate. Returns an expression string or None.

    Set MOONSHOT_API_KEY (Kimi) — or adapt base_url/model for any
    OpenAI-compatible provider. Any failure returns None so the loop
    degrades gracefully to AST mutation.
    """
    global _CLIENT
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        return None
    try:
        if _CLIENT is None:
            from openai import OpenAI
            _CLIENT = OpenAI(api_key=api_key, base_url="https://api.moonshot.ai/v1")
        resp = _CLIENT.chat.completions.create(
            model="kimi-k2-0905-preview",
            temperature=1.0,
            messages=[{"role": "user", "content": (
                f"Task: {task_spec}\n\n"
                f"Here is a candidate solution (a python expression over variable n):\n"
                f"    {parent_code}\n\n"
                "Propose ONE improved or meaningfully different candidate. "
                "Rules: pure expression, only variable n, integer constants, "
                "operators + - * // % **, comparisons, if/else expressions, "
                "and calls to min/max/abs. Reply with ONLY the expression.")}],
        )
        text = resp.choices[0].message.content.strip()
        text = text.strip("`").removeprefix("python").strip()
        for line in text.splitlines():          # take first parseable line
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                ast.parse(line, mode="eval")
                return line
            except SyntaxError:
                continue
    except Exception:
        pass
    return None

# --------------------------------------------------------------------------
# 3. Grammar + AST mutation engine (fallback generator)
# --------------------------------------------------------------------------

ARITH_OPS = [ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod]
CMP_OPS = [ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE]
CONST_POOL = list(range(0, 10)) + [10, 100]
FUNC_CALLS = {"min": 2, "max": 2, "abs": 1}


def random_expr(depth: int, top: bool = False) -> ast.expr:
    if depth == 0 or random.random() < 0.28:
        if random.random() < 0.55:
            return ast.Name(id="n", ctx=ast.Load())
        return ast.Constant(value=random.choice(CONST_POOL))
    r = random.random()
    if top and r < 0.12:                       # bare comparison (bool tasks)
        return ast.Compare(left=random_expr(depth - 1), ops=[random.choice(CMP_OPS)()],
                           comparators=[random_expr(depth - 1)])
    if r < 0.55:
        return ast.BinOp(left=random_expr(depth - 1), op=random.choice(ARITH_OPS)(),
                         right=random_expr(depth - 1))
    if r < 0.70:                               # if/else expression
        test = ast.Compare(left=random_expr(depth - 1), ops=[random.choice(CMP_OPS)()],
                           comparators=[random_expr(depth - 1)])
        return ast.IfExp(test=test, body=random_expr(depth - 1),
                         orelse=random_expr(depth - 1))
    if r < 0.85:                               # min/max/abs call
        fname = random.choice(list(FUNC_CALLS))
        return ast.Call(func=ast.Name(id=fname, ctx=ast.Load()),
                        args=[random_expr(depth - 1) for _ in range(FUNC_CALLS[fname])],
                        keywords=[])
    if r < 0.93:                               # bounded power
        return ast.BinOp(left=random_expr(depth - 1), op=ast.Pow(),
                         right=ast.Constant(value=random.choice([2, 3])))
    return ast.UnaryOp(op=ast.USub(), operand=random_expr(depth - 1))


def expr_to_str(node: ast.expr) -> str:
    return ast.unparse(node)


def _expr_nodes(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.expr)]


class _Replacer(ast.NodeTransformer):
    def __init__(self, target, new):
        self.target, self.new = target, new

    def visit(self, node):
        node = self.generic_visit(node)
        return self.new if node is self.target else node


def mutate(node: ast.expr) -> ast.expr:
    tree = copy.deepcopy(node)
    nodes = _expr_nodes(tree)
    target = random.choice(nodes)
    op = random.random()

    if op < 0.30:
        new = random_expr(depth=2)
    elif op < 0.50:
        consts = [n for n in nodes if isinstance(n, ast.Constant)]
        if not consts:
            new = random_expr(depth=1)
        else:
            c = random.choice(consts)
            new = ast.Constant(value=max(0, min(120, c.value + random.choice([-2, -1, 1, 2]))))
            target = c
    elif op < 0.65:
        binops = [n for n in nodes if isinstance(n, ast.BinOp) and not isinstance(n.op, ast.Pow)]
        if not binops:
            new = random_expr(depth=1)
        else:
            b = random.choice(binops)
            new = copy.deepcopy(b); new.op = random.choice(ARITH_OPS)()
            target = b
    elif op < 0.78:
        cmps = [n for n in nodes if isinstance(n, ast.Compare)]
        if not cmps:
            new = random_expr(depth=1)
        else:
            cmp_ = random.choice(cmps)
            new = copy.deepcopy(cmp_); new.ops = [random.choice(CMP_OPS)()]
            target = cmp_
    elif op < 0.90:                            # collapse an IfExp to one branch
        ifs = [n for n in nodes if isinstance(n, ast.IfExp)]
        if not ifs:
            new = random_expr(depth=1)
        else:
            ie = random.choice(ifs)
            new = copy.deepcopy(random.choice([ie.body, ie.orelse]))
            target = ie
    else:                                        # grow: wrap the target node
        r2 = random.random()
        if r2 < 0.40:
            new = ast.BinOp(left=copy.deepcopy(target), op=random.choice(ARITH_OPS)(),
                            right=random_expr(depth=1))
        elif r2 < 0.70:                          # wrap in min/max — key for clamp patterns
            fname = random.choice(["min", "max"])
            new = ast.Call(func=ast.Name(id=fname, ctx=ast.Load()),
                           args=[copy.deepcopy(target), random_expr(depth=1)], keywords=[])
        else:                                    # wrap in if/else — key for piecewise logic
            test = ast.Compare(left=random_expr(depth=1), ops=[random.choice(CMP_OPS)()],
                               comparators=[random_expr(depth=1)])
            new = ast.IfExp(test=test, body=copy.deepcopy(target),
                            orelse=random_expr(depth=1))

    tree = _Replacer(target, new).visit(tree)
    ast.fix_missing_locations(tree)
    return tree


def crossover(a: ast.expr, b: ast.expr) -> ast.expr:
    child, donor = copy.deepcopy(a), copy.deepcopy(b)
    target = random.choice(_expr_nodes(child))
    new = random.choice(_expr_nodes(donor))
    child = _Replacer(target, copy.deepcopy(new)).visit(child)
    ast.fix_missing_locations(child)
    return child


def structure_hash(node: ast.expr) -> str:
    class Norm(ast.NodeTransformer):
        def visit_Constant(self, n): return ast.Constant(value=0)
    normed = Norm().visit(copy.deepcopy(node))
    return hashlib.md5(ast.dump(normed).encode()).hexdigest()[:12]

# --------------------------------------------------------------------------
# 4. Verifier — unit tests + sandbox whitelist + anti-gaming + canary
# --------------------------------------------------------------------------

ALLOWED_NAMES = {"n", "min", "max", "abs"}
BANNED_NODES = (ast.Import, ast.ImportFrom, ast.Attribute, ast.Subscript,
                ast.Lambda, ast.Await, ast.Yield, ast.Global, ast.Nonlocal,
                ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
                ast.While, ast.For, ast.With, ast.Try, ast.Raise, ast.Assert)


@dataclass
class EvalResult:
    code: str
    fitness: float
    confidence: float
    calibration_penalty: float
    adjusted_fitness: float
    tests_passed: int = 0
    tests_total: int = 0
    checks: dict = field(default_factory=dict)
    error: str | None = None


class CodeVerifier:
    def __init__(self, task: dict, time_budget_s=0.5, lambda_calib=0.5):
        self.task = task
        self.time_budget = time_budget_s
        self.lambda_calib = lambda_calib
        self.expected = {split: [self._ref(x) for x in task[split]]
                         for split in ("train", "val", "heldout")}

    def _ref(self, x):
        return eval(self.task["reference"], {"__builtins__": {"min": min, "max": max, "abs": abs}},
                    {"n": x})

    # -- canary: the evaluator must grade the reference solution perfectly --
    def self_test(self) -> bool:
        for split in ("train", "val"):
            preds = self._run(self.task["reference"], self.task[split])
            if preds is None or preds != self.expected[split]:
                return False
        return True

    # -- sandboxed execution ----------------------------------------------
    @staticmethod
    def _whitelist_ok(node: ast.expr) -> bool:
        for n in ast.walk(node):
            if isinstance(n, BANNED_NODES):
                return False
            if isinstance(n, ast.Name) and n.id not in ALLOWED_NAMES:
                return False
            if isinstance(n, ast.Call):
                if not (isinstance(n.func, ast.Name) and n.func.id in FUNC_CALLS
                        and len(n.args) == FUNC_CALLS[n.func.id] and not n.keywords):
                    return False
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
                if not (isinstance(n.right, ast.Constant)
                        and isinstance(n.right.value, int) and n.right.value in (2, 3)):
                    return False
            if isinstance(n, ast.Constant):
                if not isinstance(n.value, int) or isinstance(n.value, bool) or abs(n.value) > 1000:
                    return False
        return True

    def _run(self, code_str: str, inputs: list) -> list | None:
        try:
            node = ast.parse(code_str, mode="eval").body
            if not self._whitelist_ok(node):
                return None
            fn = compile(ast.fix_missing_locations(ast.Expression(body=node)),
                         "<candidate>", "eval")
            env = {"__builtins__": {}}
            safe = {"min": min, "max": max, "abs": abs}
            preds = []
            for x in inputs:
                v = eval(fn, env, {**safe, "n": x})
                if isinstance(v, float) or not isinstance(v, (int, bool)):
                    return None
                preds.append(v)
            return preds
        except Exception:
            return None

    def evaluate(self, code_str: str) -> EvalResult:
        checks = {}
        t0 = time.perf_counter()
        preds = self._run(code_str, self.task["train"])
        elapsed = time.perf_counter() - t0
        checks["runs_safely"] = preds is not None
        if preds is None:
            return EvalResult(code_str, 0.0, 0.0, 0.0, 0.0,
                              tests_total=len(self.task["train"]),
                              checks=checks, error="exec_or_whitelist_failed")

        checks["within_time_budget"] = elapsed <= self.time_budget

        try:
            node = ast.parse(code_str, mode="eval").body
        except Exception:
            node = None
        uses_input = node is not None and any(
            isinstance(n, ast.Name) and n.id == "n" for n in ast.walk(node))
        checks["uses_input_variable"] = uses_input     # constant => memorizing
        n_nodes = len(list(ast.walk(node))) if node is not None else 999
        checks["complexity_ok"] = n_nodes <= 80

        passed = sum(1 for p, e in zip(preds, self.expected["train"]) if p == e)
        total = len(self.task["train"])
        fit = passed / total
        fit *= pow(0.995, max(0, n_nodes - 20))        # anti-bloat
        if not uses_input:
            fit *= 0.05                                 # hardcode tax
        if not checks["within_time_budget"]:
            fit *= 0.5

        conf = fit                                     # claimed: visible pass rate
        preds_val = self._run(code_str, self.task["val"])
        acc_val = (sum(1 for p, e in zip(preds_val, self.expected["val"]) if p == e)
                   / len(self.task["val"])) if preds_val else 0.0
        calib_pen = self.lambda_calib * max(0.0, conf - acc_val)
        checks["generalizes_to_val"] = acc_val >= conf - 1e-9

        return EvalResult(code_str, round(fit, 6), round(conf, 4),
                          round(calib_pen, 6), round(fit - calib_pen, 6),
                          passed, total, checks)

    def heldout_report(self, code_str: str) -> dict:
        preds = self._run(code_str, self.task["heldout"])
        if preds is None:
            return {"heldout_accuracy": 0.0}
        acc = sum(1 for p, e in zip(preds, self.expected["heldout"]) if p == e) \
            / len(self.task["heldout"])
        return {"heldout_accuracy": round(acc, 4),
                "heldout_inputs": self.task["heldout"],
                "heldout_preds": preds, "heldout_expected": self.expected["heldout"]}

# --------------------------------------------------------------------------
# 5. Evolution loop
# --------------------------------------------------------------------------

@dataclass
class Candidate:
    node: ast.expr
    code: str
    generation: int
    result: EvalResult | None = None


class CodeEvolution:
    def __init__(self, verifier: CodeVerifier, task_spec: str,
                 pop_size=60, elite=4, tournament=3, novelty_bonus=0.02,
                 llm_fraction=0.0):
        self.v = verifier
        self.spec = task_spec
        self.pop_size, self.elite = pop_size, elite
        self.tournament = tournament
        self.novelty_bonus = novelty_bonus
        self.llm_fraction = llm_fraction
        self.archive, self.cache, self.history = set(), {}, []

    def _eval(self, cand: Candidate) -> Candidate:
        if cand.code in self.cache:
            cand.result = self.cache[cand.code]
        else:
            cand.result = self.v.evaluate(cand.code)
            h = structure_hash(cand.node)
            if h not in self.archive:
                self.archive.add(h)
                cand.result.adjusted_fitness = round(
                    cand.result.adjusted_fitness + self.novelty_bonus, 6)
            self.cache[cand.code] = cand.result
        return cand

    def _child(self, pop, gen) -> Candidate:
        def tourney():
            return max(random.sample(pop, min(self.tournament, len(pop))),
                       key=lambda c: c.result.adjusted_fitness)

        if random.random() < self.llm_fraction:
            parent = tourney()
            proposal = llm_propose(parent.code, self.spec)
            if proposal:
                try:
                    node = ast.parse(proposal, mode="eval").body
                    if CodeVerifier._whitelist_ok(node):
                        return Candidate(node, expr_to_str(node), gen)
                except Exception:
                    pass

        node = crossover(tourney().node, tourney().node) if random.random() < 0.25 \
            else mutate(tourney().node)
        return Candidate(node, expr_to_str(node), gen)

    def run(self, generations: int, tag: str = ""):
        assert self.v.self_test(), f"verifier self-test failed for {tag} — aborting"

        pop = []
        for _ in range(self.pop_size):
            node = random_expr(4, top=True)
            pop.append(self._eval(Candidate(node, expr_to_str(node), 0)))

        for gen in range(1, generations + 1):
            pop.sort(key=lambda c: c.result.adjusted_fitness, reverse=True)
            best = pop[0]
            mean_fit = sum(c.result.adjusted_fitness for c in pop) / len(pop)
            self.history.append({"gen": gen, "best_code": best.code,
                                 "best_adjusted": best.result.adjusted_fitness,
                                 "mean_adjusted": round(mean_fit, 4),
                                 "distinct_structures": len(self.archive)})
            if gen % 25 == 0 or gen == 1:
                print(f"  [{tag}] gen {gen:>3} | best {best.result.adjusted_fitness:.4f} "
                      f"| mean {mean_fit:.4f} | structures {len(self.archive):>4} "
                      f"| {best.code[:52]}")

            solved = (best.result.tests_passed == best.result.tests_total
                      and best.result.checks.get("generalizes_to_val")
                      and best.result.checks.get("uses_input_variable"))
            if solved:
                print(f"  [{tag}] solved at generation {gen}: {best.code}")
                break

            elites = [copy.deepcopy(c) for c in pop[:self.elite]]
            pop = elites + [self._eval(self._child(pop, gen))
                            for _ in range(self.pop_size - self.elite)]

        pop.sort(key=lambda c: c.result.adjusted_fitness, reverse=True)
        return pop[0]

# --------------------------------------------------------------------------
# 6. CLI
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="all", choices=list(TASKS) + ["all"])
    ap.add_argument("--out", default="./phase2_results")
    ap.add_argument("--gens", type=int, default=150)
    ap.add_argument("--pop", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--llm-fraction", type=float, default=0.0)
    args = ap.parse_args()

    random.seed(args.seed)
    os.makedirs(args.out, exist_ok=True)
    names = list(TASKS) if args.task == "all" else [args.task]
    summary = {}

    for name in names:
        task = TASKS[name]
        print(f"\n=== TASK: {name} — {task['spec']}")
        verifier = CodeVerifier(task)
        loop = CodeEvolution(verifier, task["spec"], pop_size=args.pop,
                             llm_fraction=args.llm_fraction)
        best = loop.run(args.gens, tag=name)

        report = {"task": name, "spec": task["spec"], "seed": args.seed,
                  "best_solution": best.code, "reference": task["reference"],
                  "exact_match": best.code.replace(" ", "") ==
                                 task["reference"].replace(" ", ""),
                  "verifier": asdict(best.result),
                  "held_out": verifier.heldout_report(best.code),
                  "stats": {"generations_run": loop.history[-1]["gen"] if loop.history else 0,
                            "distinct_structures": len(loop.archive),
                            "unique_candidates": len(loop.cache)}}
        summary[name] = {"best": best.code, "heldout": report["held_out"]["heldout_accuracy"],
                         "train_pass": f"{best.result.tests_passed}/{best.result.tests_total}",
                         "exact_match": report["exact_match"]}

        with open(os.path.join(args.out, f"{name}_report.json"), "w") as f:
            json.dump(report, f, indent=2)
        with open(os.path.join(args.out, f"{name}_solution.py"), "w") as f:
            f.write(f"# Task: {task['spec']}\n"
                    f"# Evolved at generation {best.generation} | "
                    f"held-out accuracy: {report['held_out']['heldout_accuracy']}\n"
                    f"def solve(n):\n    return {best.code}\n")

    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== SUMMARY ===")
    for name, s in summary.items():
        print(f"  {name:<16} train {s['train_pass']:>6} | held-out {s['heldout']:.2f} "
              f"| exact-match {s['exact_match']} | {s['best'][:48]}")
    print(f"\nReports written to {args.out}/")


if __name__ == "__main__":
    main()
