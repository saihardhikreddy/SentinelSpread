"""
The CNN "Blue Team" adversary.

A small 1-D convolutional network over a raw I/Q capture of shape (2, length). It is the detector
the Stage 5 suite only gestures at: instead of five fixed statistics it learns its own filters
from labelled captures, so it can pick up on structure no single hand-built test names. Its
probability output is thresholded on noise-only scores at a chosen false-alarm rate (`pfa`),
exactly as every Stage 5 detector is, so its probability of detection is quoted on the same
footing and the numbers are comparable.

PyTorch is imported lazily inside the methods, so importing this module never requires torch; only
building or training an adversary does. The network is deliberately small (three strided conv
layers, global average pool, a linear head) and trains in seconds on CPU.
"""

from typing import Optional, Sequence

import numpy as np

from sentinelspread.adversary.dataset import iq_to_array, segments_to_array


def torch_available() -> bool:
    """True if PyTorch can be imported — lets callers (and tests) skip cleanly without it."""
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _build_net(length: int):
    import torch.nn as nn

    class _IQNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv1d(2, 16, kernel_size=7, stride=2, padding=3), nn.ReLU(),
                nn.Conv1d(16, 32, kernel_size=5, stride=2, padding=2), nn.ReLU(),
                nn.Conv1d(32, 32, kernel_size=3, stride=2, padding=1), nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Linear(32, 2)

        def forward(self, x):
            return self.head(self.features(x).squeeze(-1))

    return _IQNet()


class CNNAdversary:
    """A trainable I/Q detector with the same detect/calibrate interface as the Stage 5 detectors."""

    def __init__(self, length: int, lr: float = 1e-3, epochs: int = 25, batch_size: int = 64,
                 seed: int = 0, device: str = "cpu"):
        self.length = int(length)
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self.device = device
        self.name = "cnn"
        self.threshold = 0.5
        self.pfa = 0.0
        self.net = None

    # -- training -------------------------------------------------------------------------------
    def fit(self, x: np.ndarray, y: np.ndarray) -> "CNNAdversary":
        """Train on arrays: x is (N, 2, length) float32, y is 0/1."""
        import torch

        torch.manual_seed(self.seed)
        self.net = _build_net(self.length).to(self.device)
        xt = torch.as_tensor(np.asarray(x, dtype=np.float32), device=self.device)
        yt = torch.as_tensor(np.asarray(y, dtype=np.int64), device=self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        loss_fn = torch.nn.CrossEntropyLoss()
        n = len(xt)
        rng = np.random.default_rng(self.seed)
        self.net.train()
        for _ in range(self.epochs):
            for idx in np.array_split(rng.permutation(n), max(1, n // self.batch_size)):
                if len(idx) == 0:
                    continue
                b = torch.as_tensor(idx, device=self.device)
                opt.zero_grad()
                loss = loss_fn(self.net(xt[b]), yt[b])
                loss.backward()
                opt.step()
        self.net.eval()
        return self

    def fit_segments(self, noise_seg: Sequence[np.ndarray], signal_seg: Sequence[np.ndarray]) -> "CNNAdversary":
        """Train directly from complex captures (as the Stage 5 detectors are fit)."""
        x = np.concatenate([segments_to_array(noise_seg, self.length),
                            segments_to_array(signal_seg, self.length)])
        y = np.concatenate([np.zeros(len(noise_seg)), np.ones(len(signal_seg))])
        return self.fit(x, y)

    # -- scoring --------------------------------------------------------------------------------
    def scores(self, x: np.ndarray) -> np.ndarray:
        """Signal-present probability for each capture in an (N, 2, length) array."""
        import torch

        if self.net is None:
            raise RuntimeError("CNNAdversary.fit must be called before scoring")
        with torch.no_grad():
            xt = torch.as_tensor(np.asarray(x, dtype=np.float32), device=self.device)
            p = torch.softmax(self.net(xt), dim=1)[:, 1]
        return p.cpu().numpy().astype(float)

    def score(self, capture: np.ndarray) -> float:
        a = iq_to_array(capture)
        m = min(self.length, a.shape[1])
        buf = np.zeros((1, 2, self.length), dtype=np.float32)
        buf[0, :, :m] = a[:, :m]
        return float(self.scores(buf)[0])

    def scores_segments(self, segments: Sequence[np.ndarray]) -> np.ndarray:
        if len(segments) == 0:
            return np.zeros(0)
        return self.scores(segments_to_array(segments, self.length))

    # -- calibration and decision (same contract as the Stage 5 detectors) ----------------------
    def calibrate(self, noise_segments: Sequence[np.ndarray], pfa: float = 0.01) -> float:
        s = np.sort(self.scores_segments(noise_segments))
        keep = min(max(int(np.ceil((1.0 - pfa) * len(s))) - 1, 0), len(s) - 1)
        self.threshold = float(s[keep])
        self.pfa = pfa
        return self.threshold

    def detection_rate(self, segments: Sequence[np.ndarray]) -> float:
        if len(segments) == 0:
            return 0.0
        return float(np.mean(self.scores_segments(segments) > self.threshold))

    def detect(self, capture: np.ndarray) -> bool:
        return self.score(capture) > self.threshold
