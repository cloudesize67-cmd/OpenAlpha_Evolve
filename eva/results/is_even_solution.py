# Task: solve(n) returns True if integer n is even, else False.
# Evolved at generation 84 | held-out accuracy: 1.0
def solve(n):
    return (n if 10 * n % 4 <= 9 * n * (6 * n == n + n) * n else 8) == n
