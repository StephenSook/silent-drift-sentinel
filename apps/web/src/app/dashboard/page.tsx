"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "motion/react";
import {
  fetchDrift,
  fetchLineage,
  fetchModelCard,
  useAgentRun,
  type Drift,
  type Lineage,
  type ModelCard,
  type Scenario,
} from "./lib";

const LineageGraph = dynamic(() => import("./LineageGraph"), { ssr: false });
const DriftChart = dynamic(() => import("./DriftChart"), { ssr: false });

function KindBadge({ kind }: { kind: string }) {
  const map: Record<string, string> = {
    alarm: "text-degraded border-degraded/40 bg-degraded-soft",
    tool_call: "text-accent border-accent/40 bg-accent-soft",
    tool_result: "text-healthy border-healthy/40 bg-healthy-soft",
    result: "text-muted border-border",
    thinking: "text-subtle border-border",
    info: "text-subtle border-border",
    blocked: "text-danger border-danger/40",
  };
  return (
    <span className={`rounded border px-1.5 py-0.5 font-mono text-[8px] tracking-widest ${map[kind] ?? "text-subtle border-border"}`}>
      {kind}
    </span>
  );
}

function PropRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-1 flex gap-2 text-[10px]">
      <span className="w-14 shrink-0 font-mono text-subtle">{label}</span>
      <span className="break-all font-mono text-fg">{value}</span>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return <div className="flex h-full items-center justify-center text-xs text-subtle">{label}</div>;
}

function Metric({ label, value }: { label: string; value?: number }) {
  return (
    <div>
      <div className="tnum font-display text-xl leading-none text-fg">{value?.toFixed(3) ?? "-"}</div>
      <div className="mt-1 font-mono text-[9px] tracking-widest text-subtle">{label}</div>
    </div>
  );
}

function CalRow({ label, raw, cal }: { label: string; raw?: number; cal?: number }) {
  return (
    <div className="mt-1.5 flex items-center gap-2 text-[10px]">
      <span className="w-9 font-mono text-subtle">{label}</span>
      <span className="tnum font-mono text-muted">{raw?.toFixed(3) ?? "-"}</span>
      <span className="text-subtle">to</span>
      <span className="tnum font-mono text-healthy">{cal?.toFixed(3) ?? "-"}</span>
      <span className="text-subtle">after isotonic calibration</span>
    </div>
  );
}

export default function Dashboard() {
  const { state, run, approve } = useAgentRun();
  const [scenario, setScenario] = useState<Scenario>("harmful");
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [drift, setDrift] = useState<Drift | null>(null);
  const [card, setCard] = useState<ModelCard | null>(null);

  useEffect(() => {
    fetchLineage(scenario).then(setLineage).catch(() => {});
    fetchDrift(scenario).then(setDrift).catch(() => {});
  }, [scenario]);

  useEffect(() => {
    fetchModelCard().then(setCard).catch(() => {});
  }, []);

  const revealed =
    state.trace.some((t) => t.node === "traverse" && t.kind === "tool_result") || !!state.writeback;
  const wb = state.writeback;
  const running = state.status === "running";
  const busy = running || state.status === "awaiting";
  const awaiting = state.status === "awaiting" && !!state.approval;

  return (
    <main className="flex h-screen flex-col overflow-hidden bg-bg">
      <header className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${scenario === "harmful" ? "bg-degraded" : "bg-healthy"}`} />
            <span className={`relative inline-flex h-2 w-2 rounded-full ${scenario === "harmful" ? "bg-degraded" : "bg-healthy"}`} />
          </span>
          <span className="font-mono text-xs tracking-[0.22em] text-muted">SILENT-DRIFT SENTINEL</span>
          <span className="font-mono text-[11px] text-subtle">/ online_shoppers_purchase_intent</span>
        </div>
        <div className="flex items-center gap-2">
          {/* scenario toggle: proof that drift is not always degradation */}
          <div className="mr-1 flex overflow-hidden rounded-md border border-border text-[11px] font-medium">
            <button
              onClick={() => setScenario("harmful")}
              disabled={busy}
              title="Upstream job zeroes out PageValues: the model degrades"
              className={`px-2.5 py-1.5 transition-colors disabled:opacity-40 ${scenario === "harmful" ? "bg-degraded-soft text-degraded" : "text-subtle hover:text-muted"}`}
            >
              Harmful bug
            </button>
            <button
              onClick={() => setScenario("benign")}
              disabled={busy}
              title="PageValues rescaled x100: big shift, model unaffected"
              className={`border-l border-border px-2.5 py-1.5 transition-colors disabled:opacity-40 ${scenario === "benign" ? "bg-healthy-soft text-healthy" : "text-subtle hover:text-muted"}`}
            >
              Benign bug
            </button>
          </div>
          {awaiting && (
            <button
              onClick={() => state.approval && approve(state.approval.thread_id)}
              className="animate-pulse rounded-md border border-degraded/60 bg-degraded-soft px-3 py-1.5 text-xs font-medium text-degraded transition-colors hover:bg-degraded/20"
            >
              Approve write-back
            </button>
          )}
          <button
            onClick={() => run(false, scenario)}
            disabled={busy}
            className="rounded-md border border-accent/40 bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {busy ? (awaiting ? "Awaiting approval" : "Running...") : "Run agent (live)"}
          </button>
          <button
            onClick={() => run(true, scenario)}
            disabled={busy}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-border-strong disabled:opacity-40"
          >
            Demo
          </button>
        </div>
      </header>

      <div className="grid flex-1 grid-cols-[320px_1fr_380px] overflow-hidden">
        {/* left: agent reasoning */}
        <section className="flex flex-col overflow-hidden border-r border-border">
          <div className="border-b border-border px-4 py-2 font-mono text-[10px] tracking-widest text-subtle">
            AGENT REASONING
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {state.trace.length === 0 && (
              <div className="text-xs leading-relaxed text-subtle">
                Run the agent to watch it detect the drift, walk DataHub lineage to the upstream
                table, reason about the cause, and write the finding back onto the model.
              </div>
            )}
            <AnimatePresence initial={false}>
              {state.trace.map((ev, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-md border border-border bg-surface-1 p-2.5"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[9px] tracking-widest text-subtle">
                      {ev.node.toUpperCase()}
                    </span>
                    <KindBadge kind={ev.kind} />
                  </div>
                  <div
                    className={`mt-1 text-xs leading-relaxed ${
                      ev.kind === "alarm"
                        ? "text-degraded"
                        : ev.node === "root_cause" && ev.kind === "result"
                          ? "font-mono text-[11px] text-muted"
                          : "text-fg"
                    }`}
                  >
                    {ev.message}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </section>

        {/* center: lineage */}
        <section className="relative overflow-hidden">
          {lineage ? <LineageGraph lineage={lineage} revealed={revealed} /> : <Empty label="loading lineage" />}
          <div className="pointer-events-none absolute left-4 top-3 font-mono text-[10px] tracking-widest text-subtle">
            DATAHUB ML LINEAGE
          </div>
        </section>

        {/* right: drift signal + model page reveal */}
        <section className="flex flex-col overflow-hidden border-l border-border">
          <div className="border-b border-border p-3">
            <div className="mb-2 font-mono text-[10px] tracking-widest text-subtle">DRIFT SIGNAL</div>
            {drift ? (
              <>
                <div className="mb-2 flex items-baseline gap-2">
                  <span className={`tnum font-display text-4xl leading-none ${scenario === "harmful" ? "text-degraded" : "text-healthy"}`}>
                    {drift.performance.estimated_current}
                  </span>
                  <span className="tnum text-[11px] text-subtle">
                    est. ROC-AUC, was {drift.performance.reference}
                    {scenario === "harmful" ? " (label-free)" : " (unchanged, label-free)"}
                  </span>
                </div>
                <div className="h-32">
                  <DriftChart drift={drift} />
                </div>
              </>
            ) : (
              <Empty label="loading drift" />
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            <div className="mb-2 font-mono text-[10px] tracking-widest text-subtle">
              MODEL PAGE (DataHub)
            </div>
            <div className="rounded-card border border-border bg-surface-1 p-3">
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-medium text-fg">purchase_intent</span>
                <AnimatePresence>
                  {wb && (
                    <motion.span
                      initial={{ scale: 0, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 400, damping: 20 }}
                      className="rounded-full border border-degraded/50 bg-degraded-soft px-2 py-0.5 text-[10px] font-medium text-degraded"
                    >
                      drift-degraded
                    </motion.span>
                  )}
                </AnimatePresence>
              </div>

              <AnimatePresence>
                {wb ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="mt-3 space-y-2"
                  >
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="rounded-md border border-degraded/30 bg-degraded-soft/40 p-2"
                    >
                      <div className="font-mono text-[9px] tracking-widest text-degraded">
                        DRIFT_CAUSATION
                      </div>
                      <PropRow label="feature" value={wb.causation.drifted_feature} />
                      <PropRow label="change" value={wb.causation.change_type} />
                      <PropRow label="impact" value={wb.causation.drift_metric} />
                      <PropRow label="owner" value={wb.causation.table_owner} />
                    </motion.div>
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.18 }}
                      className="rounded-md border border-accent/30 bg-accent-soft/40 p-2"
                    >
                      <div className="font-mono text-[9px] tracking-widest text-accent">
                        RCA DOC + INCIDENT + SLACK
                      </div>
                      <div className="mt-1 text-[11px] leading-relaxed text-muted">
                        Root-cause analysis attached to the model. An incident was raised on the
                        upstream web_sessions table, and the owning team was notified in Slack.
                      </div>
                    </motion.div>
                  </motion.div>
                ) : (
                  <div className="mt-3 text-xs text-subtle">
                    {scenario === "benign"
                      ? "Healthy. Benign drift evaluated and dismissed. Nothing written to the catalog."
                      : "Healthy. No drift-causation recorded yet."}
                  </div>
                )}
              </AnimatePresence>
            </div>

            {card?.reference && (
              <div className="mt-4">
                <div className="mb-2 font-mono text-[10px] tracking-widest text-subtle">MODEL CARD</div>
                <div className="space-y-2.5 rounded-card border border-border bg-surface-1 p-3">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <Metric label="ROC-AUC" value={card.reference.roc_auc} />
                    <Metric label="PR-AUC" value={card.reference.pr_auc} />
                    <Metric label="F1" value={card.reference["f1_at_0.5"]} />
                  </div>
                  <div className="border-t border-border pt-2">
                    <CalRow label="ECE" raw={card.reference.ece_raw} cal={card.reference.ece_calibrated} />
                    <CalRow label="Brier" raw={card.reference.brier_raw} cal={card.reference.brier_calibrated} />
                  </div>
                  <div className="border-t border-border pt-2 text-[10px] leading-relaxed text-subtle">
                    LightGBM, {card.n_features} features, best iteration {card.best_iteration}. Honest
                    temporal split: {card.split_sizes?.train_fit} train / {card.split_sizes?.calib} calib
                    / {card.split_sizes?.reference} reference / {card.split_sizes?.production} production.
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
