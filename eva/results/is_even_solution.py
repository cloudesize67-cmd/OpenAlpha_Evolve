# Task: solve(n) returns True if integer n is even, else False.
# Evolved at generation 51 | VERIFIED for harvest
# held-out accuracy: 1.0 | probe accuracy: 1.0
def solve(n):
    return (0 >= n + 1) >= (100 * n % 8) ** 2
