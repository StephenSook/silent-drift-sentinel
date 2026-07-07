import numpy as np

from sentinel_ml.metrics import expected_calibration_error, reliability_curve


def test_ece_perfect_calibration_is_low():
    y = np.array([0, 0, 1, 1, 0, 1, 1, 0] * 50)
    # probabilities equal to the labels are trivially perfectly calibrated
    assert expected_calibration_error(y, y.astype(float)) < 1e-9


def test_ece_detects_overconfidence():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 2000)
    prob = np.full(2000, 0.9)  # claims 90% positive, reality ~50%
    assert expected_calibration_error(y, prob) > 0.3


def test_reliability_curve_shapes():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 500)
    prob = rng.random(500)
    conf, acc, cnt = reliability_curve(y, prob, n_bins=10)
    assert conf.shape == acc.shape == cnt.shape == (10,)
    assert cnt.sum() == 500
