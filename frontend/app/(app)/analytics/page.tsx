"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppLayoutPageConfig } from "@/lib/app-layout-config";
import { fetchReports, type ReportListItem } from "@/lib/bi";

function displayNameForReport(report: ReportListItem): string {
  if (report.name && report.name.trim()) {
    return report.name;
  }
  return report.report_key
    .split("_")
    .filter(Boolean)
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export default function AnalyticsIndexPage() {
  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadReports() {
      setIsLoading(true);
      setError(null);
      try {
        const rows = await fetchReports();
        if (!isMounted) {
          return;
        }
        setReports(rows);
      } catch (loadError) {
        if (!isMounted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Unable to load analytics reports.");
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadReports();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <section className="space-y-[var(--space-16)]" data-testid="analytics-index-page">
      <AppLayoutPageConfig
        moduleLabel="Governance"
        pageTitle="Analytics"
        subtitle="Explore tenant-scoped analytics reports."
      />

      <header className="space-y-[var(--space-6)]">
        <h1 className="text-2xl font-semibold text-[var(--neutral-text)]">Analytics</h1>
        <p className="text-sm text-[var(--neutral-muted)]">
          Select a report to launch embedded Power BI analytics.
        </p>
      </header>

      {isLoading ? (
        <div className="grid gap-[var(--space-12)] md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={`analytics-loading-${index}`}
              className="h-28 animate-pulse rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow)]"
            />
          ))}
        </div>
      ) : null}

      {!isLoading && error ? (
        <div className="rounded-[var(--radius-card)] border border-[color-mix(in_srgb,var(--status-critical)_30%,white)] bg-[color-mix(in_srgb,var(--status-critical)_8%,white)] p-[var(--space-16)] text-sm text-[var(--status-critical)]">
          {error}
        </div>
      ) : null}

      {!isLoading && !error ? (
        reports.length > 0 ? (
          <div className="grid gap-[var(--space-12)] md:grid-cols-2">
            {reports.map((item) => (
              <Link
                key={item.report_key}
                href={`/analytics/${encodeURIComponent(item.report_key)}`}
                className="rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] p-[var(--space-16)] shadow-[var(--shadow)] transition-colors hover:bg-[var(--surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-primary)]"
              >
                <p className="text-base font-semibold text-[var(--neutral-text)]">{displayNameForReport(item)}</p>
                <p className="mt-[var(--space-6)] text-xs font-medium text-[var(--neutral-muted)]">
                  Key: {item.report_key}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] p-[var(--space-16)] text-sm text-[var(--neutral-muted)]">
            No analytics reports are enabled.
          </div>
        )
      ) : null}
    </section>
  );
}
