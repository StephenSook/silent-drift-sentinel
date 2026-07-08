"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8130";
export const DATAHUB_URL =
  process.env.NEXT_PUBLIC_DATAHUB_URL ?? "https://datahub.16-59-185-192.nip.io";

// DataHub v1.5 routes entity pages by type; the old /entity/<urn> path returns the
// app's own 404. An mlModel lives at /mlModels/<urn>, a dataset at /dataset/<urn>,
// and so on. The urn is used raw in the path (the browser encodes it on navigation).
const DATAHUB_ENTITY_PATH: Record<string, string> = {
  mlModel: "mlModels",
  mlModelGroup: "mlModelGroup",
  mlFeature: "mlFeatures",
  mlFeatureTable: "mlFeatureTables",
  dataset: "dataset",
  corpuser: "user",
  corpGroup: "group",
};

/** Deep-link to the real DataHub entity page for a URN, routed by entity type. */
export function datahubEntityUrl(urn: string): string {
  const type = urn.match(/^urn:li:(\w+):/)?.[1] ?? "";
  const path = DATAHUB_ENTITY_PATH[type];
  return path ? `${DATAHUB_URL}/${path}/${urn}` : `${DATAHUB_URL}/search?query=${encodeURIComponent(urn)}`;
}

export type TraceEvent = { node: string; kind: string; message: string };

export type LineageNode = {
  id: string;
  kind: "model" | "feature" | "dataset" | "deployment";
  label: string;
  status: "degraded" | "drifted" | "changed" | "ok";
  owner?: string;
  metrics?: Record<string, string>;
};
export type LineageEdge = { id: string; source: string; target: string; root: boolean };
export type Lineage = { nodes: LineageNode[]; edges: LineageEdge[]; drifted_feature: string };

export type Performance = {
  metric: string;
  reference: number;
  estimated_current: number;
  estimated_drop: number;
};
export type Drift = {
  feature: string;
  bins: number[];
  reference_hist: number[];
  production_hist: number[];
  performance: Performance;
};

export type WriteBack = {
  causation: Record<string, string>;
  result: Record<string, { status: string; result?: string }>;
};

/** The data-quality guardrail the agent generated from the diagnosis (metadata-aware
 * code-gen): a paste-ready dbt test, Great Expectations expectation, and SQL guard. */
export type ProposedFix = {
  change_type: string;
  column: string;
  table: string;
  summary: string;
  dbt: string;
  great_expectations: string;
  sql: string;
  needs: string[];
};

export type Scenario = "harmful" | "benign" | "default";

export async function fetchLineage(scenario: Scenario = "harmful"): Promise<Lineage> {
  const r = await fetch(`${AGENT_URL}/api/lineage?scenario=${scenario}`);
  return r.json();
}
export async function fetchDrift(scenario: Scenario = "harmful"): Promise<Drift> {
  const r = await fetch(`${AGENT_URL}/api/drift?scenario=${scenario}`);
  return r.json();
}

export type ModelCard = {
  reference?: Record<string, number>;
  split_sizes?: Record<string, number>;
  n_features?: number;
  best_iteration?: number;
};
export async function fetchModelCard(): Promise<ModelCard> {
  const r = await fetch(`${AGENT_URL}/api/model-card`);
  return r.json();
}

/** The detector's evaluation over a labeled scenario suite: proof the root-cause
 * localization is measured, not just asserted. */
export type EvalReport = {
  n_scenarios?: number;
  alarm?: { precision: number; recall: number; accuracy: number; tp: number; fp: number; tn: number; fn: number };
  localization_accuracy?: number;
  localization_n?: number;
  change_type_accuracy?: number;
  change_type_n?: number;
};
export async function fetchEval(): Promise<EvalReport> {
  const r = await fetch(`${AGENT_URL}/api/eval`);
  return r.json();
}

/** The drift_causation property re-fetched FROM DataHub: proof the write-back
 * landed on the real catalog, not just what the agent claimed. */
export type CatalogProof = {
  present: boolean;
  causation?: { property_urn: string; value: string; tag_present: boolean; source: string };
};
export async function verifyCatalog(): Promise<CatalogProof> {
  const r = await fetch(`${AGENT_URL}/api/verify`);
  if (!r.ok) throw new Error(`verify ${r.status}`);
  return r.json();
}

/** Return the model to a pristine state so the live demo re-runs cleanly. */
export async function resetDemo(): Promise<void> {
  await fetch(`${AGENT_URL}/api/reset`, { method: "POST" });
}

export type Approval = {
  thread_id: string;
  causation: Record<string, string>;
  proposed_fix?: ProposedFix;
};

export type RunState = {
  status: "idle" | "running" | "awaiting" | "done";
  trace: TraceEvent[];
  writeback?: WriteBack;
  activeNode?: string;
  approval?: Approval;
  demo?: boolean;
  modelUrn?: string;
  verified?: CatalogProof;
  unreachable?: boolean;
  proposedFix?: ProposedFix;
  // close-the-loop: this run recognized a cause the agent already recorded and
  // short-circuited (no re-diagnosis, no duplicate write)
  recalled?: boolean;
};

export function useAgentRun() {
  const [state, setState] = useState<RunState>({ status: "idle", trace: [] });
  const esRef = useRef<EventSource | null>(null);

  const run = useCallback((demo: boolean, scenario: Scenario = "harmful", agentic = false) => {
    esRef.current?.close();
    setState({ status: "running", trace: [], demo });
    const es = new EventSource(
      `${AGENT_URL}/api/stream?demo_mode=${demo}&scenario=${scenario}&agentic=${agentic}`,
    );
    esRef.current = es;

    es.addEventListener("start", (e) => {
      const d = JSON.parse((e as MessageEvent).data) as { model_urn?: string };
      setState((s) => ({ ...s, modelUrn: d.model_urn }));
    });
    es.addEventListener("trace", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as TraceEvent;
      setState((s) => ({ ...s, trace: [...s.trace, ev], activeNode: ev.node }));
    });
    es.addEventListener("awaiting_approval", (e) => {
      const a = JSON.parse((e as MessageEvent).data) as Approval;
      // the demo replay auto-proceeds; a live run waits for the human
      setState((s) => ({
        ...s,
        approval: a,
        proposedFix: a.proposed_fix ?? s.proposedFix,
        status: s.demo ? "running" : "awaiting",
      }));
    });
    es.addEventListener("writeback", (e) => {
      const wb = JSON.parse((e as MessageEvent).data) as WriteBack;
      setState((s) => ({ ...s, writeback: wb }));
    });
    es.addEventListener("done", () => {
      setState((s) => ({
        ...s,
        status: "done",
        activeNode: undefined,
        recalled: s.trace.some((t) => t.node === "recall"),
      }));
      es.close();
    });
    es.onerror = () => {
      es.close();
      setState((s) => {
        // no trace at all means the agent is unreachable (cold VM / down), not a
        // normal at-gate close; surface it instead of spinning forever
        if (s.status === "running" && s.trace.length === 0) {
          return { ...s, status: "idle", unreachable: true };
        }
        // a live run closes the stream at the approval gate; preserve that state
        return s.status === "running" ? { ...s, status: "done" } : s;
      });
    };
  }, []);

  const approve = useCallback(async (threadId: string) => {
    // keep `approval` set during the POST so a failure can drop back to the gate
    setState((s) => ({ ...s, status: "running" }));
    try {
      const r = await fetch(`${AGENT_URL}/api/approve?thread_id=${threadId}`, { method: "POST" });
      if (!r.ok) throw new Error(`approve ${r.status}`);
      const data = (await r.json()) as { trace?: TraceEvent[]; writeback?: WriteBack };
      setState((s) => ({
        ...s,
        approval: undefined,
        trace: [...s.trace, ...(data.trace ?? [])],
        writeback: data.writeback ?? s.writeback,
        status: "done",
      }));
      // re-fetch the property FROM DataHub as independent proof it landed
      const proof = await verifyCatalog().catch(() => undefined);
      if (proof) setState((s) => ({ ...s, verified: proof }));
    } catch {
      // a failed approval must not hang the UI on "Running..."; return to the gate so
      // the human can retry (the approval is still in state)
      setState((s) => ({ ...s, status: "awaiting" }));
    }
  }, []);

  // reset run state (used on scenario toggle and the Reset-demo button); when
  // clearCatalog, also wipe the write-back from DataHub so a re-run re-animates.
  const reset = useCallback((clearCatalog = false) => {
    esRef.current?.close();
    setState({ status: "idle", trace: [] });
    if (clearCatalog) resetDemo().catch(() => {});
  }, []);

  // close any open SSE stream when the dashboard unmounts, so an in-flight run does
  // not leak the connection or setState on an unmounted component
  useEffect(() => () => esRef.current?.close(), []);

  // when a run recalled a recorded cause, re-fetch the property FROM DataHub so the
  // model-page panel can show the exact value the agent read back (proof, not claim)
  useEffect(() => {
    if (state.status === "done" && state.recalled && !state.verified) {
      verifyCatalog()
        .then((proof) => setState((s) => ({ ...s, verified: proof })))
        .catch(() => {});
    }
  }, [state.status, state.recalled, state.verified]);

  return { state, run, approve, reset };
}
