import type { ReactNode } from "react";

import Sidebar from "../components/sidebar";
import { BRANDING } from "@/lib/branding";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col gap-6 px-4 py-6 lg:flex-row lg:items-stretch lg:gap-8 lg:px-6">
        <Sidebar />
        <div className="flex min-h-[calc(100vh-3rem)] flex-1 flex-col overflow-hidden rounded-3xl border border-slate-200/70 bg-white/95 shadow-[0_30px_80px_rgba(15,23,42,0.08)] backdrop-blur">
          <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/70 px-6 py-4">
            <div className="space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                {BRANDING.name}
              </div>
              <div className="text-sm font-semibold text-slate-900">
                {BRANDING.tagline}
              </div>
            </div>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-center">
              <div className="relative w-full sm:w-72">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.8}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-4 w-4"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="M20 20l-3.5-3.5" />
                  </svg>
                </span>
                <input
                  className="h-10 w-full rounded-full border border-slate-200 bg-white pl-10 pr-4 text-sm text-slate-700 placeholder:text-slate-400 focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-200"
                  placeholder="Search patients, encounters, tasks"
                  type="search"
                />
              </div>
              <button
                type="button"
                className="flex items-center gap-3 rounded-full border border-slate-200 bg-white px-3 py-2 text-left transition hover:border-slate-300"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                  TD
                </span>
                <span className="hidden sm:block">
                  <span className="block text-xs font-semibold text-slate-900">
                    Taylor Dawson
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    Clinical Admin
                  </span>
                </span>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4 text-slate-400"
                >
                  <path d="M6 9l6 6 6-6" />
                </svg>
              </button>
            </div>
          </header>
          <main className="flex-1 px-6 py-6 sm:px-8 sm:py-8">{children}</main>
          <footer className="border-t border-slate-200/70 px-6 py-3 text-xs text-slate-500">
            {BRANDING.internalNote}
          </footer>
        </div>
      </div>
    </div>
  );
}
