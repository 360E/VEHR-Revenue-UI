import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import MetricCard from "../_components/MetricCard";
import { apiFetch } from "@/lib/api";

type CatalogVersion = {
  id: string;
  version: number;
  status: string;
  created_at: string;
};

type CatalogItem = {
  name: string;
  latest_version: number;
  published_version?: number | null;
  draft_versions: number[];
  versions: CatalogVersion[];
};

type UsageInsights = {
  template_count: number;
  submission_count: number;
  status_distribution: Record<string, number>;
  top_templates: { template_id: string; name: string; submission_count: number }[];
};

const starterSchema = `{
  "title": "Intake Assessment",
  "type": "object",
  "required": ["chief_complaint", "risk_level"],
  "properties": {
    "chief_complaint": { "type": "string" },
    "risk_level": { "type": "string" },
    "suicidal_ideation": { "type": "boolean" }
  }
}`;

export default async function FormsBuilderPage() {
  let catalog: CatalogItem[] = [];
  let usage: UsageInsights | null = null;
  let error: string | null = null;

  try {
    const [catalogRes, usageRes] = await Promise.all([
      apiFetch<CatalogItem[]>("/api/v1/forms/templates/catalog", { cache: "no-store" }),
      apiFetch<UsageInsights>("/api/v1/forms/templates/insights/usage", { cache: "no-store" }),
    ]);
    catalog = catalogRes;
    usage = usageRes;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load forms builder data";
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
          Forms Platform
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Forms Builder</h1>
        <p className="text-sm text-slate-500">
          Versioned schema templates, publish controls, and submission readiness.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Templates"
          value={`${usage?.template_count ?? catalog.length}`}
          hint="Total template versions"
        />
        <MetricCard
          label="Submissions"
          value={`${usage?.submission_count ?? 0}`}
          hint="Stored form submissions"
        />
        <MetricCard
          label="Published"
          value={`${usage?.status_distribution?.published ?? 0}`}
          hint="Live template count"
        />
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50/80">
          <CardContent className="pt-6 text-sm text-rose-700">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Template Catalog</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-5">
            {catalog.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-6 text-sm text-slate-500">
                No templates created yet.
              </div>
            ) : (
              catalog.map((template) => (
                <div
                  key={template.name}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-900">{template.name}</div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px] uppercase">
                        v{template.latest_version}
                      </Badge>
                      {template.published_version ? (
                        <Badge className="text-[10px] uppercase">
                          Published v{template.published_version}
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px] uppercase">
                          Unpublished
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    Drafts:{" "}
                    {template.draft_versions.length > 0
                      ? template.draft_versions.map((version) => `v${version}`).join(", ")
                      : "none"}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Starter Schema</CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            <pre className="overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs text-emerald-100">
              {starterSchema}
            </pre>
            <p className="mt-3 text-xs text-slate-500">
              Use this as a starting point for required fields and conditional extensions.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base text-slate-900">Most Used Templates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-5">
          {(usage?.top_templates ?? []).length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
              No submission activity yet.
            </div>
          ) : (
            (usage?.top_templates ?? []).map((item) => (
              <div
                key={item.template_id}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3"
              >
                <div className="text-sm text-slate-700">{item.name}</div>
                <div className="text-xs font-mono text-slate-500">{item.submission_count} submissions</div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
