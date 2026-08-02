# Task: solve(n) clamps integer n into [0, 100].
# Evolved at generation 23 | held-out accuracy: 1.0
def solve(n):
    return abs(max(0, min(100, n)))
