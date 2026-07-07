const PIPELINE = [
  { step: "01", name: "Detect", note: "label-free performance drop" },
  { step: "02", name: "Traverse", note: "walk DataHub ML lineage" },
  { step: "03", name: "Root-Cause", note: "the upstream column that changed" },
  { step: "04", name: "Identify Owner", note: "from catalog metadata" },
  { step: "05", name: "Write-Back", note: "drift-causation onto the model" },
];

export default function Home() {
  return (
    <main className="relative flex flex-1 flex-col items-center justify-center overflow-hidden px-6 py-24">
      {/* ambient accent glow + faint grid, the restrained precursor to the cinematic landing */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, oklch(0.7 0.16 253 / 0.14), transparent 70%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(oklch(1 0 0 / 0.03) 1px, transparent 1px), linear-gradient(90deg, oklch(1 0 0 / 0.03) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(70% 60% at 50% 30%, #000, transparent 80%)",
        }}
      />

      <div className="relative z-10 flex w-full max-w-3xl flex-col items-center text-center">
        <div className="mb-8 flex items-center gap-2 rounded-full border border-border bg-surface-1 px-3 py-1 text-xs font-medium text-muted">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-healthy opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-healthy" />
          </span>
          Silent-Drift Sentinel
        </div>

        <h1 className="text-balance text-4xl font-semibold leading-[1.1] tracking-tight text-fg sm:text-5xl">
          Your model is quietly getting worse.
          <br />
          <span className="text-accent">The Sentinel finds out why.</span>
        </h1>

        <p className="mt-6 max-w-xl text-pretty text-lg leading-8 text-muted">
          An on-call agent that detects a silent performance drop, walks DataHub&apos;s ML
          lineage to the exact upstream column that changed, names the owner, and writes the
          cause back onto the model, so the next engineer inherits the answer.
        </p>

        <ol className="mt-12 grid w-full grid-cols-1 gap-2 sm:grid-cols-5">
          {PIPELINE.map((p) => (
            <li
              key={p.step}
              className="flex flex-col rounded-card border border-border bg-surface-1 p-3 text-left transition-colors hover:border-border-strong"
            >
              <span className="tnum text-[11px] font-medium text-subtle">{p.step}</span>
              <span className="mt-1 text-sm font-semibold text-fg">{p.name}</span>
              <span className="mt-1 text-[11px] leading-4 text-subtle">{p.note}</span>
            </li>
          ))}
        </ol>

        <p className="mt-12 text-xs text-subtle">
          Built on open-source DataHub. Apache-2.0. Under active development.
        </p>
      </div>
    </main>
  );
}
