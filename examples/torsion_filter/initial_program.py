"""
initial_program.py -- seed filter for the torsion-balance denoise task.
Only code inside the EVOLVE-BLOCK markers is mutated by the evolutionary
search. Signature must stay: apply_filter(noisy: np.ndarray, fs: float) -> np.ndarray
"""
import numpy as np


# EVOLVE-BLOCK-START
def apply_filter(noisy, fs):
    """Naive baseline: 25-tap moving average. Returns filtered signal,
    same length as input."""
    return np.convolve(noisy, np.ones(25) / 25, mode="same")
# EVOLVE-BLOCK-END
