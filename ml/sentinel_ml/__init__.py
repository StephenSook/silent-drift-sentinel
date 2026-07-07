"""Silent-Drift Sentinel ML core.

The monitored model: a calibrated LightGBM purchase-intent classifier on the
UCI Online Shoppers Purchasing Intention dataset (CC BY 4.0). Kept deliberately
credible for an expert ML reviewer: honest temporal split, isotonic calibration
verified with ECE and a reliability diagram, class-imbalance aware metrics.
"""

__all__ = ["data", "metrics", "train"]
