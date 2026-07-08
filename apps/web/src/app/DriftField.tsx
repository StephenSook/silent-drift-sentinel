"use client";

import { useEffect, useRef } from "react";

/**
 * Animated hero backdrop: a loose constellation of nodes that slowly drift from
 * their origin while faint lines connect near neighbors (a lineage graph feel).
 * A degradation front sweeps left to right, tipping the nodes it passes to amber.
 * Light (2D canvas), pauses when off-screen, and honors reduced-motion.
 */
export default function DriftField() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    let raf = 0;
    let running = true;

    type Node = { ox: number; oy: number; x: number; y: number; ax: number; ay: number; sp: number; drift: number };
    const nodes: Node[] = [];

    const seed = () => {
      nodes.length = 0;
      const cols = Math.max(6, Math.round(w / 130));
      const rows = Math.max(4, Math.round(h / 130));
      const gx = w / (cols + 1);
      const gy = h / (rows + 1);
      let i = 0;
      for (let r = 1; r <= rows; r++) {
        for (let c = 1; c <= cols; c++) {
          // deterministic jitter (no Math.random dependency for SSR stability)
          const j = Math.sin(i * 12.9898) * 43758.5453;
          const jx = ((j - Math.floor(j)) - 0.5) * gx * 0.7;
          const k = Math.sin(i * 78.233) * 43758.5453;
          const jy = ((k - Math.floor(k)) - 0.5) * gy * 0.7;
          const ox = c * gx + jx;
          const oy = r * gy + jy;
          nodes.push({
            ox, oy, x: ox, y: oy,
            ax: 8 + ((j - Math.floor(j)) * 14),
            ay: 6 + ((k - Math.floor(k)) * 12),
            sp: 0.15 + (j - Math.floor(j)) * 0.35,
            drift: i * 0.7,
          });
          i++;
        }
      }
    }

    const resize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    }

    const ACCENT = "112, 158, 246"; // electric blue rgb
    const AMBER = "230, 174, 90"; // degradation amber rgb

    const render = (time: number) => {
      const t = time / 1000;
      ctx.clearRect(0, 0, w, h);
      // degradation front position (sweeps slowly across, then wraps)
      const front = ((t * 0.05) % 1.4 - 0.2) * w;

      for (const n of nodes) {
        n.x = n.ox + Math.sin(t * n.sp + n.drift) * n.ax;
        n.y = n.oy + Math.cos(t * n.sp * 0.8 + n.drift) * n.ay;
      }

      // connecting lines
      const maxD = 150;
      for (let a = 0; a < nodes.length; a++) {
        for (let b = a + 1; b < nodes.length; b++) {
          const dx = nodes[a].x - nodes[b].x;
          const dy = nodes[a].y - nodes[b].y;
          const d2 = dx * dx + dy * dy;
          if (d2 > maxD * maxD) continue;
          const alpha = (1 - Math.sqrt(d2) / maxD) * 0.16;
          ctx.strokeStyle = `rgba(${ACCENT}, ${alpha})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(nodes[a].x, nodes[a].y);
          ctx.lineTo(nodes[b].x, nodes[b].y);
          ctx.stroke();
        }
      }

      // nodes
      for (const n of nodes) {
        const degraded = n.x < front;
        const rgb = degraded ? AMBER : ACCENT;
        const glow = degraded ? 0.9 : 0.5;
        ctx.beginPath();
        ctx.arc(n.x, n.y, degraded ? 2.4 : 1.7, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb}, ${glow})`;
        ctx.shadowColor = `rgba(${rgb}, ${glow})`;
        ctx.shadowBlur = degraded ? 12 : 5;
        ctx.fill();
      }
      ctx.shadowBlur = 0;

      if (running && !reduce) raf = requestAnimationFrame(render);
    }

    resize();
    window.addEventListener("resize", resize);

    if (reduce) {
      render(0);
    } else {
      raf = requestAnimationFrame(render);
    }

    // pause when the hero scrolls out of view
    const io = new IntersectionObserver(
      ([e]) => {
        running = e.isIntersecting;
        if (running && !reduce) raf = requestAnimationFrame(render);
        else cancelAnimationFrame(raf);
      },
      { threshold: 0 },
    );
    io.observe(canvas);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      io.disconnect();
    };
  }, []);

  return <canvas ref={ref} className="absolute inset-0 h-full w-full" aria-hidden="true" />;
}
