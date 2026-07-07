# CLAUDE.md — The Silent-Drift Sentinel

This file gives Claude Code the full context and hard constraints for this project. Read it before writing any code.

## What we are building
An on-call AI agent for the ML engineer who owns a silently-degrading production model. It:
1. Detects the degradation from a real, externally-computed drift signal.
2. Walks DataHub's ML lineage graph automatically to the specific upstream data change that caused it.
3. Identifies the model's owner from catalog metadata.
4. Writes a durable drift-causation object back onto the model so the next engineer or agent inherits the knowledge.

This is a submission for the Build with DataHub: The Agent Hackathon (deadline August 10). Track: Agents That Do Real Work. Positioned for the Grand Prize.

## The one non-negotiable design fact
Incidents CANNOT be raised on mlModel entities in DataHub. They can only be raised on datasets, charts, dashboards, dataFlows, dataJobs, and schemaFields. This is verified against the incident metamodel. Therefore the write-back is split:
- On the MODEL: a typed structured property (`drift_causation`) via the MCP `add_structured_properties` tool, plus a context document via `save_document`.
- On the UPSTREAM DATASET: an incident via the GraphQL `raiseIncident` mutation (NOT an MCP tool, and there is no typed Python SDK for incidents yet, so call GraphQL directly).

Do NOT use `update_description` in the open-source path. It is Cloud-only in recent MCP versions. Use `add_structured_properties` and `save_document`, which are OSS-available under the mutation flag.

## Day-one tasks (do these first, before building anything else)
These are the three things the fact-check could not fully close from docs. Verify each against a live `datahub docker quickstart` instance before building on them. If any fails, the design shifts, so confirm now.
1. Confirm a structured property can be written to an mlModel and renders on its page. (This is the primary write-back and must work.)
2. Confirm a context document can link to an mlModel as a related asset. If constrained, fall back to structured-property-only for the model attachment.
3. Confirm `TOOLS_IS_MUTATION_ENABLED=true` on self-hosted `mcp-server-datahub` >= v0.5.0 exposes `add_structured_properties` and `save_document`, and confirm a `raiseIncident` GraphQL call works on a dataset.

Also verify early: `get_lineage` traverses downstream from a raw table through the feature layer to the model. The whole concept rests on this working.

## The stack (decided; do not re-litigate)
- Front-end: Next.js 16 (App Router) + React 19, shadcn/ui on Base UI + Tailwind v4 (OKLCH dark theme). Lineage graph = React Flow (@xyflow/react) with ELK/dagre DAG layout and custom entity-type node cards. Drift charts = Apache ECharts. Agent streaming UI = CopilotKit consuming AG-UI events. Motion for micro-interactions; GSAP for the write-back reveal.
- Back-end: Python. FastAPI + sse-starlette streaming AG-UI events over SSE. Agent = LangGraph state machine (five nodes: Detect, Traverse, Root-Cause, Identify Owner, Write-Back), Pydantic-typed state, driven by Claude (GPT fallback via LiteLLM). LangGraph Postgres checkpointing for durability.
- ML core: two layers. Primary signal = label-free performance estimation (NannyML CBPE for classification / DLE for regression). Diagnostic = per-feature drift (KS numeric, Chi-squared categorical) with multiple-testing correction (Bonferroni/FDR) + data-quality checks (null rate, cardinality, range). The monitored model is LightGBM on realistic tabular data, calibrated (isotonic), verified with ECE + reliability diagram, honest temporal train/val/test split.
- DataHub integration: self-hosted `mcp-server-datahub` over streamable HTTP, connected via `langchain-mcp-adapters`. Service-account PAT (`DATAHUB_GMS_URL` + `DATAHUB_GMS_TOKEN`) with a minimal metadata policy (EDIT_ENTITY_PROPERTIES + EDIT_ENTITY_INCIDENTS + VIEW_ENTITY_PAGE, scoped to dataset/mlModel). Every mutation gated behind a LangGraph interrupt (human-in-the-loop).
- Substrate: `datahub docker quickstart` + `showcase-ecommerce` datapack (via the loader, do not vendor JSON) + local MLflow (>= 1.28.0) ingesting a real trained model, with the feature/deployment layer SDK-emitted.
- Persistence: PostgreSQL backbone (LangGraph checkpoints, drift time-series, JSONB lineage cache, causation objects, app data). Redis/Valkey for SSE pub/sub and caching. No graph DB (DataHub is the graph source of truth).
- Secrets: Doppler or Infisical, not committed env files. Short-lived rotated DataHub tokens.

## Environment pins
- MLflow >= 1.28.0
- mcp-server-datahub >= v0.5.0 (mutation flag on, self-hosted against DataHub Core)
- Latest `acryl-datahub` CLI/SDK
- Docker: 2 CPUs, 8GB RAM, 2GB swap, ~13GB disk
- Python 3.10+
- Incidents via GraphQL (no typed Python SDK yet)

## Hard rules for all code and prose
- No em-dashes anywhere. In code comments, commit messages, docs, the README, the video script, everything. This is a deliberate standing preference.
- Plain builder voice. No marketing language, no corporate fluff, no startup-casual filler.
- Keep the LLM out of the write path. The agent reasons; deterministic code executes the DataHub writes. This is what keeps the demo from wobbling live.
- Product UI stays generic and universal. No hardcoded persona names in the product layer. Named personas belong only in the pitch narration.
- The private methodology behind this project must NEVER appear in any public artifact, repo, deliverable, or teammate-facing document. Never reference it, never commit it, never push it to GitHub in any form.
- Explain technical steps simply and concretely, as if the reader is hearing them for the first time. Break every step down individually.
- Write-ahead every DataHub mutation to a local copy so a failed write retries idempotently.

## The demo hero moment (what everything serves)
The DataHub model page changing live: the agent detects drift, and on screen a drift-degraded tag badge plus a typed `drift_causation` property block appears on the model, naming the exact upstream column that changed and the owner, with a linked RCA document, and a companion incident lands on the upstream dataset with its health badge. Build a recorded/deterministic demo mode (fixed LLM responses + cached DataHub data) so it streams identically every time, with the same code path able to run live.

## The originality framing (for README, video, any judge-facing text)
Concede drift detection and owner lookup as composed commodities. Lead with the two novel parts: automated model-lineage root-cause, and the write-back of a new context class onto the model entity in an open-source catalog. Name the prior art (Monte Carlo, Arize, Fiddler, Databricks Lakehouse Monitoring, Atlan, OpenMetadata) and state precisely why each stops short: data-not-models, feature-space-not-lineage, findings-siloed, vision-not-shipped. Frame root-cause honestly as lineage-guided correlation, not proven causation.

## Repo hygiene
- Apache-2.0 license.
- Clean README, architecture diagram, `examples/` folder with sample outputs.
- Setup references the datapack via the loader, not vendored JSON.
- Verify licensing is clean before submission.
