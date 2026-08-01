"""Seed program for the torsion-filter task.

Implements ``filter_signal(x, fs)``: given a noisy 1-D measurement and its
sample rate, return an array of the same length estimating the clean torsion
signal. The evolutionary search mutates only the code between the EVOLVE-BLOCK
markers; everything outside them is fixed scaffolding.

This starting point is deliberately modest -- a mean-subtracting detrend
followed by a short moving average. It removes the DC offset but leaves most of
the low-frequency drift and out-of-band interference, so it scores *below* the
human baseline. Improving it (a real bandpass around the science band, better
stopband rejection, less passband distortion) is the point of the search.
"""
import numpy as np


def filter_signal(x, fs):
    x = np.asarray(x, dtype=float)

    # EVOLVE-BLOCK-START filter
    # Naive baseline: remove the DC level, then smooth with a short boxcar.
    # This leaves drift and mains interference largely intact -- beat it.
    detrended = x - np.mean(x)
    window = 5
    kernel = np.ones(window) / window
    estimate = np.convolve(detrended, kernel, mode="same")
    # EVOLVE-BLOCK-END filter

    return estimate
