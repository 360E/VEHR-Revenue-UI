"use client";

import { useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type FormTemplate = {
  id: string;
  name: string;
  description?: string | null;
  version: number;
  status: "draft" | "published" | "archived" | string;
  schema_json: string;
  created_at: string;
};

const starterSchema = JSON.stringify(
  {
    title: "Intake Assessment",
    type: "object",
    fields: [
      { id: "chief_complaint", label: "Chief Complaint", type: "textarea", required: true },
      {
        id: "risk_level",
        label: "Risk Level",
        type: "select",
        required: true,
        options: ["Low", "Moderate", "High"],
      },
      { id: "safety_plan_present", label: "Safety Plan Present", type: "checkbox", required: false },
    ],
  },
  null,
  2
);

function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function parseSchemaPreview(schemaJson: string): string {
  try {
    return JSON.stringify(JSON.parse(schemaJson), null, 2);
  } catch {
    return schemaJson;
  }
}

function templateLabel(template: FormTemplate): string {
  return `${template.name} v${template.version} (${template.status})`;
}

export default function FormsBuilderPage() {
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  const [newTemplateName, setNewTemplateName] = useState("");
  const [newTemplateDescription, setNewTemplateDescription] = useState("");

  const [editorName, setEditorName] = useState("");
  const [editorDescription, setEditorDescription] = useState("");
  const [editorSchema, setEditorSchema] = useState(starterSchema);
  const [editorError, setEditorError] = useState<string | null>(null);

  const [aiPrompt, setAiPrompt] = useState("");
  const [aiPreview, setAiPreview] = useState<string>("");
  const [aiClonedFromPublished, setAiClonedFromPublished] = useState(false);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) ?? null,
    [selectedTemplateId, templates]
  );

  const publishedTemplates = useMemo(
    () => templates.filter((template) => template.status === "published"),
    [templates]
  );

  async function loadTemplates() {
    try {
      setLoading(true);
      setError(null);
      const data = await apiFetch<FormTemplate[]>("/api/v1/forms/templates", {
        cache: "no-store",
      });
      setTemplates(data);
      setSelectedTemplateId((current) => current || data?.[0]?.id || "");
    } catch (loadError) {
      setError(toErrorMessage(loadError, "Failed to load templates"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTemplates();
  }, []);

  useEffect(() => {
    if (!selectedTemplate) return;
    setEditorName(selectedTemplate.name);
    setEditorDescription(selectedTemplate.description || "");
    setEditorSchema(parseSchemaPreview(selectedTemplate.schema_json));
    setEditorError(null);
    setAiPreview("");
    setAiClonedFromPublished(false);
  }, [selectedTemplate]);

  function requireSelectedTemplate(): FormTemplate | null {
    if (!selectedTemplate) {
      setError("Select a template first.");
      return null;
    }
    return selectedTemplate;
  }

  function clearMessages() {
    setError(null);
    setSuccess(null);
  }

  async function handleCreateTemplate() {
    clearMessages();
    const name = newTemplateName.trim();
    if (!name) {
      setError("Template name is required.");
      return;
    }

    let parsedSchema: unknown;
    try {
      parsedSchema = JSON.parse(starterSchema);
    } catch {
      setError("Starter schema is invalid JSON.");
      return;
    }

    try {
      setIsBusy(true);
      const created = await apiFetch<FormTemplate>("/api/v1/forms/templates", {
        method: "POST",
        body: JSON.stringify({
          name,
          description: newTemplateDescription.trim() || null,
          status: "draft",
          schema: parsedSchema,
        }),
      });

      setNewTemplateName("");
      setNewTemplateDescription("");
      setSuccess(`Template created: ${templateLabel(created)}`);
      await loadTemplates();
      setSelectedTemplateId(created.id);
    } catch (createError) {
      setError(toErrorMessage(createError, "Failed to create template"));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSaveDraft() {
    clearMessages();
    setEditorError(null);
    const template = requireSelectedTemplate();
    if (!template) return;
    if (template.status !== "draft") {
      setEditorError("Published templates are immutable. Clone to draft before editing.");
      return;
    }

    let parsedSchema: unknown;
    try {
      parsedSchema = JSON.parse(editorSchema);
    } catch {
      setEditorError("Schema must be valid JSON.");
      return;
    }

    const name = editorName.trim();
    if (!name) {
      setEditorError("Template name is required.");
      return;
    }

    try {
      setIsBusy(true);
      const updated = await apiFetch<FormTemplate>(`/api/v1/forms/templates/${template.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name,
          description: editorDescription.trim() || null,
          schema: parsedSchema,
        }),
      });
      setSuccess(`Draft saved: ${templateLabel(updated)}`);
      await loadTemplates();
      setSelectedTemplateId(updated.id);
    } catch (saveError) {
      setEditorError(toErrorMessage(saveError, "Failed to save draft"));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCloneToDraft() {
    clearMessages();
    const template = requireSelectedTemplate();
    if (!template) return;

    try {
      setIsBusy(true);
      const cloned = await apiFetch<FormTemplate>(`/api/v1/forms/templates/${template.id}/clone`, {
        method: "POST",
        body: JSON.stringify({ status: "draft" }),
      });
      setSuccess(`Draft created: ${templateLabel(cloned)}`);
      await loadTemplates();
      setSelectedTemplateId(cloned.id);
    } catch (cloneError) {
      setError(toErrorMessage(cloneError, "Failed to clone template"));
    } finally {
      setIsBusy(false);
    }
  }

  async function handlePublish() {
    clearMessages();
    const template = requireSelectedTemplate();
    if (!template) return;
    if (template.status !== "draft") {
      setError("Only draft templates can be published.");
      return;
    }

    try {
      setIsBusy(true);
      const published = await apiFetch<FormTemplate>(`/api/v1/forms/templates/${template.id}/publish`, {
        method: "POST",
        body: JSON.stringify({ archive_previous_published: true }),
      });
      setSuccess(`Published: ${templateLabel(published)}`);
      await loadTemplates();
      setSelectedTemplateId(published.id);
    } catch (publishError) {
      setError(toErrorMessage(publishError, "Failed to publish template"));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleGenerateWithAi() {
    clearMessages();
    setEditorError(null);
    const template = requireSelectedTemplate();
    if (!template) return;

    const prompt = aiPrompt.trim();
    if (prompt.length < 3) {
      setError("Prompt must be at least 3 characters.");
      return;
    }

    try {
      setIsBusy(true);
      const response = await apiFetch<{
        template: FormTemplate;
        was_cloned_from_published: boolean;
        source_template_id: string;
      }>(`/api/v1/forms/templates/${template.id}/generate`, {
        method: "POST",
        body: JSON.stringify({ prompt }),
      });

      const preview = parseSchemaPreview(response.template.schema_json);
      setAiPreview(preview);
      setAiClonedFromPublished(response.was_cloned_from_published);
      setSuccess(
        response.was_cloned_from_published
          ? "Generated into a new draft cloned from the published template."
          : "Generated schema applied to draft template."
      );
      await loadTemplates();
      setSelectedTemplateId(response.template.id);
    } catch (generateError) {
      setError(toErrorMessage(generateError, "Failed to generate schema"));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
          Forms Platform
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Forms Builder</h1>
        <p className="text-sm text-slate-500">
          Create, version, publish, and submit production-ready form templates.
        </p>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700" role="alert">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {success}
        </div>
      ) : null}

      {aiClonedFromPublished ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          Published template was auto-cloned to a new draft before AI updates.
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Create Template</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 pt-5">
            <Input
              placeholder="Template name"
              value={newTemplateName}
              onChange={(event) => setNewTemplateName(event.target.value)}
            />
            <Input
              placeholder="Description (optional)"
              value={newTemplateDescription}
              onChange={(event) => setNewTemplateDescription(event.target.value)}
            />
            <Button type="button" disabled={isBusy} onClick={handleCreateTemplate}>
              {isBusy ? "Working..." : "Create Draft Template"}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Published Templates</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-5 text-sm text-slate-600">
            {publishedTemplates.length === 0 ? (
              <div>No published templates yet.</div>
            ) : (
              publishedTemplates.map((template) => (
                <div key={template.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                  <div className="font-medium text-slate-800">
                    {template.name} v{template.version}
                  </div>
                  <div className="text-xs text-slate-500">{template.description || "No description"}</div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base text-slate-900">Template Editor</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
                value={selectedTemplateId}
                onChange={(event) => setSelectedTemplateId(event.target.value)}
                disabled={loading || templates.length === 0}
              >
                {templates.length === 0 ? (
                  <option value="">No templates</option>
                ) : (
                  templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {templateLabel(template)}
                    </option>
                  ))
                )}
              </select>
              {selectedTemplate ? (
                <Badge variant={selectedTemplate.status === "published" ? "default" : "secondary"}>
                  {selectedTemplate.status}
                </Badge>
              ) : null}
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5">
          {loading ? <div className="text-sm text-slate-500">Loading templates...</div> : null}

          {!loading && !selectedTemplate ? (
            <div className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500">
              Create a template to begin editing.
            </div>
          ) : null}

          {selectedTemplate ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <Input
                  value={editorName}
                  onChange={(event) => setEditorName(event.target.value)}
                  disabled={selectedTemplate.status !== "draft"}
                  placeholder="Template name"
                />
                <Input
                  value={editorDescription}
                  onChange={(event) => setEditorDescription(event.target.value)}
                  disabled={selectedTemplate.status !== "draft"}
                  placeholder="Template description"
                />
              </div>

              {editorError ? (
                <div className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {editorError}
                </div>
              ) : null}

              <div className="grid gap-2">
                <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Schema JSON
                </label>
                <textarea
                  className="min-h-[280px] w-full rounded-md border border-slate-300 bg-slate-950 p-3 font-mono text-xs text-emerald-100 focus:border-slate-300 focus:outline-none"
                  value={editorSchema}
                  onChange={(event) => setEditorSchema(event.target.value)}
                  disabled={selectedTemplate.status !== "draft"}
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={handleSaveDraft} disabled={isBusy || selectedTemplate.status !== "draft"}>
                  Save Draft
                </Button>
                <Button type="button" variant="outline" onClick={handlePublish} disabled={isBusy || selectedTemplate.status !== "draft"}>
                  Publish Template
                </Button>
                <Button type="button" variant="outline" onClick={handleCloneToDraft} disabled={isBusy}>
                  Clone to Draft
                </Button>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base text-slate-900">Generate With AI</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 pt-5">
          <textarea
            className="min-h-[110px] w-full rounded-md border border-slate-300 bg-white p-3 text-sm text-slate-800 focus:border-slate-300 focus:outline-none"
            placeholder="Example: Build an intake assessment with depression/anxiety scores and treatment plan alignment fields."
            value={aiPrompt}
            onChange={(event) => setAiPrompt(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <Button type="button" onClick={handleGenerateWithAi} disabled={isBusy || !selectedTemplate}>
              Generate Schema
            </Button>
            <span className="text-xs text-slate-500">Requires `forms:manage` permission.</span>
          </div>

          {aiPreview ? (
            <div className="grid gap-2">
              <label className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Generated Preview
              </label>
              <pre className="max-h-[280px] overflow-auto rounded-md border border-slate-300 bg-slate-950 p-3 font-mono text-xs text-cyan-100">
                {aiPreview}
              </pre>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

