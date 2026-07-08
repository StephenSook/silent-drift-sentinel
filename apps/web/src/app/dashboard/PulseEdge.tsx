"use client";

import { BaseEdge, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

/**
 * A lineage edge that, when hot (root path + revealed), sends a pulse traveling
 * BACKWARD along the path, from the downstream (model) end toward the upstream
 * (source) end, the direction the agent actually reasons. keyPoints="1;0" reverses
 * the motion (edges point source=upstream -> target=downstream), and each edge is
 * delayed by its hop distance from the model so the pulse flows model -> feature ->
 * source table in order rather than every edge flashing at once.
 */
export default function PulseEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  data,
}: EdgeProps) {
  const [path] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 12,
  });
  const hot = Boolean(data?.hot);
  const delay = (data?.delay as number) ?? 0;
  const dur = (data?.dur as number) ?? 1.05;

  return (
    <>
      <BaseEdge path={path} style={style} markerEnd={markerEnd} />
      {hot && (
        <circle r={4.5} fill="var(--color-degraded)" style={{ filter: "drop-shadow(0 0 6px var(--color-degraded))" }}>
          <animateMotion
            dur={`${dur}s`}
            begin={`${delay}s`}
            repeatCount="indefinite"
            calcMode="linear"
            keyPoints="1;0"
            keyTimes="0;1"
            path={path}
          />
        </circle>
      )}
    </>
  );
}
