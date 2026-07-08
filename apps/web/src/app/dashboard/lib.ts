"use client";

import { useCallback, useRef, useState } from "react";

export const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8130";

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

export type Scenario = "harmful" | "benign";

export async function fetchLineage(scenario: Scenario = "harmful"): Promise<Lineage> {
  const r = await fetch(`${AGENT_URL}/api/lineage?scenario=${scenario}`);
  return r.json();
}
export async function fetchDrift(scenario: Scenario = "harmful"): Promise<Drift> {
  const r = await fetch(`${AGENT_URL}/api/drift?scenario=${scenario}`);
  return r.json();
}

export type Approval = { thread_id: string; causation: Record<string, string> };

export type RunState = {
  status: "idle" | "running" | "awaiting" | "done";
  trace: TraceEvent[];
  writeback?: WriteBack;
  activeNode?: string;
  approval?: Approval;
  demo?: boolean;
};

export function useAgentRun() {
  const [state, setState] = useState<RunState>({ status: "idle", trace: [] });
  const esRef = useRef<EventSource | null>(null);

  const run = useCallback((demo: boolean, scenario: Scenario = "harmful") => {
    esRef.current?.close();
    setState({ status: "running", trace: [], demo });
    const es = new EventSource(`${AGENT_URL}/api/stream?demo_mode=${demo}&scenario=${scenario}`);
    esRef.current = es;

    es.addEventListener("trace", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as TraceEvent;
      setState((s) => ({ ...s, trace: [...s.trace, ev], activeNode: ev.node }));
    });
    es.addEventListener("awaiting_approval", (e) => {
      const a = JSON.parse((e as MessageEvent).data) as Approval;
      // the demo replay auto-proceeds; a live run waits for the human
      setState((s) => ({ ...s, approval: a, status: s.demo ? "running" : "awaiting" }));
    });
    es.addEventListener("writeback", (e) => {
      const wb = JSON.parse((e as MessageEvent).data) as WriteBack;
      setState((s) => ({ ...s, writeback: wb }));
    });
    es.addEventListener("done", () => {
      setState((s) => ({ ...s, status: "done", activeNode: undefined }));
      es.close();
    });
    es.onerror = () => {
      es.close();
      // a live run closes the stream at the approval gate; preserve that state
      setState((s) => (s.status === "running" ? { ...s, status: "done" } : s));
    };
  }, []);

  const approve = useCallback(async (threadId: string) => {
    setState((s) => ({ ...s, status: "running", approval: undefined }));
    const r = await fetch(`${AGENT_URL}/api/approve?thread_id=${threadId}`, { method: "POST" });
    const data = (await r.json()) as { trace?: TraceEvent[]; writeback?: WriteBack };
    setState((s) => ({
      ...s,
      trace: [...s.trace, ...(data.trace ?? [])],
      writeback: data.writeback ?? s.writeback,
      status: "done",
    }));
  }, []);

  return { state, run, approve };
}
