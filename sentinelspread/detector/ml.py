"""
Machine-learning detector: one classifier over the whole feature vector.

Trained on labelled captures (noise vs signal present), then its probability output is
thresholded on noise-only scores the same way the single-feature detectors are, so its
detection rate is quoted at the same false-alarm budget.
"""

from typing import Optional, Sequence

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from sentinelspread.detector.features import FEATURE_NAMES, feature_vector


class MLDetector:
    def __init__(self, noise_reference: float = 1.0, n_estimators: int = 120, random_state: int = 0):
        self.noise_reference = noise_reference
        self.scaler = StandardScaler()
        self.model = RandomForestClassifier(
            n_estimators=n_estimators, random_state=random_state, min_samples_leaf=2)
        self.threshold = 0.5
        self.pfa = 0.0
        self.name = "ml"
        self._fitted = False

    def features(self, segments: Sequence[np.ndarray]) -> np.ndarray:
        return np.array([feature_vector(s, self.noise_reference) for s in segments], dtype=float)

    def fit(self, noise_segments: Sequence[np.ndarray], signal_segments: Sequence[np.ndarray]) -> "MLDetector":
        x = np.vstack([self.features(noise_segments), self.features(signal_segments)])
        y = np.concatenate([np.zeros(len(noise_segments)), np.ones(len(signal_segments))])
        self.model.fit(self.scaler.fit_transform(x), y)
        self._fitted = True
        return self

    def score(self, x: np.ndarray) -> float:
        if not self._fitted:
            raise RuntimeError("MLDetector.fit must be called before scoring")
        f = self.scaler.transform(feature_vector(x, self.noise_reference).reshape(1, -1))
        return float(self.model.predict_proba(f)[0, 1])

    def scores(self, segments: Sequence[np.ndarray]) -> np.ndarray:
        return np.array([self.score(s) for s in segments], dtype=float)

    def calibrate(self, noise_segments: Sequence[np.ndarray], pfa: float = 0.01) -> float:
        s = np.sort(self.scores(noise_segments))
        keep = min(max(int(np.ceil((1.0 - pfa) * len(s))) - 1, 0), len(s) - 1)
        self.threshold = float(s[keep])
        self.pfa = pfa
        return self.threshold

    def detect(self, x: np.ndarray) -> bool:
        return self.score(x) > self.threshold

    def detection_rate(self, segments: Sequence[np.ndarray]) -> float:
        if len(segments) == 0:
            return 0.0
        return float(np.mean([self.detect(s) for s in segments]))

    def importances(self) -> dict:
        if not self._fitted:
            raise RuntimeError("MLDetector.fit must be called first")
        return dict(zip(FEATURE_NAMES, (round(float(v), 4) for v in self.model.feature_importances_)))
