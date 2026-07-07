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

export async function fetchLineage(): Promise<Lineage> {
  const r = await fetch(`${AGENT_URL}/api/lineage`);
  return r.json();
}
export async function fetchDrift(): Promise<Drift> {
  const r = await fetch(`${AGENT_URL}/api/drift`);
  return r.json();
}

export type RunState = {
  status: "idle" | "running" | "done";
  trace: TraceEvent[];
  writeback?: WriteBack;
  activeNode?: string;
};

export function useAgentRun() {
  const [state, setState] = useState<RunState>({ status: "idle", trace: [] });
  const esRef = useRef<EventSource | null>(null);

  const run = useCallback((demo: boolean) => {
    esRef.current?.close();
    setState({ status: "running", trace: [] });
    const es = new EventSource(`${AGENT_URL}/api/stream?demo_mode=${demo}`);
    esRef.current = es;

    es.addEventListener("trace", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as TraceEvent;
      setState((s) => ({ ...s, trace: [...s.trace, ev], activeNode: ev.node }));
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
      setState((s) => ({ ...s, status: "done" }));
    };
  }, []);

  return { state, run };
}
