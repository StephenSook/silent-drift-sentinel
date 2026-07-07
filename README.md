# Silent-Drift Sentinel

An on-call AI agent for the ML engineer who owns a silently degrading production model.

When a production model quietly loses accuracy, the Sentinel:

1. Detects the degradation from a real, externally computed drift signal (label-free performance estimation, not a raw distribution alarm).
2. Walks DataHub's ML lineage graph automatically to the specific upstream data change that caused it.
3. Identifies the model's owner from catalog metadata.
4. Writes a durable drift-causation object back onto the model in DataHub, so the next engineer or agent inherits the knowledge instead of rediscovering it.

Built for the Build with DataHub: The Agent Hackathon. Track: Agents That Do Real Work.

## What is genuinely novel

Drift detection and owner lookup are commodity plumbing, and we say so. The defensible contribution is the seam between two things no shipped tool combines: walking a catalog's model lineage to the upstream root cause, and writing a new drift-causation context class back onto the model entity in an open-source catalog. Root cause is framed honestly as lineage-guided correlation, not causal proof.

## Status

Under active development. Architecture, setup, and demo instructions land here as the build progresses.

## License

Apache-2.0. See [LICENSE](./LICENSE).
