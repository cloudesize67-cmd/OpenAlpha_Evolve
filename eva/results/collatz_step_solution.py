# Task: solve(n) returns one Collatz step: n//2 if n is even, 3*n+1 if n is odd (integer n >= 1).
# Evolved at generation 59 | NOT VERIFIED — diagnostic artifact only, do not use as ground truth
# held-out accuracy: 0.5 | probe accuracy: 0.55
def solve(n):
    return (n if n // 2 else 9) // 2
