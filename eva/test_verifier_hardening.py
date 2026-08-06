#!/usr/bin/env python3
"""
Exploit regression suite for the EVA verifier (design doc Section 5.8 / L6:
"every discovered specification-gaming incident becomes a regression test").

Both patterns below are real candidates the unhardened evolutionary loop
actually selected as its "best" solution in a committed run
(see eva/results/*_report.json in the commit history), which motivated the
hardening in phase2_code_evolution.py. Confirmed by direct execution against
a wide integer range, not by assumption:

  * sum_to_n: `min(n, 6) ** 2` passes enough of the tiny visible train split
    to look competitive, but is wrong outside roughly n <= 6 — a genuine
    memorization/overfitting exploit (P1-style reward hacking) that the old
    "uses_input_variable" hardcode check missed, because the candidate does
    reference `n`. Only a wide-range probe split catches it.
  * is_even: a convoluted boolean-arithmetic expression that turned out to be
    a mathematically valid (if absurdly overcomplicated) encoding of n % 2 ==
    0 -- NOT a correctness exploit, but the kind of unnecessary complexity
    the parsimony tiebreak (`selection_key`) exists to suppress in favor of
    simpler, equally-correct candidates.

Run: python3 eva/test_verifier_hardening.py
"""

from phase2_code_evolution import TASKS, CodeVerifier, Candidate, EvalResult, selection_key
import ast


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  OK: {msg}")


def test_sum_to_n_memorization_exploit_fails_probe_gate():
    verifier = CodeVerifier(TASKS["sum_to_n"])
    exploit_code = "min(n, 6) ** 2"

    result = verifier.evaluate(exploit_code)
    held_out = verifier.heldout_report(exploit_code)
    probe = verifier.probe_report(exploit_code)

    check(result.tests_passed < result.tests_total,
          "sum_to_n exploit does not even fully pass the visible train split")
    check(probe["probe_accuracy"] < 0.2,
          f"sum_to_n exploit must collapse on the wide probe split "
          f"(got {probe['probe_accuracy']})")
    check(held_out["heldout_accuracy"] < 0.2,
          "sum_to_n exploit must also fail the fixed held-out split")
    print("  sum_to_n memorization exploit correctly rejected by the harvest gate\n")


def test_is_even_bloated_formula_is_correct_but_not_preferred():
    verifier = CodeVerifier(TASKS["is_even"])
    bloated_code = ("(n if 10 * n % 4 <= 9 * n * (6 * n == n + n) * n else 8) == n")
    simple_code = "n % 2 == 0"

    probe_bloated = verifier.probe_report(bloated_code)
    probe_simple = verifier.probe_report(simple_code)
    check(probe_bloated["probe_accuracy"] == 1.0,
          "the bloated formula is genuinely correct everywhere -- "
          "this is a parsimony problem, not a correctness exploit")
    check(probe_simple["probe_accuracy"] == 1.0,
          "sanity: the minimal reference-equivalent formula is also correct")

    bloated_node = ast.parse(bloated_code, mode="eval").body
    simple_node = ast.parse(simple_code, mode="eval").body
    bloated = Candidate(bloated_node, bloated_code, 0, verifier.evaluate(bloated_code))
    simple = Candidate(simple_node, simple_code, 0, verifier.evaluate(simple_code))

    # The anti-bloat term in `evaluate()` already discounts the 42-node
    # formula below the 8-node one on raw fitness alone, so end-to-end
    # ranking already prefers the minimal form:
    check(selection_key(simple) > selection_key(bloated),
          "the minimal correct candidate must outrank the convoluted one end-to-end")
    print("  minimal correct candidate outranks the convoluted-but-correct one\n")

    # Isolate the tiebreak itself: two *equal-fitness* candidates differing
    # only in AST size must be ranked by complexity, not left ambiguous --
    # this is the mechanism that would have caught the original run's
    # bloated survivor had a same-fitness simpler rival been present.
    tied_simple = Candidate(simple_node, simple_code, 0,
                            EvalResult(simple_code, 1.0, 1.0, 0.0, 1.0, 14, 14, 8))
    tied_bloated = Candidate(bloated_node, bloated_code, 0,
                             EvalResult(bloated_code, 1.0, 1.0, 0.0, 1.0, 14, 14, 42))
    check(selection_key(tied_simple) > selection_key(tied_bloated),
          "at equal adjusted_fitness, selection_key must break ties toward fewer AST nodes")
    print("  Occam's-razor tiebreak correctly resolves equal-fitness ties\n")


def test_canary_covers_probe_split():
    verifier = CodeVerifier(TASKS["collatz_step"])
    check(verifier.self_test(),
          "canary self-test (train+val+probe) must pass for the reference solution")
    print("  canary self-test covers the probe split\n")


if __name__ == "__main__":
    print("=== EVA verifier hardening regression suite ===\n")
    test_sum_to_n_memorization_exploit_fails_probe_gate()
    test_is_even_bloated_formula_is_correct_but_not_preferred()
    test_canary_covers_probe_split()
    print("All regression checks passed.")
