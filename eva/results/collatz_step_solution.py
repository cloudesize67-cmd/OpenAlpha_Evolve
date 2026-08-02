# Task: solve(n) returns one Collatz step: n//2 if n is even, 3*n+1 if n is odd (integer n >= 1).
# Evolved at generation 34 | held-out accuracy: 0.5
def solve(n):
    return n // (0 - (n - n) - 2) % n
