"""
Forward error correction: Hamming(7,4) single-error correction with block interleaving.

Each group of 4 message bits becomes a 7-bit codeword that can correct any single bit flip in
that codeword. Interleaving spreads the bits of each codeword apart in the transmitted stream so
that a short burst of channel errors lands on different codewords rather than overwhelming one.

Rate is 4/7: the payload grows by 75%, in exchange for tolerating isolated bit errors that would
otherwise make AES-GCM reject the whole message.
"""

import numpy as np

# Generator and parity-check matrices for systematic Hamming(7,4): codeword = [d0 d1 d2 d3 p0 p1 p2]
_G = np.array([
    [1, 0, 0, 0, 1, 1, 0],
    [0, 1, 0, 0, 1, 0, 1],
    [0, 0, 1, 0, 0, 1, 1],
    [0, 0, 0, 1, 1, 1, 1],
], dtype=np.uint8)

_H = np.array([
    [1, 1, 0, 1, 1, 0, 0],
    [1, 0, 1, 1, 0, 1, 0],
    [0, 1, 1, 1, 0, 0, 1],
], dtype=np.uint8)

# syndrome (as an integer, bit order [s0 s1 s2]) -> index of the bit to flip, or -1
_SYNDROME_WEIGHTS = np.array([1, 2, 4])
_SYNDROME_TO_BIT = np.full(8, -1, dtype=np.int64)
for _col in range(7):
    _SYNDROME_TO_BIT[int(_H[:, _col] @ _SYNDROME_WEIGHTS)] = _col


def encode(bits: np.ndarray) -> np.ndarray:
    """Encode a bit array (padded to a multiple of 4) into Hamming(7,4) codewords, interleaved."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    pad = (-len(bits)) % 4
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    blocks = bits.reshape(-1, 4)
    code = (blocks @ _G) % 2                      # (n, 7)
    # interleave: transmit all bit-0s, then all bit-1s, ... so a burst hits one position per word
    return code.T.ravel().astype(np.uint8)


def decode(bits: np.ndarray, num_message_bits: int) -> tuple:
    """De-interleave, correct one error per codeword, return (message_bits, errors_corrected).
    `num_message_bits` trims the padding added at encode time."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    n_words = len(bits) // 7
    bits = bits[:n_words * 7]
    code = bits.reshape(7, n_words).T.copy()      # undo the interleave
    syndromes = (code @ _H.T) % 2                 # (n_words, 3)
    # Vectorized: look up every word's bad bit at once instead of looping in Python.
    flips = _SYNDROME_TO_BIT[syndromes @ _SYNDROME_WEIGHTS]
    rows = np.nonzero(flips >= 0)[0]
    code[rows, flips[rows]] ^= 1
    corrected = int(len(rows))
    message = code[:, :4].ravel()[:num_message_bits]
    return message.astype(np.uint8), corrected
