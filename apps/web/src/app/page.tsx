"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import DriftField from "./DriftField";

const REPO = "https://github.com/StephenSook/silent-drift-sentinel";

const PIPELINE = [
  { step: "01", name: "Detect", note: "Label-free performance estimation (NannyML CBPE) flags a drop before any ground-truth labels arrive." },
  { step: "02", name: "Traverse", note: "The agent walks DataHub ML lineage through the Agent Context Kit, model to features to the source table." },
  { step: "03", name: "Root-Cause", note: "Per-feature drift with FDR correction plus data-quality evidence localizes the exact upstream column that changed." },
  { step: "04", name: "Identify Owner", note: "The owning team is read straight from catalog metadata on the upstream dataset." },
  { step: "05", name: "Write-Back", note: "A typed drift_causation object lands on the model, and an incident lands on the upstream table." },
];

const ARCHITECTURE = [
  { k: "Agent", v: "LangGraph five-node state machine. Claude writes the narrative; deterministic code executes every DataHub write behind a write-ahead log." },
  { k: "ML core", v: "Calibrated LightGBM on real UCI Online Shoppers data. CBPE for label-free performance, KS and Chi-squared drift with Benjamini-Hochberg correction." },
  { k: "Catalog", v: "Self-hosted open-source DataHub. Reads through the Agent Context Kit, writes via structured properties, documents, and incidents." },
  { k: "Surface", v: "Next.js and React Flow, streamed over SSE. Every step you see is the agent running, not a recording." },
];

function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function Label({ children }: { children: ReactNode }) {
  return <div className="mb-4 font-mono text-[11px] uppercase tracking-[0.28em] text-subtle">{children}</div>;
}

export default function Home() {
  return (
    <main className="relative flex flex-col bg-bg">
      {/* ---- hero ---- */}
      <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 py-24">
        <DriftField />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(70% 55% at 50% 32%, transparent, oklch(0.16 0.006 264 / 0.85) 78%, var(--color-bg) 100%)" }}
        />
        <div className="relative z-10 flex w-full max-w-3xl flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mb-8 flex items-center gap-2 rounded-full border border-border bg-surface-1/70 px-3 py-1 font-mono text-[11px] tracking-[0.18em] text-muted backdrop-blur"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-degraded opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-degraded" />
            </span>
            SILENT-DRIFT SENTINEL
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.08 }}
            className="text-balance font-display text-5xl leading-[1.05] tracking-tight text-fg sm:text-7xl"
          >
            Your model is quietly
            <br />
            getting worse.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.18 }}
            className="mt-7 max-w-xl text-pretty text-lg leading-8 text-muted"
          >
            An on-call AI agent that detects the silent degradation, walks DataHub&apos;s ML lineage
            to the exact upstream column that caused it, names the owner, and writes the cause back
            onto the model. The next engineer inherits the answer.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.28 }}
            className="mt-10 flex flex-wrap items-center justify-center gap-3"
          >
            <Link
              href="/dashboard"
              className="rounded-md border border-accent/50 bg-accent-soft px-5 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/20"
            >
              See it run live
            </Link>
            <a
              href={REPO}
              target="_blank"
              rel="noreferrer"
              className="rounded-md border border-border px-5 py-2.5 text-sm font-medium text-muted transition-colors hover:border-border-strong"
            >
              Read the source
            </a>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="mt-8 font-mono text-[11px] tracking-wider text-subtle"
          >
            Running against open-source DataHub. Apache-2.0.
          </motion.p>
        </div>
      </section>

      {/* ---- problem ---- */}
      <section className="border-t border-border px-6 py-28">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <Label>The problem</Label>
            <h2 className="font-display text-3xl leading-tight text-fg sm:text-4xl">
              The person who detects the drift is never the person who caused it.
            </h2>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-8 space-y-5 text-lg leading-8 text-muted">
              <p>
                A data engineer fixes a normalization bug in an upstream table. The model was trained
                on the old values. Accuracy slides for two weeks, and nobody connects the pipeline
                change to the model, because the two live in different tools owned by different teams.
              </p>
              <p>
                The on-call ML engineer sees the symptom, not the cause, and has no authority over the
                pipeline that broke it. Roughly 80% of production ML failures trace to data and
                pipeline issues, not model weights. This is coordination without authority, and it is
                the gap this agent closes.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---- pipeline ---- */}
      <section className="border-t border-border px-6 py-28">
        <div className="mx-auto max-w-4xl">
          <Reveal>
            <Label>How it works</Label>
            <h2 className="font-display text-3xl leading-tight text-fg sm:text-4xl">
              Five steps, from silent drop to a durable answer on the model.
            </h2>
          </Reveal>
          <div className="mt-12 flex flex-col">
            {PIPELINE.map((p, i) => (
              <Reveal key={p.step} delay={i * 0.06}>
                <div className="flex gap-5 border-t border-border py-6">
                  <div className="tnum shrink-0 font-mono text-sm text-accent">{p.step}</div>
                  <div>
                    <div className="text-lg font-medium text-fg">{p.name}</div>
                    <p className="mt-1.5 max-w-2xl text-[15px] leading-7 text-muted">{p.note}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---- the write-back hero moment ---- */}
      <section className="border-t border-border px-6 py-28">
        <div className="mx-auto grid max-w-5xl items-center gap-12 lg:grid-cols-2">
          <Reveal>
            <div>
              <Label>The write-back</Label>
              <h2 className="font-display text-3xl leading-tight text-fg sm:text-4xl">
                It writes the cause back onto the model.
              </h2>
              <div className="mt-6 space-y-5 text-[15px] leading-7 text-muted">
                <p>
                  Incidents cannot be raised on ML model entities in DataHub, so the finding is split.
                  A typed <span className="font-mono text-fg">drift_causation</span> property, a{" "}
                  <span className="font-mono text-fg">drift-degraded</span> tag, and an RCA document
                  land on the model. A matching incident lands on the upstream table and routes to its
                  owner.
                </p>
                <p>
                  The catalog stops being a passive record and becomes the place the answer lives. The
                  next engineer or agent that opens the model page inherits the diagnosis instead of
                  starting the investigation over.
                </p>
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.12}>
            <div className="rounded-card border border-border bg-surface-1 p-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <span className="font-mono text-sm font-medium text-fg">purchase_intent</span>
                <span className="rounded-full border border-degraded/50 bg-degraded-soft px-2 py-0.5 text-[10px] font-medium text-degraded">
                  drift-degraded
                </span>
              </div>
              <div className="mt-3 rounded-md border border-degraded/30 bg-degraded-soft/40 p-3">
                <div className="font-mono text-[9px] tracking-widest text-degraded">DRIFT_CAUSATION</div>
                <div className="mt-2 space-y-1.5 font-mono text-[11px]">
                  <div className="flex gap-2"><span className="w-16 shrink-0 text-subtle">feature</span><span className="text-fg">PageValues</span></div>
                  <div className="flex gap-2"><span className="w-16 shrink-0 text-subtle">change</span><span className="text-fg">null_default_regression</span></div>
                  <div className="flex gap-2"><span className="w-16 shrink-0 text-subtle">impact</span><span className="text-fg">roc_auc 0.808 to 0.713</span></div>
                  <div className="flex gap-2"><span className="w-16 shrink-0 text-subtle">owner</span><span className="text-fg">data-engineering</span></div>
                </div>
              </div>
              <div className="mt-2 rounded-md border border-accent/30 bg-accent-soft/40 p-3">
                <div className="font-mono text-[9px] tracking-widest text-accent">RCA DOCUMENT + INCIDENT</div>
                <p className="mt-1.5 text-[11px] leading-5 text-muted">
                  Root-cause analysis attached to the model. A FRESHNESS incident raised on the
                  upstream web_sessions table.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---- novelty ---- */}
      <section className="border-t border-border px-6 py-28">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <Label>What is actually new</Label>
            <h2 className="font-display text-3xl leading-tight text-fg sm:text-4xl">
              Two novel parts, framed honestly.
            </h2>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="mt-8 space-y-5 text-[15px] leading-7 text-muted">
              <p>
                Drift detection and owner lookup are composed commodities. We concede them. The
                defensible parts are automated model-lineage root-cause, walking the catalog&apos;s
                model graph to the upstream change, and the write-back of a new context class onto the
                model entity in an open-source catalog.
              </p>
              <p>
                The prior art stops short in specific ways. Monte Carlo and Bigeye root-cause data
                incidents, not model degradation. Arize and Fiddler work in feature space, not catalog
                lineage. Atlan and OpenMetadata hold the metadata but leave the trace to a human.
                Databricks Lakehouse Monitoring is closest in vision but does not ship this loop on an
                open catalog.
              </p>
              <p className="text-subtle">
                Root cause here is lineage-guided correlation supported by data-quality evidence, not
                proven causation. The product says so, on the model page and in the RCA.
              </p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---- architecture ---- */}
      <section className="border-t border-border px-6 py-28">
        <div className="mx-auto max-w-4xl">
          <Reveal>
            <Label>Architecture</Label>
            <h2 className="font-display text-3xl leading-tight text-fg sm:text-4xl">
              The LLM reasons. Deterministic code does the writing.
            </h2>
          </Reveal>
          <div className="mt-12 grid gap-px overflow-hidden rounded-card border border-border bg-border sm:grid-cols-2">
            {ARCHITECTURE.map((a, i) => (
              <Reveal key={a.k} delay={i * 0.06} className="bg-surface-1">
                <div className="h-full p-6">
                  <div className="font-mono text-[11px] uppercase tracking-widest text-accent">{a.k}</div>
                  <p className="mt-2 text-[14px] leading-6 text-muted">{a.v}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ---- final CTA ---- */}
      <section className="relative overflow-hidden border-t border-border px-6 py-32">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(60% 60% at 50% 100%, oklch(0.7 0.16 253 / 0.1), transparent 70%)" }}
        />
        <div className="relative mx-auto max-w-2xl text-center">
          <Reveal>
            <h2 className="font-display text-4xl leading-tight text-fg sm:text-5xl">
              Watch it run.
            </h2>
            <p className="mx-auto mt-5 max-w-lg text-lg leading-8 text-muted">
              Open the dashboard and press run. You will see the agent detect the drift, walk the
              lineage, reason about the cause, and write it back, live, in about fifteen seconds.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link
                href="/dashboard"
                className="rounded-md border border-accent/50 bg-accent-soft px-5 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/20"
              >
                Open the dashboard
              </Link>
              <a
                href={REPO}
                target="_blank"
                rel="noreferrer"
                className="rounded-md border border-border px-5 py-2.5 text-sm font-medium text-muted transition-colors hover:border-border-strong"
              >
                View on GitHub
              </a>
            </div>
          </Reveal>
        </div>
        <div className="relative mx-auto mt-20 flex max-w-4xl flex-wrap items-center justify-between gap-4 border-t border-border pt-8 font-mono text-[11px] text-subtle">
          <span>SILENT-DRIFT SENTINEL</span>
          <span>Built on open-source DataHub</span>
          <span>Apache-2.0</span>
        </div>
      </section>
    </main>
  );
}
