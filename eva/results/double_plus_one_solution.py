# Task: solve(n) returns 2*n + 1 for integer n.
# Evolved at generation 99 | VERIFIED for harvest
# held-out accuracy: 1.0 | probe accuracy: 1.0
def solve(n):
    return n + 1 + (n if n < n else n)
