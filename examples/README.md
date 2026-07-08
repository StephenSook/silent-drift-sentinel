# Sample outputs

Artifacts the Silent-Drift Sentinel produces, so you can judge the quality without running it.

- `drift_signal.json` — the structured signal the drift detector emits and the agent consumes: the label-free performance drop (CBPE), the root-cause feature, the change type, the per-feature drift stats, and the data-quality fingerprint.
- `sample_rca.md` — a real root-cause narrative Claude wrote for the demo scenario, plus the exact `drift_causation` structured-property value the agent wrote onto the model.
- `reliability.png` — the calibration reliability diagram for the monitored model (raw vs isotonic-calibrated).

These are the actual outputs from a live run against DataHub, not mockups.
