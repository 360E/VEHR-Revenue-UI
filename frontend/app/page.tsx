import Link from "next/link";

import { BRANDING } from "@/lib/branding";

const highlights = [
  {
    title: "Custom Forms Platform",
    note: "Versioned templates, validation gates, and publish workflow for clinical teams.",
  },
  {
    title: "Audit Compliance Center",
    note: "Rule-driven anomaly detection with assistant briefings for review queues.",
  },
  {
    title: "Integration Framework",
    note: "Connector catalog built for vendor-agnostic expansion across operations.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen px-6 py-16 sm:px-10">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10">
        <div className="rounded-3xl border border-slate-200/70 bg-white/90 p-8 shadow-[0_30px_80px_rgba(15,23,42,0.08)] backdrop-blur sm:p-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">
            <span className="h-2 w-2 rounded-full bg-emerald-500/80" />
            {BRANDING.environmentLabel}
          </div>

          <div className="mt-6 space-y-4">
            <h1 className="text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
              {BRANDING.fullName}
            </h1>
            <p className="max-w-3xl text-base text-slate-600 sm:text-lg">
              A unified clinical operating system for care delivery, compliance oversight, and
              extensible business operations.
            </p>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Open Console
            </Link>
            <Link
              href="/audit-center"
              className="rounded-full border border-slate-300 bg-white px-5 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400"
            >
              View Audit Center
            </Link>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {highlights.map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-slate-200/70 bg-slate-50/70 p-5 text-sm text-slate-600"
              >
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                  {item.title}
                </div>
                <p className="mt-3 text-sm text-slate-700">{item.note}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 text-xs text-slate-500">{BRANDING.internalNote}</div>
        </div>
      </div>
    </div>
  );
}
