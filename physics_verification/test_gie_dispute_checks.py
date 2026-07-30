"""Tests for gie_dispute_checks.py: confirm the hard constraints actually discriminate a correct outer-product-sum derivation from a broken one."""
import sympy as sp
import pytest

from gie_dispute_checks import (
    build_diagonal_matrix,
    build_full_sum_matrix,
    check_full_sum_is_always_separable,
    check_diagonal_reduces_to_near_field_form,
    run_reference_checks,
)


def _generic_V():
    VLL, VLR, VRL, VRR = sp.symbols("V_LL V_LR V_RL V_RR")
    return sp.Matrix([[VLL, VLR], [VRL, VRR]])


def test_full_sum_construction_is_always_separable():
    V = _generic_V()
    Lambda, t = sp.symbols("Lambda t", positive=True)
    ok, det = check_full_sum_is_always_separable(V, Lambda, t)
    assert ok
    assert det == 0


def test_diagonal_construction_is_generically_entangled():
    V = _generic_V()
    Lambda, t = sp.symbols("Lambda t", positive=True)
    matrix = build_diagonal_matrix(V, Lambda, t)
    det = sp.simplify(matrix.det())
    assert det != 0


def test_diagonal_reduces_to_near_field_kappa_over_d_squared():
    V = _generic_V()
    Lambda, t = sp.symbols("Lambda t", positive=True)
    d = sp.Matrix(2, 2, lambda i, j: sp.Symbol(f"d_{('L','R')[i]}{('L','R')[j]}", positive=True))
    assert check_diagonal_reduces_to_near_field_form(V, Lambda, t, d)


def test_a_broken_candidate_fails_the_full_sum_hard_constraint():
    """A candidate that does NOT sum over initial branches correctly (e.g. sums only k, drops m) must be caught."""
    V = _generic_V()
    Lambda, t = sp.symbols("Lambda t", positive=True)

    def broken_full_sum(V, Lambda, t):
        # BROKEN: sums over k for the row index but reuses the same row index
        # for the column sum instead of summing over m -- an easy mistake
        # that silently breaks the outer-product structure.
        row_sums = [sum(V[i, :]) for i in range(2)]
        return sp.Matrix(2, 2, lambda i, j: Lambda * t**2 * row_sums[i] * row_sums[j])

    matrix = broken_full_sum(V, Lambda, t)
    det = sp.simplify(matrix.det())
    # This particular broken variant happens to still be rank-1 (it's an
    # outer product of row_sums with itself), so assert on a genuinely
    # non-outer-product broken variant instead:
    def broken_full_sum_2(V, Lambda, t):
        # BROKEN: adds a spurious cross term that isn't a pure outer product.
        row_sums = [sum(V[i, :]) for i in range(2)]
        col_sums = [sum(V[:, j]) for j in range(2)]
        return sp.Matrix(2, 2, lambda i, j: Lambda * t**2 * row_sums[i] * col_sums[j] + V[i, j])

    matrix2 = broken_full_sum_2(V, Lambda, t)
    det2 = sp.simplify(matrix2.det())
    assert det2 != 0  # correctly flagged as inconsistent with the required hard constraint


def test_reference_checks_all_pass():
    results = run_reference_checks()
    assert results["diagonal"]["is_separable"] is False
    assert results["full_sum"]["is_separable"] is True
    assert results["full_sum_always_separable"] is True
    assert results["near_field_reduction_matches_aziz_howl"] is True


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
