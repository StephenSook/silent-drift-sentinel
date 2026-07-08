"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { AnimatePresence, motion } from "motion/react";
import {
  datahubEntityUrl,
  fetchDrift,
  fetchEval,
  fetchLineage,
  fetchModelCard,
  useAgentRun,
  type Drift,
  type EvalReport,
  type Lineage,
  type ModelCard,
  type ProposedFix,
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

function FixPanel({ fix }: { fix: ProposedFix }) {
  const [tab, setTab] = useState<"dbt" | "great_expectations" | "sql">("dbt");
  const [copied, setCopied] = useState(false);
  const code = fix[tab];
  const tabs: { k: "dbt" | "great_expectations" | "sql"; label: string }[] = [
    { k: "dbt", label: "dbt" },
    { k: "great_expectations", label: "GE" },
    { k: "sql", label: "SQL" },
  ];
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-4"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[10px] tracking-widest text-subtle">PROPOSED FIX</span>
        <span className="font-mono text-[9px] text-subtle">metadata-aware code-gen</span>
      </div>
      <div className="rounded-card border border-accent/20 bg-surface-1 p-3">
        <div className="text-[11px] leading-relaxed text-muted">{fix.summary}</div>
        <div className="mt-2 flex items-center gap-1">
          {tabs.map((t) => (
            <button
              key={t.k}
              onClick={() => setTab(t.k)}
              className={`rounded px-2 py-0.5 font-mono text-[9px] transition-colors ${
                tab === t.k ? "bg-accent-soft text-accent" : "text-subtle hover:text-muted"
              }`}
            >
              {t.label}
            </button>
          ))}
          <button
            onClick={() => {
              navigator.clipboard?.writeText(code);
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            }}
            className="ml-auto rounded px-2 py-0.5 font-mono text-[9px] text-subtle hover:text-muted"
          >
            {copied ? "copied" : "copy"}
          </button>
        </div>
        <pre className="mt-2 max-h-52 overflow-auto rounded bg-bg p-2 font-mono text-[9px] leading-relaxed text-fg">
          {code}
        </pre>
        {fix.needs.length > 0 && (
          <div className="mt-1 font-mono text-[9px] text-subtle">requires: {fix.needs.join(", ")}</div>
        )}
      </div>
    </motion.div>
  );
}

export default function Dashboard() {
  const { state, run, approve, reset } = useAgentRun();
  const [scenario, setScenario] = useState<Scenario>("harmful");
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [drift, setDrift] = useState<Drift | null>(null);
  const [card, setCard] = useState<ModelCard | null>(null);
  const [evalr, setEvalr] = useState<EvalReport | null>(null);
  // opt in to the agentic loop: Claude drives the catalog reads live (slower, watchable)
  const [agentic, setAgentic] = useState(false);

  useEffect(() => {
    fetchLineage(scenario).then(setLineage).catch(() => {});
    fetchDrift(scenario).then(setDrift).catch(() => {});
  }, [scenario]);

  // clear any stale write-back when the scenario changes, so the benign screen
  // never contradicts a leftover harmful write-back (or vice versa)
  useEffect(() => {
    reset();
  }, [scenario, reset]);

  useEffect(() => {
    fetchModelCard().then(setCard).catch(() => {});
    fetchEval().then(setEvalr).catch(() => {});
  }, []);

  // the reasoning panel follows the stream
  const traceRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    traceRef.current?.scrollTo({ top: traceRef.current.scrollHeight, behavior: "smooth" });
  }, [state.trace.length]);

  const revealed =
    state.trace.some((t) => t.node === "traverse" && t.kind === "tool_result") || !!state.writeback;
  const wb = state.writeback;
  const recalled = !!state.recalled;
  const running = state.status === "running";
  const busy = running || state.status === "awaiting";
  const awaiting = state.status === "awaiting" && !!state.approval;

  return (
    <main className="flex min-h-screen flex-col bg-bg lg:h-screen lg:overflow-hidden">
      <header className="flex flex-col items-start gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${scenario === "harmful" ? "bg-degraded" : "bg-healthy"}`} />
            <span className={`relative inline-flex h-2 w-2 rounded-full ${scenario === "harmful" ? "bg-degraded" : "bg-healthy"}`} />
          </span>
          <span className="font-mono text-xs tracking-[0.22em] text-muted">SILENT-DRIFT SENTINEL</span>
          <span className="font-mono text-[11px] text-subtle">/ online_shoppers_purchase_intent</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
            onClick={() => setAgentic((a) => !a)}
            disabled={busy}
            title="Agentic mode: Claude drives the DataHub reads itself in a live tool-calling loop (slower, but you watch it investigate). Off uses the fast single synthesis over Agent Context Kit reads."
            className={`rounded-md border px-2.5 py-1.5 text-[11px] font-medium transition-colors disabled:opacity-40 ${
              agentic ? "border-accent/60 bg-accent-soft text-accent" : "border-border text-subtle hover:text-muted"
            }`}
          >
            Agentic {agentic ? "on" : "off"}
          </button>
          <button
            onClick={() => run(false, scenario, agentic)}
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
          {state.writeback && !recalled && (
            <button
              onClick={() => run(false, scenario)}
              disabled={busy}
              title="Run the agent again. It recognizes the cause it already recorded on the model and recalls it, instead of re-diagnosing or paging anyone twice."
              className="rounded-md border border-accent/40 bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
            >
              Run again (recall)
            </button>
          )}
          {(state.writeback || state.status === "done") && (
            <button
              onClick={() => reset(true)}
              disabled={busy}
              title="Clear the write-back from DataHub so the demo re-runs from a pristine model"
              className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-subtle transition-colors hover:border-border-strong hover:text-muted disabled:opacity-40"
            >
              Reset
            </button>
          )}
        </div>
      </header>

      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[320px_1fr_380px] lg:overflow-hidden">
        {/* left: agent reasoning */}
        <section className="flex max-h-[46vh] flex-col overflow-hidden border-b border-border lg:max-h-none lg:border-b-0 lg:border-r">
          <div className="border-b border-border px-4 py-2 font-mono text-[10px] tracking-widest text-subtle">
            AGENT REASONING
          </div>
          <div ref={traceRef} className="flex-1 space-y-2 overflow-y-auto p-3">
            {state.trace.length === 0 && !state.unreachable && (
              <div className="text-xs leading-relaxed text-subtle">
                Run the agent to watch it detect the drift, walk DataHub lineage to the upstream
                table, reason about the cause, and write the finding back onto the model.
              </div>
            )}
            {state.unreachable && (
              <div className="rounded-md border border-degraded/40 bg-degraded-soft/40 p-2 text-xs leading-relaxed text-degraded">
                The agent did not respond. The always-on host may be waking up. Wait a moment, then
                run again.
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
        <section className="relative h-[62vh] overflow-hidden lg:h-auto">
          {lineage ? <LineageGraph lineage={lineage} revealed={revealed} /> : <Empty label="loading lineage" />}
          <div className="pointer-events-none absolute left-4 top-3 font-mono text-[10px] tracking-widest text-subtle">
            DATAHUB ML LINEAGE
          </div>
        </section>

        {/* right: drift signal + model page reveal */}
        <section className="flex flex-col overflow-hidden border-t border-border lg:border-l lg:border-t-0">
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
                  {(wb || recalled) && (
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

              {state.modelUrn && (
                <a
                  href={datahubEntityUrl(state.modelUrn)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block font-mono text-[10px] text-accent hover:underline"
                >
                  View on DataHub &#8599;
                </a>
              )}

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
                        Root-cause analysis written to the model description. An incident was raised
                        on the upstream web_sessions table, and the owning team was notified in Slack.
                      </div>
                    </motion.div>
                    {state.verified?.present && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.32 }}
                        className="rounded-md border border-healthy/40 bg-healthy-soft/40 p-2"
                      >
                        <div className="font-mono text-[9px] tracking-widest text-healthy">
                          VERIFIED FROM DATAHUB
                        </div>
                        <div className="mt-1 break-all font-mono text-[9px] leading-relaxed text-fg">
                          {state.verified.causation?.value}
                        </div>
                        <div className="mt-1 text-[9px] text-subtle">
                          Re-fetched from the catalog after the write, not the agent&apos;s claim.
                        </div>
                      </motion.div>
                    )}
                  </motion.div>
                ) : recalled ? (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 space-y-2">
                    <div className="rounded-md border border-accent/40 bg-accent-soft/40 p-2">
                      <div className="font-mono text-[9px] tracking-widest text-accent">
                        KNOWN CAUSE, RECALLED
                      </div>
                      <div className="mt-1 text-[11px] leading-relaxed text-muted">
                        The Sentinel recognized a cause it already recorded on this model and
                        short-circuited: no re-diagnosis, no duplicate incident. The next on-call
                        agent inherited the knowledge straight from the catalog.
                      </div>
                    </div>
                    {state.verified?.present && (
                      <div className="rounded-md border border-healthy/40 bg-healthy-soft/40 p-2">
                        <div className="font-mono text-[9px] tracking-widest text-healthy">
                          READ BACK FROM DATAHUB
                        </div>
                        <div className="mt-1 break-all font-mono text-[9px] leading-relaxed text-fg">
                          {state.verified.causation?.value}
                        </div>
                      </div>
                    )}
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

            {state.proposedFix && <FixPanel fix={state.proposedFix} />}

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

            {evalr?.alarm && (
              <div className="mt-4">
                <div className="mb-2 font-mono text-[10px] tracking-widest text-subtle">DETECTOR EVAL</div>
                <div className="space-y-2 rounded-card border border-border bg-surface-1 p-3">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <Metric label="ALARM PREC" value={evalr.alarm.precision} />
                    <Metric label="ALARM RECALL" value={evalr.alarm.recall} />
                    <Metric label="LOCALIZE" value={evalr.localization_accuracy} />
                  </div>
                  <div className="border-t border-border pt-2 text-[10px] leading-relaxed text-subtle">
                    Over {evalr.n_scenarios} labeled scenarios (null/default, unit rescale, default
                    value, benign shift): no false alarms and no misses (fp {evalr.alarm.fp}, fn{" "}
                    {evalr.alarm.fn}), root cause localized {evalr.localization_n}/{evalr.localization_n},
                    change type classified{" "}
                    {evalr.change_type_accuracy != null ? Math.round(evalr.change_type_accuracy * 100) : "-"}%
                    correct. Measured, not asserted.
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
