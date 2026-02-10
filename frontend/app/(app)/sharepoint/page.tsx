"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ExternalLink, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type SharePointHomeResponse = {
  organization_id: string;
  home_url: string;
};

const EMBED_TIMEOUT_MS = 8000;
const DEFAULT_SHAREPOINT_HOME_URL =
  "https://valleyhealthandcounseling.sharepoint.com/sites/ValleyHealthHomePage";

function buildQuickLinks(homeUrl: string): Array<{ label: string; href: string }> {
  const normalized = homeUrl.replace(/\/$/, "");
  return [
    { label: "SharePoint Home", href: homeUrl },
    { label: "Site Contents", href: `${normalized}/_layouts/15/viewlsts.aspx` },
  ];
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export default function SharePointPage() {
  const [homeUrl, setHomeUrl] = useState<string>(DEFAULT_SHAREPOINT_HOME_URL);
  const [loadingConfig, setLoadingConfig] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [iframeKey, setIframeKey] = useState(0);
  const [iframeLoading, setIframeLoading] = useState(true);
  const [showFallback, setShowFallback] = useState(false);

  const quickLinks = useMemo(() => buildQuickLinks(homeUrl), [homeUrl]);

  useEffect(() => {
    let mounted = true;
    async function loadSharePointConfig() {
      try {
        setLoadingConfig(true);
        setConfigError(null);
        const response = await apiFetch<SharePointHomeResponse>("/api/v1/sharepoint/home", {
          cache: "no-store",
        });
        if (!mounted) return;
        setHomeUrl(response.home_url);
        setShowFallback(false);
        setIframeLoading(true);
        setIframeKey((current) => current + 1);
      } catch (error) {
        if (!mounted) return;
        setConfigError(toErrorMessage(error, "Failed to load SharePoint configuration."));
      } finally {
        if (mounted) {
          setLoadingConfig(false);
        }
      }
    }

    loadSharePointConfig();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (loadingConfig || showFallback || !iframeLoading) {
      return;
    }

    const timer = window.setTimeout(() => {
      setShowFallback(true);
      setIframeLoading(false);
    }, EMBED_TIMEOUT_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadingConfig, showFallback, iframeLoading, iframeKey]);

  function handleTryAgain() {
    setShowFallback(false);
    setIframeLoading(true);
    setIframeKey((current) => current + 1);
  }

  return (
    <div className="flex min-h-[calc(100vh-15rem)] flex-col gap-5">
      <div className="space-y-2 border-b border-slate-200/70 pb-4">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">SharePoint</h1>
        <p className="text-sm text-slate-500">Organization SharePoint home</p>
      </div>

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden border-slate-200/70 shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between border-b border-slate-200/70 bg-slate-50/70 px-5 py-4">
          <CardTitle className="text-base text-slate-900">Embedded Window</CardTitle>
          <button
            type="button"
            onClick={() => setShowFallback(true)}
            className="text-xs font-semibold text-slate-600 underline decoration-slate-300 underline-offset-4 hover:text-slate-900"
          >
            Having trouble loading?
          </button>
        </CardHeader>
        <CardContent className="relative flex min-h-0 flex-1 p-0">
          {configError ? (
            <div className="flex h-full w-full items-center justify-center bg-slate-50/70 p-6">
              <Card className="w-full max-w-2xl border-rose-200 bg-white shadow-sm">
                <CardHeader className="border-b border-rose-100">
                  <CardTitle className="text-base text-rose-700">Unable to load SharePoint configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-5">
                  <p className="text-sm text-rose-700">{configError}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button type="button" variant="outline" onClick={() => window.location.reload()}>
                      Reload page
                    </Button>
                    <Button asChild>
                      <a href={DEFAULT_SHAREPOINT_HOME_URL} target="_blank" rel="noopener">
                        Open default SharePoint in new tab
                      </a>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}

          {!configError && !showFallback && !loadingConfig ? (
            <iframe
              key={iframeKey}
              src={homeUrl}
              title="Organization SharePoint home"
              className="h-full w-full border-0"
              onLoad={() => setIframeLoading(false)}
            />
          ) : null}

          {!configError && !showFallback && (loadingConfig || iframeLoading) ? (
            <div className="absolute inset-0 flex items-center justify-center bg-white/90">
              <div className="flex flex-col items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
                <span className="h-9 w-9 animate-spin rounded-full border-2 border-slate-300 border-t-cyan-500" />
                <p className="text-sm font-medium text-slate-700">Loading SharePoint...</p>
              </div>
            </div>
          ) : null}

          {!configError && showFallback ? (
            <div className="flex h-full w-full items-center justify-center bg-slate-50/80 p-6">
              <Card className="w-full max-w-2xl border-slate-200 shadow-sm">
                <CardHeader className="border-b border-slate-200/70 bg-white">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                      <AlertTriangle className="h-5 w-5" />
                    </span>
                    <CardTitle className="text-base text-slate-900">Embedding blocked</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-5 pt-5">
                  <p className="text-sm text-slate-700">
                    SharePoint embedding is blocked by your organization&apos;s security policy.
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <Button asChild>
                      <a href={homeUrl} target="_blank" rel="noopener">
                        Open SharePoint in new tab
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </Button>
                    <Button type="button" variant="outline" onClick={handleTryAgain}>
                      Try again
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </div>
                  <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                      Quick Links
                    </h2>
                    <ul className="space-y-1">
                      {quickLinks.map((link) => (
                        <li key={link.href}>
                          <a
                            href={link.href}
                            target="_blank"
                            rel="noopener"
                            className="text-sm font-medium text-cyan-700 underline decoration-cyan-300 underline-offset-4 hover:text-cyan-900"
                          >
                            {link.label}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
