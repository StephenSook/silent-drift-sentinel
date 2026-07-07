"""Calibration metrics: Expected Calibration Error and reliability-curve data.

Calibration is load-bearing for this project. NannyML CBPE estimates performance
from the model's predicted probabilities, so those probabilities must be
trustworthy. We verify with ECE and a reliability diagram, and report ECE both
before and after isotonic calibration to show the lift.
"""
from __future__ import annotations

import numpy as np


def expected_calibration_error(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> float:
    """Equal-width-bin ECE: sum over bins of (bin weight) * |accuracy - confidence|."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(y_prob, edges) - 1, 0, n_bins - 1)
    total = len(y_true)
    ece = 0.0
    for b in range(n_bins):
        mask = bin_idx == b
        count = int(mask.sum())
        if count == 0:
            continue
        confidence = float(y_prob[mask].mean())
        accuracy = float(y_true[mask].mean())
        ece += (count / total) * abs(accuracy - confidence)
    return ece


def reliability_curve(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (bin_confidence, bin_accuracy, bin_count) for a reliability diagram."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(y_prob, edges) - 1, 0, n_bins - 1)
    conf = np.full(n_bins, np.nan)
    acc = np.full(n_bins, np.nan)
    cnt = np.zeros(n_bins, dtype=int)
    for b in range(n_bins):
        mask = bin_idx == b
        cnt[b] = int(mask.sum())
        if cnt[b] > 0:
            conf[b] = float(y_prob[mask].mean())
            acc[b] = float(y_true[mask].mean())
    return conf, acc, cnt
