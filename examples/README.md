# Sample outputs

The actual artifacts the Silent-Drift Sentinel produces on the demo scenario (an
upstream job that starts emitting `PageValues = 0`), so you can judge the quality
without running it. These are real outputs from the code in this repo, not mockups.

## What the detector emits
- `drift_signal.json`: the structured signal the drift detector emits and the agent
  consumes: the label-free performance drop (CBPE), the root-cause feature, the
  change type, the per-feature drift stats, and the data-quality fingerprint.
- `eval_report.json`: the detector evaluated over a labeled scenario suite (clean,
  null/default regression, unit rescale, default-value regression, benign shift):
  alarm precision 1.0 / recall 1.0 (no false alarms, no misses), root-cause
  localization 1.0, change-type accuracy 1.0. Regenerate with `python ml/scripts/run_eval.py`.
- `reliability.png`: the calibration reliability diagram for the monitored model
  (raw vs isotonic-calibrated).

## What the agent writes back
- `drift_causation.txt`: the exact value written onto the mlModel as a typed
  structured property (`io.sentinel.drift_causation`), so the next engineer or agent
  inherits the cause instead of rediscovering it.
- `sample_rca.md`: a real root-cause narrative Claude wrote, plus the property value.
- `proposed_fix.md`: the metadata-aware code-gen output, a paste-ready dbt test, a
  Great Expectations expectation, and a plain SQL guard, generated from the diagnosed
  change type and written onto the model as a second typed property.
- `incident.json`: the incident raised on the upstream **dataset** (incidents cannot
  target an mlModel in DataHub, which is why the write-back is split across the two
  entities).
- `run_trace.json`: the streamed agent trace (the same events the dashboard renders):
  detect, traverse lineage, root-cause over Agent Context Kit reads, propose fix,
  write back.

The write path is deterministic code, never the LLM, so the demo cannot wobble. Root
cause is stated honestly as lineage-guided correlation, not proven causation.
