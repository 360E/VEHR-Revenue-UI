"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

type Patient = {
  id: string;
  first_name: string;
  last_name: string;
  dob?: string | null;
  phone?: string | null;
  email?: string | null;
  created_at?: string;
};

type Encounter = {
  id: string;
  patient_id: string;
  encounter_type: string;
  start_time: string;
  end_time?: string | null;
  clinician?: string | null;
  location?: string | null;
  modality?: string | null;
  created_at?: string;
};

type FormSubmission = {
  id: string;
  patient_id: string;
  encounter_id?: string | null;
  form_template_id: string;
  template_version_id?: string | null;
  submitted_data_json: string;
  pdf_uri?: string | null;
  created_at?: string;
};

type FormTemplate = {
  id: string;
  name: string;
  description?: string | null;
  version: number;
  status: string;
  schema_json: string;
  created_at?: string;
};

type RenderField = {
  id: string;
  label: string;
  type: "text" | "textarea" | "number" | "select" | "checkbox" | "date";
  required?: boolean;
  options?: string[];
};

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim().length > 0) {
      return message;
    }
  }
  return fallback;
}

function parseTemplateFields(schemaJson: string): RenderField[] {
  try {
    const parsed = JSON.parse(schemaJson) as {
      fields?: unknown;
      properties?: Record<string, unknown>;
      required?: unknown;
    };

    if (Array.isArray(parsed.fields)) {
      const fields: RenderField[] = [];
      for (const rawField of parsed.fields) {
        if (!rawField || typeof rawField !== "object") continue;
        const value = rawField as Record<string, unknown>;
        const id = typeof value.id === "string" ? value.id.trim() : "";
        const label = typeof value.label === "string" ? value.label.trim() : id;
        const fieldType =
          value.type === "text" ||
          value.type === "textarea" ||
          value.type === "number" ||
          value.type === "select" ||
          value.type === "checkbox" ||
          value.type === "date"
            ? value.type
            : null;

        if (!id || !label || !fieldType) continue;
        const options =
          Array.isArray(value.options) &&
          value.options.every((option) => typeof option === "string")
            ? (value.options as string[])
            : undefined;
        fields.push({
          id,
          label,
          type: fieldType,
          required: Boolean(value.required),
          options,
        });
      }
      if (fields.length > 0) {
        return fields;
      }
    }

    if (parsed.properties && typeof parsed.properties === "object") {
      const requiredSet = new Set(
        Array.isArray(parsed.required)
          ? parsed.required.filter((item) => typeof item === "string")
          : []
      );
      const fields: RenderField[] = [];

      for (const [propertyName, rawProperty] of Object.entries(parsed.properties)) {
        if (!rawProperty || typeof rawProperty !== "object") continue;
        const property = rawProperty as Record<string, unknown>;
        const typeValue =
          typeof property.type === "string"
            ? property.type
            : Array.isArray(property.type) && typeof property.type[0] === "string"
              ? property.type[0]
              : "string";

        let mappedType: RenderField["type"] = "text";
        if (typeValue === "boolean") mappedType = "checkbox";
        if (typeValue === "number" || typeValue === "integer") mappedType = "number";
        if (typeValue === "string" && property.format === "date") mappedType = "date";

        const enumOptions =
          Array.isArray(property.enum) &&
          property.enum.every((value) => typeof value === "string")
            ? (property.enum as string[])
            : undefined;

        if (enumOptions && enumOptions.length > 0) {
          mappedType = "select";
        }

        fields.push({
          id: propertyName,
          label:
            typeof property.title === "string" && property.title.trim().length > 0
              ? property.title
              : propertyName,
          type: mappedType,
          required: requiredSet.has(propertyName),
          options: enumOptions,
        });
      }

      return fields;
    }

    return [];
  } catch {
    return [];
  }
}

export default function PatientChartPage() {
  const params = useParams();
  const patientId = Array.isArray(params?.id) ? params.id[0] : params?.id;

  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "encounters" | "forms">("overview");
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [encountersLoading, setEncountersLoading] = useState(true);
  const [encountersError, setEncountersError] = useState<string | null>(null);
  const [forms, setForms] = useState<FormSubmission[]>([]);
  const [formsLoading, setFormsLoading] = useState(true);
  const [formsError, setFormsError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedEncounterId, setSelectedEncounterId] = useState("");
  const [formValues, setFormValues] = useState<Record<string, string | number | boolean>>({});
  const [formValidationErrors, setFormValidationErrors] = useState<string[]>([]);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccessId, setSubmitSuccessId] = useState<string | null>(null);
  const [encounterDialogOpen, setEncounterDialogOpen] = useState(false);
  const [encounterSubmitLoading, setEncounterSubmitLoading] = useState(false);
  const [encounterSubmitError, setEncounterSubmitError] = useState<string | null>(null);
  const [encounterForm, setEncounterForm] = useState({
    encounter_type: "",
    start_time: "",
    end_time: "",
    clinician: "",
    location: "",
    modality: "",
  });

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) ?? null,
    [templates, selectedTemplateId]
  );

  const publishedTemplates = useMemo(
    () => templates.filter((template) => template.status === "published"),
    [templates]
  );

  const renderFields = useMemo<RenderField[]>(() => {
    if (!selectedTemplate) return [];
    return parseTemplateFields(selectedTemplate.schema_json);
  }, [selectedTemplate]);

  useEffect(() => {
    if (!patientId) return;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiFetch<Patient>(`/api/v1/patients/${patientId}`, {
          cache: "no-store",
        });
        setPatient(data);
      } catch (error: unknown) {
        setError(toErrorMessage(error, "Failed to load patient"));
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [patientId]);

  const refreshEncounters = useCallback(async () => {
    if (!patientId) return;

    try {
      setEncountersLoading(true);
      setEncountersError(null);
      const data = await apiFetch<Encounter[]>(`/api/v1/patients/${patientId}/encounters`, {
        cache: "no-store",
      });
      setEncounters(data);
      setSelectedEncounterId((current) =>
        current && data.some((encounter) => encounter.id === current)
          ? current
          : (data[0]?.id ?? "")
      );
    } catch (error: unknown) {
      setEncountersError(toErrorMessage(error, "Failed to load encounters"));
    } finally {
      setEncountersLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    refreshEncounters();
  }, [refreshEncounters]);

  const refreshForms = useCallback(async () => {
    if (!patientId) return;

    try {
      setFormsLoading(true);
      setFormsError(null);
      const data = await apiFetch<FormSubmission[]>(`/api/v1/patients/${patientId}/forms`, {
        cache: "no-store",
      });
      setForms(data);
    } catch (error: unknown) {
      setFormsError(toErrorMessage(error, "Failed to load forms"));
    } finally {
      setFormsLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    refreshForms();
  }, [refreshForms]);

  useEffect(() => {
    async function loadTemplates() {
      try {
        setTemplatesLoading(true);
        setTemplatesError(null);
        const data = await apiFetch<FormTemplate[]>("/api/v1/forms/templates", {
          cache: "no-store",
        });
        setTemplates(data);
        const firstPublished = data.find((template) => template.status === "published")?.id;
        setSelectedTemplateId((current) => {
          if (current && data.some((template) => template.id === current && template.status === "published")) {
            return current;
          }
          return firstPublished || "";
        });
      } catch (error: unknown) {
        setTemplatesError(toErrorMessage(error, "Failed to load templates"));
      } finally {
        setTemplatesLoading(false);
      }
    }

    loadTemplates();
  }, []);

  useEffect(() => {
    if (renderFields.length === 0) {
      setFormValues({});
      return;
    }
    setFormValues((current) => {
      const next: Record<string, string | number | boolean> = {};
      for (const field of renderFields) {
        const existing = current[field.id];
        if (existing !== undefined) {
          next[field.id] = existing;
        } else if (field.type === "checkbox") {
          next[field.id] = false;
        } else if (field.type === "number") {
          next[field.id] = 0;
        } else {
          next[field.id] = "";
        }
      }
      return next;
    });
    setFormValidationErrors([]);
    setSubmitError(null);
    setSubmitSuccessId(null);
  }, [renderFields]);

  function formatDate(value?: string | null) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function toLocalDateTimeInput(value: Date) {
    const pad = (amount: number) => String(amount).padStart(2, "0");
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(
      value.getDate()
    )}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
  }

  function openEncounterDialog() {
    setEncounterSubmitError(null);
    setEncounterForm({
      encounter_type: "",
      start_time: toLocalDateTimeInput(new Date()),
      end_time: "",
      clinician: "",
      location: "",
      modality: "",
    });
    setEncounterDialogOpen(true);
  }

  function closeEncounterDialog() {
    setEncounterDialogOpen(false);
    setEncounterSubmitError(null);
  }

  async function handleCreateEncounter(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!patientId) return;

    const encounter_type = encounterForm.encounter_type.trim();
    const start_time = encounterForm.start_time.trim();

    if (!encounter_type || !start_time) {
      setEncounterSubmitError("Encounter type and start time are required.");
      return;
    }

    try {
      setEncounterSubmitLoading(true);
      setEncounterSubmitError(null);

      const payload = {
        encounter_type,
        start_time: new Date(start_time).toISOString(),
        end_time: encounterForm.end_time
          ? new Date(encounterForm.end_time).toISOString()
          : null,
        clinician: encounterForm.clinician || null,
        location: encounterForm.location || null,
        modality: encounterForm.modality || null,
      };

      await apiFetch<Encounter>(`/api/v1/patients/${patientId}/encounters`, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      closeEncounterDialog();
      await refreshEncounters();
    } catch (error: unknown) {
      setEncounterSubmitError(toErrorMessage(error, "Failed to create encounter"));
    } finally {
      setEncounterSubmitLoading(false);
    }
  }

  function updateFormField(fieldId: string, value: string | number | boolean) {
    setFormValues((current) => ({ ...current, [fieldId]: value }));
  }

  function validateCurrentForm(): string[] {
    const errors: string[] = [];
    for (const field of renderFields) {
      const value = formValues[field.id];
      if (field.required && (value === undefined || value === null || value === "")) {
        errors.push(`${field.label} is required`);
      }
      if (field.type === "select" && field.options && value && !field.options.includes(String(value))) {
        errors.push(`${field.label} must be one of: ${field.options.join(", ")}`);
      }
      if (field.type === "number" && value !== undefined && value !== null && value !== "") {
        const asNumber = Number(value);
        if (Number.isNaN(asNumber)) {
          errors.push(`${field.label} must be a number`);
        }
      }
    }
    return errors;
  }

  async function handleStartForm() {
    if (!patientId || !selectedTemplateId) {
      setSubmitError("Select a published template to submit.");
      return;
    }

    if (!selectedTemplate || selectedTemplate.status !== "published") {
      setSubmitError("Only published templates can be submitted.");
      return;
    }

    const validationErrors = validateCurrentForm();
    if (validationErrors.length > 0) {
      setFormValidationErrors(validationErrors);
      setSubmitError("Fix validation errors before submitting.");
      return;
    }

    const submittedData: Record<string, string | number | boolean> = {};
    for (const field of renderFields) {
      const raw = formValues[field.id];
      if (raw === undefined || raw === null || raw === "") {
        continue;
      }
      if (field.type === "number") {
        submittedData[field.id] = Number(raw);
      } else {
        submittedData[field.id] = raw;
      }
    }

    try {
      setSubmitLoading(true);
      setSubmitError(null);
      setFormValidationErrors([]);
      setSubmitSuccessId(null);

      const payload = {
        patient_id: patientId,
        template_version_id: selectedTemplateId,
        encounter_id: selectedEncounterId || null,
        submitted_data: submittedData,
      };

      const data = await apiFetch<FormSubmission>("/api/v1/forms/submit", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSubmitSuccessId(data?.id ?? "unknown");
      await refreshForms();
    } catch (error: unknown) {
      setSubmitError(toErrorMessage(error, "Failed to submit form"));
    } finally {
      setSubmitLoading(false);
    }
  }

  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ fontSize: 28, fontWeight: 700 }}>Patient Chart</h1>

      {!patientId && <p style={{ color: "crimson" }}>Error: Missing patient id</p>}
      {loading && patientId && <p>Loading...</p>}
      {error && <p style={{ color: "crimson" }}>Error: {error}</p>}

      {!loading && !error && patient && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>
            {patient.last_name}, {patient.first_name}
          </div>

          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => setActiveTab("overview")}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #ddd",
                background: activeTab === "overview" ? "#f4f4f5" : "white",
                fontWeight: activeTab === "overview" ? 600 : 500,
                cursor: "pointer",
              }}
            >
              Overview
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("encounters")}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #ddd",
                background: activeTab === "encounters" ? "#f4f4f5" : "white",
                fontWeight: activeTab === "encounters" ? 600 : 500,
                cursor: "pointer",
              }}
            >
              Encounters
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("forms")}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                border: "1px solid #ddd",
                background: activeTab === "forms" ? "#f4f4f5" : "white",
                fontWeight: activeTab === "forms" ? 600 : 500,
                cursor: "pointer",
              }}
            >
              Forms
            </button>
          </div>

          {activeTab === "overview" && (
            <div style={{ marginTop: 12, display: "grid", gap: 6 }}>
              <div>
                <strong>DOB:</strong> {patient.dob ?? "-"}
              </div>
              <div>
                <strong>Phone:</strong> {patient.phone ?? "-"}
              </div>
              <div>
                <strong>Email:</strong> {patient.email ?? "-"}
              </div>
            </div>
          )}

          {activeTab === "encounters" && (
            <div style={{ marginTop: 12 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                  marginBottom: 12,
                }}
              >
                <div style={{ fontWeight: 600 }}>Encounters</div>
                <button
                  type="button"
                  onClick={openEncounterDialog}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 6,
                    border: "1px solid #1f2937",
                    background: "#1f2937",
                    color: "white",
                    cursor: "pointer",
                  }}
                >
                  New Encounter
                </button>
              </div>

              {encountersLoading && <p>Loading encounters...</p>}
              {encountersError && <p style={{ color: "crimson" }}>Error: {encountersError}</p>}

              {!encountersLoading && !encountersError && encounters.length === 0 && (
                <p>No encounters yet.</p>
              )}

              {!encountersLoading && !encountersError && encounters.length > 0 && (
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Type
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Start
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        End
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Clinician
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Location
                      </th>
                      <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: 8 }}>
                        Modality
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {encounters.map((encounter) => (
                      <tr key={encounter.id}>
                        <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>
                          {encounter.encounter_type || "Encounter"}
                        </td>
                        <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>
                          {formatDate(encounter.start_time)}
                        </td>
                        <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>
                          {formatDate(encounter.end_time)}
                        </td>
                        <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>
                          {encounter.clinician ?? "-"}
                        </td>
                        <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>
                          {encounter.location ?? "-"}
                        </td>
                        <td style={{ borderBottom: "1px solid #eee", padding: 8 }}>
                          {encounter.modality ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "forms" && (
            <div style={{ marginTop: 12 }}>
              <div style={{ display: "grid", gap: 12 }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <label htmlFor="template-select" style={{ fontWeight: 600 }}>
                    Template
                  </label>
                  <select
                    id="template-select"
                    value={selectedTemplateId}
                    onChange={(e) => setSelectedTemplateId(e.target.value)}
                    disabled={templatesLoading || publishedTemplates.length === 0}
                    style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #ddd", minWidth: 260 }}
                  >
                    {publishedTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name} v{template.version}
                      </option>
                    ))}
                  </select>

                  <label htmlFor="encounter-select" style={{ fontWeight: 600 }}>
                    Encounter
                  </label>
                  <select
                    id="encounter-select"
                    value={selectedEncounterId}
                    onChange={(e) => setSelectedEncounterId(e.target.value)}
                    style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #ddd", minWidth: 220 }}
                  >
                    <option value="">None</option>
                    {encounters.map((encounter) => (
                      <option key={encounter.id} value={encounter.id}>
                        {encounter.encounter_type || "Encounter"} - {formatDate(encounter.start_time)}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    onClick={handleStartForm}
                    disabled={submitLoading || templatesLoading || publishedTemplates.length === 0}
                    style={{
                      padding: "6px 12px",
                      borderRadius: 6,
                      border: "1px solid #1f2937",
                      background: "#1f2937",
                      color: "white",
                      cursor: submitLoading ? "default" : "pointer",
                    }}
                  >
                    {submitLoading ? "Submitting..." : "Submit Form"}
                  </button>
                </div>

                {selectedTemplate ? (
                  <div
                    style={{
                      border: "1px solid #e2e8f0",
                      borderRadius: 10,
                      padding: 14,
                      display: "grid",
                      gap: 10,
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>
                      {selectedTemplate.name} v{selectedTemplate.version}
                    </div>
                    {selectedTemplate.description ? (
                      <div style={{ color: "#475569", fontSize: 14 }}>{selectedTemplate.description}</div>
                    ) : null}

                    {renderFields.length === 0 ? (
                      <div style={{ color: "#dc2626", fontSize: 14 }}>
                        This template schema is not renderer-compatible yet.
                      </div>
                    ) : (
                      <div style={{ display: "grid", gap: 10 }}>
                        {renderFields.map((field) => {
                          const value = formValues[field.id];
                          return (
                            <div key={field.id} style={{ display: "grid", gap: 4 }}>
                              <label htmlFor={`field-${field.id}`} style={{ fontWeight: 600 }}>
                                {field.label}
                                {field.required ? " *" : ""}
                              </label>

                              {field.type === "textarea" ? (
                                <textarea
                                  id={`field-${field.id}`}
                                  value={typeof value === "string" ? value : ""}
                                  onChange={(event) => updateFormField(field.id, event.target.value)}
                                  style={{
                                    border: "1px solid #cbd5e1",
                                    borderRadius: 6,
                                    padding: "8px 10px",
                                    minHeight: 90,
                                  }}
                                />
                              ) : null}

                              {field.type === "text" ? (
                                <input
                                  id={`field-${field.id}`}
                                  type="text"
                                  value={typeof value === "string" ? value : ""}
                                  onChange={(event) => updateFormField(field.id, event.target.value)}
                                  style={{ border: "1px solid #cbd5e1", borderRadius: 6, padding: "8px 10px" }}
                                />
                              ) : null}

                              {field.type === "number" ? (
                                <input
                                  id={`field-${field.id}`}
                                  type="number"
                                  value={typeof value === "number" ? String(value) : typeof value === "string" ? value : ""}
                                  onChange={(event) => updateFormField(field.id, event.target.value)}
                                  style={{ border: "1px solid #cbd5e1", borderRadius: 6, padding: "8px 10px" }}
                                />
                              ) : null}

                              {field.type === "date" ? (
                                <input
                                  id={`field-${field.id}`}
                                  type="date"
                                  value={typeof value === "string" ? value : ""}
                                  onChange={(event) => updateFormField(field.id, event.target.value)}
                                  style={{ border: "1px solid #cbd5e1", borderRadius: 6, padding: "8px 10px" }}
                                />
                              ) : null}

                              {field.type === "select" ? (
                                <select
                                  id={`field-${field.id}`}
                                  value={typeof value === "string" ? value : ""}
                                  onChange={(event) => updateFormField(field.id, event.target.value)}
                                  style={{ border: "1px solid #cbd5e1", borderRadius: 6, padding: "8px 10px" }}
                                >
                                  <option value="">Select...</option>
                                  {(field.options || []).map((option) => (
                                    <option key={`${field.id}-${option}`} value={option}>
                                      {option}
                                    </option>
                                  ))}
                                </select>
                              ) : null}

                              {field.type === "checkbox" ? (
                                <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                  <input
                                    id={`field-${field.id}`}
                                    type="checkbox"
                                    checked={Boolean(value)}
                                    onChange={(event) => updateFormField(field.id, event.target.checked)}
                                  />
                                  <span>Checked</span>
                                </label>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>

              {templatesLoading && <p>Loading templates...</p>}
              {templatesError && <p style={{ color: "crimson" }}>Error: {templatesError}</p>}
              {!templatesLoading && !templatesError && publishedTemplates.length === 0 && (
                <p>No published templates available. Create and publish one in Forms Builder.</p>
              )}

              {submitError && <p style={{ color: "crimson" }}>Error: {submitError}</p>}
              {formValidationErrors.length > 0 && (
                <ul style={{ marginTop: 8, color: "crimson" }}>
                  {formValidationErrors.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              )}
              {submitSuccessId && (
                <p style={{ color: "green" }}>Submitted form: {submitSuccessId}</p>
              )}

              {formsLoading && <p>Loading forms...</p>}
              {formsError && <p style={{ color: "crimson" }}>Error: {formsError}</p>}

              {!formsLoading && !formsError && forms.length === 0 && <p>No forms yet.</p>}

              {!formsLoading && !formsError && forms.length > 0 && (
                <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
                  {forms.map((form) => (
                    <li
                      key={form.id}
                      style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}
                    >
                      <div style={{ fontWeight: 600 }}>Template: {form.form_template_id}</div>
                      <div style={{ color: "#555", marginTop: 4 }}>
                        Submitted: {formatDate(form.created_at)}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {encounterDialogOpen && (
            <div
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(15, 23, 42, 0.45)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 16,
                zIndex: 50,
              }}
            >
              <div
                style={{
                  width: "100%",
                  maxWidth: 520,
                  background: "white",
                  borderRadius: 12,
                  border: "1px solid #e2e8f0",
                  padding: 20,
                  boxShadow: "0 24px 60px rgba(15, 23, 42, 0.2)",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div>
                    <h2 style={{ margin: 0, fontSize: 18 }}>New Encounter</h2>
                    <p style={{ marginTop: 6, color: "#64748b" }}>
                      Record a new visit for this patient.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={closeEncounterDialog}
                    style={{
                      border: "none",
                      background: "transparent",
                      color: "#334155",
                      cursor: "pointer",
                      fontSize: 14,
                    }}
                  >
                    Close
                  </button>
                </div>

                <form
                  onSubmit={handleCreateEncounter}
                  style={{ marginTop: 16, display: "grid", gap: 12 }}
                >
                  {encounterSubmitError && (
                    <p style={{ color: "crimson", margin: 0 }}>{encounterSubmitError}</p>
                  )}
                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="encounter_type" style={{ fontWeight: 600 }}>
                      Encounter type
                    </label>
                    <input
                      id="encounter_type"
                      value={encounterForm.encounter_type}
                      onChange={(event) =>
                        setEncounterForm((current) => ({
                          ...current,
                          encounter_type: event.target.value,
                        }))
                      }
                      required
                      style={{
                        border: "1px solid #cbd5f5",
                        borderRadius: 6,
                        padding: "8px 10px",
                      }}
                      placeholder="Annual checkup"
                    />
                  </div>

                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="start_time" style={{ fontWeight: 600 }}>
                      Start time
                    </label>
                    <input
                      id="start_time"
                      type="datetime-local"
                      value={encounterForm.start_time}
                      onChange={(event) =>
                        setEncounterForm((current) => ({
                          ...current,
                          start_time: event.target.value,
                        }))
                      }
                      required
                      style={{
                        border: "1px solid #cbd5f5",
                        borderRadius: 6,
                        padding: "8px 10px",
                      }}
                    />
                  </div>

                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="end_time" style={{ fontWeight: 600 }}>
                      End time (optional)
                    </label>
                    <input
                      id="end_time"
                      type="datetime-local"
                      value={encounterForm.end_time}
                      onChange={(event) =>
                        setEncounterForm((current) => ({
                          ...current,
                          end_time: event.target.value,
                        }))
                      }
                      style={{
                        border: "1px solid #cbd5f5",
                        borderRadius: 6,
                        padding: "8px 10px",
                      }}
                    />
                  </div>

                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="clinician" style={{ fontWeight: 600 }}>
                      Clinician
                    </label>
                    <input
                      id="clinician"
                      value={encounterForm.clinician}
                      onChange={(event) =>
                        setEncounterForm((current) => ({
                          ...current,
                          clinician: event.target.value,
                        }))
                      }
                      style={{
                        border: "1px solid #cbd5f5",
                        borderRadius: 6,
                        padding: "8px 10px",
                      }}
                      placeholder="Dr. Rivera"
                    />
                  </div>

                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="location" style={{ fontWeight: 600 }}>
                      Location
                    </label>
                    <input
                      id="location"
                      value={encounterForm.location}
                      onChange={(event) =>
                        setEncounterForm((current) => ({
                          ...current,
                          location: event.target.value,
                        }))
                      }
                      style={{
                        border: "1px solid #cbd5f5",
                        borderRadius: 6,
                        padding: "8px 10px",
                      }}
                      placeholder="Clinic A"
                    />
                  </div>

                  <div style={{ display: "grid", gap: 6 }}>
                    <label htmlFor="modality" style={{ fontWeight: 600 }}>
                      Modality
                    </label>
                    <input
                      id="modality"
                      value={encounterForm.modality}
                      onChange={(event) =>
                        setEncounterForm((current) => ({
                          ...current,
                          modality: event.target.value,
                        }))
                      }
                      style={{
                        border: "1px solid #cbd5f5",
                        borderRadius: 6,
                        padding: "8px 10px",
                      }}
                      placeholder="In-person"
                    />
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
                    <button
                      type="button"
                      onClick={closeEncounterDialog}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 6,
                        border: "1px solid #cbd5e1",
                        background: "white",
                        cursor: "pointer",
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={encounterSubmitLoading}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 6,
                        border: "1px solid #1f2937",
                        background: "#1f2937",
                        color: "white",
                        cursor: encounterSubmitLoading ? "default" : "pointer",
                      }}
                    >
                      {encounterSubmitLoading ? "Creating..." : "Create encounter"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
