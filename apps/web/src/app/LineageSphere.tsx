"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const COUNT = 1700;
const R = 2.35;
const BLUE = new THREE.Color("#6f9ef6");
const AMBER = new THREE.Color("#e6ae5a");

/**
 * A Fibonacci-sphere constellation of lineage nodes. On load the points fly in
 * from a scattered cloud and assemble onto the sphere (easeOutCubic), the
 * surface shimmers, and an amber "drift" band sweeps across it (drift is not
 * always degradation, so it passes through). Rotates slowly and parallaxes to
 * the cursor. Additive-blended points for a luminous, no-texture glow.
 * Reduced-motion users get the assembled sphere, static (frameloop on demand).
 */
function Constellation({ reduced }: { reduced: boolean }) {
  const ref = useRef<THREE.Points>(null!);
  const started = useRef<number | null>(null);

  const { targets, scattered, positions, colors } = useMemo(() => {
    const targets = new Float32Array(COUNT * 3);
    const scattered = new Float32Array(COUNT * 3);
    const phi = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < COUNT; i++) {
      const ix = i * 3;
      const y = 1 - (i / (COUNT - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const theta = phi * i;
      targets[ix] = Math.cos(theta) * r * R;
      targets[ix + 1] = y * R;
      targets[ix + 2] = Math.sin(theta) * r * R;
      const sr = 7 + Math.random() * 7;
      const sTheta = Math.random() * Math.PI * 2;
      const sPhi = Math.acos(2 * Math.random() - 1);
      scattered[ix] = sr * Math.sin(sPhi) * Math.cos(sTheta);
      scattered[ix + 1] = sr * Math.sin(sPhi) * Math.sin(sTheta);
      scattered[ix + 2] = sr * Math.cos(sPhi);
    }
    // reduced-motion: render the assembled sphere from the first frame, no fly-in
    const positions = (reduced ? targets : scattered).slice();
    const colors = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) BLUE.toArray(colors, i * 3);
    return { targets, scattered, positions, colors };
  }, [reduced]);

  useFrame((state) => {
    if (reduced) return; // static assembled sphere; nothing to animate
    const g = ref.current.geometry;
    const pos = g.attributes.position.array as Float32Array;
    const col = g.attributes.color.array as Float32Array;
    const t = state.clock.elapsedTime;
    if (started.current === null) started.current = t;
    const a = Math.min(1, (t - started.current) / 2.4);
    const e = 1 - Math.pow(1 - a, 3);
    const front = -R + ((t * 0.16) % (2.5 * R));

    for (let i = 0; i < COUNT; i++) {
      const ix = i * 3;
      pos[ix] = scattered[ix] + (targets[ix] - scattered[ix]) * e + Math.sin(t * 1.4 + i) * 0.018;
      pos[ix + 1] = scattered[ix + 1] + (targets[ix + 1] - scattered[ix + 1]) * e + Math.cos(t * 1.2 + i) * 0.018;
      pos[ix + 2] = scattered[ix + 2] + (targets[ix + 2] - scattered[ix + 2]) * e + Math.sin(t * 1.1 + i * 1.3) * 0.018;
      const drifted = e > 0.85 && targets[ix + 1] < front && targets[ix + 1] > front - 0.6;
      if (drifted) AMBER.toArray(col, ix);
      else BLUE.toArray(col, ix);
    }
    g.attributes.position.needsUpdate = true;
    g.attributes.color.needsUpdate = true;
    ref.current.rotation.y = t * 0.05 + state.pointer.x * 0.35;
    ref.current.rotation.x = state.pointer.y * -0.2;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        sizeAttenuation
        vertexColors
        transparent
        opacity={0.92}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

export default function LineageSphere() {
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return (
    <Canvas
      camera={{ position: [0, 0, 7.2], fov: 45 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      dpr={[1, 2]}
      frameloop={reduced ? "demand" : "always"}
      style={{ position: "absolute", inset: 0 }}
    >
      <Constellation reduced={reduced} />
    </Canvas>
  );
}
