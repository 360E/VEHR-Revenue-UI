"use client";

import type { ComponentType } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { BRANDING } from "@/lib/branding";

type NavItem = {
  href: string;
  label: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
};

type NavSection = {
  label: string;
  items: NavItem[];
};

function IconPulse({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M3 12h4l2.5-5 5 10 2.5-5H21" />
    </svg>
  );
}

function IconDashboard({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M3 13c0-5 4-9 9-9s9 4 9 9" />
      <path d="M12 7v6l4 2" />
      <path d="M7 20h10" />
    </svg>
  );
}

function IconPatients({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M16 11a4 4 0 1 0-8 0" />
      <path d="M3 20a9 9 0 0 1 18 0" />
      <circle cx="12" cy="7" r="3" />
    </svg>
  );
}

function IconEncounters({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="4" y="4" width="16" height="16" rx="3" />
      <path d="M8 2v4M16 2v4M4 10h16" />
      <path d="M9 14h6" />
    </svg>
  );
}

function IconForms({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </svg>
  );
}

function IconAudit({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M4 6h16v12H4z" />
      <path d="M9 10h6M9 14h3" />
      <path d="M7 2v4M17 2v4" />
    </svg>
  );
}

function IconIntegrations({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="6" r="3" />
      <circle cx="18" cy="18" r="3" />
      <path d="M8.8 10.8l6.4-3.6M8.8 13.2l6.4 3.6" />
    </svg>
  );
}

function IconCrm({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M4 8h16v12H4z" />
      <path d="M8 8V6a4 4 0 0 1 8 0v2" />
      <path d="M9 14h6" />
    </svg>
  );
}

const navSections: NavSection[] = [
  {
    label: "Overview",
    items: [
      {
        href: "/dashboard",
        label: "Dashboard",
        description: "Operational overview",
        icon: IconDashboard,
      },
    ],
  },
  {
    label: "Care Delivery",
    items: [
      {
        href: "/patients",
        label: "Patients",
        description: "Charts and demographics",
        icon: IconPatients,
      },
      {
        href: "/encounters",
        label: "Encounters",
        description: "Visits and notes",
        icon: IconEncounters,
      },
      {
        href: "/forms-builder",
        label: "Forms Builder",
        description: "Versioned schema templates",
        icon: IconForms,
      },
    ],
  },
  {
    label: "Compliance",
    items: [
      {
        href: "/audit-center",
        label: "Audit Center",
        description: "Risk analytics and reviews",
        icon: IconAudit,
      },
      {
        href: "/integrations",
        label: "Integrations",
        description: "Connector catalog",
        icon: IconIntegrations,
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        href: "/crm",
        label: "CRM",
        description: "Relationships and pipeline",
        icon: IconCrm,
      },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full flex-col gap-8 rounded-3xl border border-slate-900/70 bg-slate-950 p-6 text-slate-100 shadow-[0_35px_90px_rgba(15,23,42,0.35)] lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan-500/15 text-cyan-200">
          <IconPulse className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-semibold tracking-tight text-white">
            {BRANDING.name}
          </div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
            {BRANDING.tagline}
          </div>
        </div>
      </div>

      <nav className="space-y-6">
        {navSections.map((section) => (
          <div key={section.label} className="space-y-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-500">
              {section.label}
            </div>
            <div className="grid gap-2">
              {section.items.map((item) => {
                const isActive =
                  pathname === item.href || pathname?.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`group relative flex items-start gap-3 rounded-2xl border px-3 py-3 transition ${
                      isActive
                        ? "border-cyan-400/60 bg-slate-900 text-white shadow-[0_16px_40px_rgba(8,145,178,0.35)]"
                        : "border-slate-900/60 bg-slate-900/40 text-slate-200 hover:border-slate-700 hover:bg-slate-900/70"
                    }`}
                    data-active={isActive}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <span
                      className={`absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r ${
                        isActive ? "bg-cyan-400" : "bg-transparent"
                      }`}
                    />
                    <span
                      className={`flex h-9 w-9 items-center justify-center rounded-xl border ${
                        isActive
                          ? "border-cyan-400/30 bg-cyan-500/10 text-cyan-200"
                          : "border-slate-800 bg-slate-900/70 text-slate-300 group-hover:text-cyan-100"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="space-y-1">
                      <span className="text-sm font-semibold text-white">
                        {item.label}
                      </span>
                      <span
                        className={`text-xs ${
                          isActive
                            ? "text-slate-300"
                            : "text-slate-500 group-hover:text-slate-300"
                        }`}
                      >
                        {item.description}
                      </span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-auto space-y-4 text-xs text-slate-400">
        <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)]" />
            {BRANDING.environmentLabel}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Audit-ready workflows with live sandbox data.
          </p>
        </div>
        <div className="text-[11px] text-slate-500">{BRANDING.internalNote}</div>
      </div>
    </aside>
  );
}
