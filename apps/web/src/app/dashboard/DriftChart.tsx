"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { Drift } from "./lib";

export default function DriftChart({ drift }: { drift: Drift }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el, undefined, { renderer: "canvas" });
    const cats = drift.bins.slice(0, -1).map((b) => String(b));
    chart.setOption({
      grid: { top: 26, left: 34, right: 10, bottom: 20 },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: {
        top: 0,
        right: 0,
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { color: "oklch(0.72 0.012 264)", fontSize: 10 },
        data: ["reference", "production"],
      },
      xAxis: {
        type: "category",
        data: cats,
        axisLabel: { color: "oklch(0.56 0.012 264)", fontSize: 8, interval: 4 },
        axisLine: { lineStyle: { color: "oklch(0.45 0.01 264 / 0.3)" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "oklch(0.56 0.012 264)", fontSize: 8 },
        splitLine: { lineStyle: { color: "oklch(1 0 0 / 0.05)" } },
      },
      series: [
        {
          name: "reference",
          type: "bar",
          data: drift.reference_hist,
          itemStyle: { color: "oklch(0.7 0.16 253 / 0.55)" },
          barGap: "-100%",
          barCategoryGap: "20%",
        },
        {
          name: "production",
          type: "bar",
          data: drift.production_hist,
          itemStyle: { color: "oklch(0.8 0.15 76 / 0.85)" },
          barCategoryGap: "20%",
        },
      ],
    });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [drift]);

  return <div ref={ref} className="h-full w-full" />;
}
