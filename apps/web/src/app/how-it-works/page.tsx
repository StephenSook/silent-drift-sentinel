import type { ReactNode } from "react";
import Link from "next/link";

export const metadata = {
  title: "How it works | Silent-Drift Sentinel",
  description:
    "The engineering behind the Silent-Drift Sentinel: the ML core, the drift detector, the five-node agent, and the DataHub write-back.",
};

function Section({ label, title, children }: { label: string; title: string; children: ReactNode }) {
  return (
    <section className="border-t border-border px-6 py-16">
      <div className="mx-auto max-w-3xl">
        <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.28em] text-subtle">{label}</div>
        <h2 className="font-display text-3xl leading-tight text-fg">{title}</h2>
        <div className="mt-6 space-y-4 text-[15px] leading-7 text-muted">{children}</div>
      </div>
    </section>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-col gap-1 border-t border-border py-3 sm:flex-row sm:gap-4">
      <div className="w-40 shrink-0 font-mono text-[13px] text-accent">{k}</div>
      <div className="text-[14px] leading-6 text-muted">{v}</div>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <main className="bg-bg">
      <header className="px-6 pb-6 pt-20">
        <div className="mx-auto max-w-3xl">
          <Link href="/" className="font-mono text-[11px] tracking-widest text-subtle hover:text-muted">
            &larr; SILENT-DRIFT SENTINEL
          </Link>
          <h1 className="mt-6 font-display text-5xl leading-[1.05] text-fg">How it works</h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-muted">
            The engineering behind the agent, from the calibrated model to the write-back. The LLM
            reasons about the cause; deterministic code does every catalog write.
          </p>
        </div>
      </header>

      <Section label="The model" title="A calibrated model on real data, split honestly">
        <p>
          The monitored model is a gradient-boosted tree (LightGBM) that predicts purchase intent
          from session behavior, trained on the UCI Online Shoppers dataset (real data, CC BY 4.0).
          The data is split by time, not at random, so the reference and production windows come
          after training, the way a real deployment sees them.
        </p>
        <p>
          Raw tree probabilities are overconfident, so they are isotonic-calibrated on a held-out
          window. Calibration is verified, not assumed: expected calibration error drops from 0.087
          to 0.041 and the Brier score from 0.143 to 0.133. Those numbers are on the dashboard model
          card, computed from the same run.
        </p>
      </Section>

      <Section label="Detection" title="Two layers, and drift is not degradation">
        <p>
          The primary signal is label-free. In production, ground-truth labels arrive late or never,
          so the Sentinel estimates performance without them using NannyML CBPE, which is valid under
          covariate shift with calibrated probabilities. The diagnostic layer is per-feature drift (KS
          for numeric, Chi-squared for categorical) with Benjamini-Hochberg correction for multiple
          testing, a PCA reconstruction check, and a data-quality fingerprint (null rate, cardinality,
          range).
        </p>
        <p>
          The important part is what it does not do. A large input shift is not always a problem. A
          unit rescale of a feature (dollars to cents) moves the distribution a lot, but a tree model
          is invariant to a monotonic transform, so performance is unchanged. The Sentinel proves this
          on the dashboard: the benign scenario shows a hard shift with a flat performance estimate,
          and the agent correctly takes no action. Only a harmful change (a feature regressing to a
          constant default) trips the alarm.
        </p>
      </Section>

      <Section label="The agent" title="Five nodes, a human gate, and the LLM out of the write path">
        <p>
          The agent is a LangGraph state machine with five nodes: Detect, Traverse, Root-Cause,
          Identify Owner, Write-Back. It reads DataHub through the Agent Context Kit tools
          (get_entities, get_lineage) to walk the model&apos;s lineage to the upstream table, and reads
          the owning team from catalog ownership.
        </p>
        <p>
          Claude writes the root-cause narrative, and only the narrative. Every structural decision
          and every catalog write is deterministic code, guarded by a write-ahead log so a failed
          write retries idempotently. If the primary provider errors, the narrative fails over through
          LiteLLM. The write itself is gated behind a human-in-the-loop interrupt: the streamed run
          stops before writing and waits for an explicit approval, so a read never mutates the catalog.
        </p>
      </Section>

      <Section label="The write-back" title="A model cannot hold an incident, so the finding is split">
        <p>
          DataHub&apos;s incident metamodel allows incidents on datasets, charts, dashboards, data
          flows, data jobs, and schema fields, but not on ML models. So the write-back is split. The
          model gets a typed <span className="font-mono text-fg">drift_causation</span> structured
          property, a <span className="font-mono text-fg">drift-degraded</span> tag, and an RCA
          document. The upstream dataset gets an incident routed to its owner.
        </p>
        <p>
          The catalog stops being a passive record and becomes the place the answer lives. The next
          engineer or agent that opens the model page inherits the diagnosis instead of starting the
          investigation over. The root cause is framed honestly as lineage-guided correlation plus
          data-quality evidence, not proven causation.
        </p>
      </Section>

      <Section label="The stack" title="What each piece runs on">
        <div className="mt-2">
          <Row k="ML core" v="LightGBM, scikit-learn isotonic calibration, NannyML CBPE, KS / Chi-squared with Benjamini-Hochberg, PCA reconstruction." />
          <Row k="Agent" v="Python, FastAPI, sse-starlette, LangGraph with a checkpointer and interrupt, langchain-anthropic, LiteLLM failover." />
          <Row k="DataHub" v="Self-hosted open-source DataHub Core, the Agent Context Kit for reads, structured properties and documents and raiseIncident for writes." />
          <Row k="Dashboard" v="Next.js 16, React 19, Tailwind v4 (OKLCH), React Flow with ELK layout, Apache ECharts, Motion." />
          <Row k="Infra" v="One always-on cloud VM (systemd + Caddy TLS) for the agent and DataHub; the dashboard on Vercel." />
        </div>
      </Section>

      <section className="border-t border-border px-6 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-md border border-accent/50 bg-accent-soft px-5 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/20"
            >
              See it run
            </Link>
            <a
              href="https://github.com/StephenSook/silent-drift-sentinel"
              target="_blank"
              rel="noreferrer"
              className="rounded-md border border-border px-5 py-2.5 text-sm font-medium text-muted transition-colors hover:border-border-strong"
            >
              Read the source
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
