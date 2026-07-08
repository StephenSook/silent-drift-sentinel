"use client";

import { useEffect, useState } from "react";
import {
  Background,
  Controls,
  type Edge,
  MarkerType,
  type Node,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import ELK from "elkjs/lib/elk.bundled.js";
import PulseEdge from "./PulseEdge";
import type { Lineage, LineageNode } from "./lib";

const elk = new ELK();

const KIND: Record<LineageNode["kind"], { accent: string; glyph: string }> = {
  dataset: { accent: "var(--color-muted)", glyph: "TABLE" },
  feature: { accent: "var(--color-accent)", glyph: "FEATURE" },
  model: { accent: "var(--color-degraded)", glyph: "MODEL" },
  deployment: { accent: "var(--color-healthy)", glyph: "DEPLOY" },
};
const RING: Record<LineageNode["status"], string> = {
  degraded: "var(--color-degraded)",
  drifted: "var(--color-degraded)",
  changed: "var(--color-danger)",
  ok: "transparent",
};

function EntityNode({ data }: { data: LineageNode }) {
  const k = KIND[data.kind];
  const ring = RING[data.status];
  const active = ring !== "transparent";
  return (
    <div
      className="rounded-card border bg-surface-1 px-3 py-2"
      style={{
        width: 168,
        borderColor: active ? ring : "var(--color-border)",
        boxShadow: active ? `0 0 0 1px ${ring}, 0 0 26px -8px ${ring}` : "none",
      }}
    >
      <div className="font-mono text-[9px] tracking-[0.18em]" style={{ color: k.accent }}>
        {k.glyph}
      </div>
      <div className="mt-0.5 truncate font-mono text-[13px] font-medium text-fg">{data.label}</div>
      {data.status !== "ok" && (
        <div className="mt-1 text-[9px] uppercase tracking-wide" style={{ color: ring }}>
          {data.status}
        </div>
      )}
      {data.owner && (
        <div className="mt-1 truncate font-mono text-[9px] text-subtle">{data.owner}</div>
      )}
    </div>
  );
}

const nodeTypes = { entity: EntityNode };
const edgeTypes = { pulse: PulseEdge };

export default function LineageGraph({
  lineage,
  revealed,
}: {
  lineage: Lineage;
  revealed: boolean;
}) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  useEffect(() => {
    const graph = {
      id: "root",
      layoutOptions: {
        "elk.algorithm": "layered",
        "elk.direction": "RIGHT",
        "elk.spacing.nodeNode": "30",
        "elk.layered.spacing.nodeNodeBetweenLayers": "96",
      },
      children: lineage.nodes.map((n) => ({ id: n.id, width: 168, height: 66 })),
      edges: lineage.edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
    };
    let cancelled = false;
    elk.layout(graph).then((res) => {
      if (cancelled) return;
      setNodes(
        (res.children ?? []).map((c) => {
          const n = lineage.nodes.find((x) => x.id === c.id)!;
          return { id: c.id, type: "entity", position: { x: c.x ?? 0, y: c.y ?? 0 }, data: n };
        }),
      );
      // hop distance from the model along the root path, so the backward pulse is
      // staggered (model -> feature fires first, then feature -> source table)
      const modelId = lineage.nodes.find((n) => n.kind === "model")?.id;
      const rootAdj: Record<string, string[]> = {};
      lineage.edges
        .filter((e) => e.root)
        .forEach((e) => {
          (rootAdj[e.source] ??= []).push(e.target);
          (rootAdj[e.target] ??= []).push(e.source);
        });
      const dist: Record<string, number> = {};
      if (modelId) {
        dist[modelId] = 0;
        const queue = [modelId];
        while (queue.length) {
          const cur = queue.shift()!;
          for (const nb of rootAdj[cur] ?? []) {
            if (dist[nb] === undefined) {
              dist[nb] = dist[cur] + 1;
              queue.push(nb);
            }
          }
        }
      }
      const DUR = 1.05;
      setEdges(
        lineage.edges.map((e) => {
          const hot = e.root && revealed;
          const color = hot ? "var(--color-degraded)" : "var(--color-border-strong)";
          return {
            id: e.id,
            source: e.source,
            target: e.target,
            type: "pulse",
            data: { hot, delay: (dist[e.target] ?? 0) * DUR, dur: DUR },
            style: { stroke: color, strokeWidth: hot ? 2 : 1 },
            markerEnd: { type: MarkerType.ArrowClosed, color },
          };
        }),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [lineage, revealed]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      minZoom={0.3}
      colorMode="dark"
    >
      <Background color="oklch(0.45 0.01 264 / 0.18)" gap={22} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
