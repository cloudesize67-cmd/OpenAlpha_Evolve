# Task: solve(n) returns the sum 0+1+...+n (closed form, integer n >= 0).
# Evolved at generation 85 | NOT VERIFIED — diagnostic artifact only, do not use as ground truth
# held-out accuracy: 0.0 | probe accuracy: 0.0
def solve(n):
    return n + (n + n + n) * n // 7
