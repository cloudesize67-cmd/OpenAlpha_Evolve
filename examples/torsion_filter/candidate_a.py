import numpy as np
def apply_filter(x, fs):
    m = np.arange(801) - 400.0
    h6 = np.sinc(2*6.5/fs * m) * np.hamming(801); h6 /= h6.sum()
    h3 = np.sinc(2*3.5/fs * m) * np.hamming(801); h3 /= h3.sum()
    k = h6 - h3
    y = np.convolve(x, k, mode="same")
    return np.convolve(y[::-1], k, mode="same")[::-1]
