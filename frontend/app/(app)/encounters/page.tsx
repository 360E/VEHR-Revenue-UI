"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiFetch } from "@/lib/api";

const encounterQueues = [
  {
    label: "Intake Assessments",
    note: "Awaiting clinician assignment",
  },
  {
    label: "Follow-Up Visits",
    note: "Documentation due",
  },
  {
    label: "Care Plan Reviews",
    note: "Pending sign-off",
  },
];

type CaptureCreateResponse = {
  id: string;
  encounter_id: string;
  upload_url: string;
  upload_method: string;
  upload_headers: Record<string, string>;
  marked_for_deletion_at: string;
};

type TranscriptResponse = {
  id: string;
  capture_id: string;
  text: string;
  created_at: string;
};

type DraftResponse = {
  id: string;
  capture_id: string;
  note_type: "SOAP" | "DAP";
  content: string;
  created_at: string;
  updated_at: string;
};

type InsertIntoChartResponse = {
  note_id: string;
  patient_id: string;
  encounter_id: string;
  status: string;
};

function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

export default function EncountersPage() {
  const [encounterId, setEncounterId] = useState("");
  const [primaryServiceId, setPrimaryServiceId] = useState("");
  const [visibility, setVisibility] = useState<"clinical_only" | "legal_and_clinical">("clinical_only");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [captureId, setCaptureId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState("");
  const [draftText, setDraftText] = useState("");
  const [draftId, setDraftId] = useState<string | null>(null);
  const [draftType, setDraftType] = useState<"SOAP" | "DAP" | null>(null);
  const [insertResult, setInsertResult] = useState<InsertIntoChartResponse | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [isInserting, setIsInserting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusLine, setStatusLine] = useState<string | null>(null);

  const canUpload = useMemo(() => !!encounterId.trim() && selectedFile !== null && !isUploading, [encounterId, isUploading, selectedFile]);
  const canTranscribe = !!captureId && !isTranscribing;
  const canGenerateDraft = !!captureId && !!transcript.trim() && !isGeneratingDraft;
  const canSaveDraft = !!draftId && !!draftText.trim() && !isSavingDraft;
  const canInsert = !!draftId && !!draftText.trim() && !isInserting;

  async function uploadAudio() {
    if (!selectedFile || !encounterId.trim()) return;

    setIsUploading(true);
    setError(null);
    setStatusLine("Preparing secure upload...");
    setInsertResult(null);

    try {
      const createResponse = await apiFetch<CaptureCreateResponse>("/api/v1/scribe/captures", {
        method: "POST",
        body: JSON.stringify({
          encounter_id: encounterId.trim(),
          filename: selectedFile.name,
          content_type: selectedFile.type || "audio/webm",
        }),
      });

      const uploadResponse = await fetch(createResponse.upload_url, {
        method: createResponse.upload_method,
        headers: createResponse.upload_headers,
        body: selectedFile,
      });
      if (!uploadResponse.ok) {
        throw new Error("Audio upload failed");
      }

      await apiFetch(`/api/v1/scribe/captures/${encodeURIComponent(createResponse.id)}/complete`, {
        method: "POST",
        body: JSON.stringify({}),
      });

      setCaptureId(createResponse.id);
      setTranscript("");
      setDraftText("");
      setDraftId(null);
      setDraftType(null);
      setStatusLine(`Audio uploaded. Capture ID: ${createResponse.id}`);
    } catch (uploadError) {
      setError(toErrorMessage(uploadError, "Failed to upload audio"));
    } finally {
      setIsUploading(false);
    }
  }

  async function transcribeAudio() {
    if (!captureId) return;

    setIsTranscribing(true);
    setError(null);
    setStatusLine("Transcribing capture...");

    try {
      const response = await apiFetch<TranscriptResponse>(`/api/v1/scribe/captures/${encodeURIComponent(captureId)}/transcribe`, {
        method: "POST",
      });
      setTranscript(response.text);
      setStatusLine(`Transcript saved (${new Date(response.created_at).toLocaleString()})`);
    } catch (transcribeError) {
      setError(toErrorMessage(transcribeError, "Failed to transcribe audio"));
    } finally {
      setIsTranscribing(false);
    }
  }

  async function generateDraft(noteType: "SOAP" | "DAP") {
    if (!captureId) return;

    setIsGeneratingDraft(true);
    setError(null);
    setStatusLine(`Generating ${noteType} draft...`);

    try {
      const response = await apiFetch<DraftResponse>(`/api/v1/scribe/captures/${encodeURIComponent(captureId)}/draft-note`, {
        method: "POST",
        body: JSON.stringify({ note_type: noteType }),
      });
      setDraftId(response.id);
      setDraftType(response.note_type);
      setDraftText(response.content);
      setStatusLine(`${response.note_type} draft generated. Provider review required before insert.`);
    } catch (draftError) {
      setError(toErrorMessage(draftError, `Failed to generate ${noteType} draft`));
    } finally {
      setIsGeneratingDraft(false);
    }
  }

  async function saveDraft() {
    if (!draftId || !draftText.trim()) return;

    setIsSavingDraft(true);
    setError(null);
    setStatusLine("Saving draft changes...");

    try {
      const response = await apiFetch<DraftResponse>(`/api/v1/scribe/drafts/${encodeURIComponent(draftId)}`, {
        method: "PUT",
        body: JSON.stringify({ content: draftText.trim() }),
      });
      setDraftText(response.content);
      setStatusLine("Draft updated.");
    } catch (saveError) {
      setError(toErrorMessage(saveError, "Failed to save draft"));
    } finally {
      setIsSavingDraft(false);
    }
  }

  async function insertIntoChart() {
    if (!draftId) return;

    setIsInserting(true);
    setError(null);
    setStatusLine("Inserting draft into chart...");

    try {
      const response = await apiFetch<InsertIntoChartResponse>(
        `/api/v1/scribe/drafts/${encodeURIComponent(draftId)}/insert-into-chart`,
        {
          method: "POST",
          body: JSON.stringify({
            primary_service_id: primaryServiceId.trim() || undefined,
            visibility,
          }),
        }
      );
      setInsertResult(response);
      setStatusLine("Draft inserted into chart as a patient note.");
    } catch (insertError) {
      setError(toErrorMessage(insertError, "Failed to insert draft into chart"));
    } finally {
      setIsInserting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">Encounters</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Encounter Queue</h1>
        <p className="text-sm text-slate-500">Visit timelines, documentation workflow, and clinical status tracking.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Visit Timeline</CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            <div className="space-y-3">
              {["Morning rounds", "Midday check-ins", "Evening handoff"].map((slot) => (
                <div
                  key={slot}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm text-slate-600"
                >
                  <span>{slot}</span>
                  <span className="text-xs text-slate-400">Scheduled</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Documentation Queue</CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            <div className="space-y-3 text-sm text-slate-600">
              {encounterQueues.map((item) => (
                <div key={item.label} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <div className="font-medium text-slate-800">{item.label}</div>
                  <div className="text-xs text-slate-500">{item.note}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base text-slate-900">AI Scribe</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          {error ? <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div> : null}
          {statusLine ? <div className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm text-cyan-900">{statusLine}</div> : null}
          {insertResult ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              Note inserted: {insertResult.note_id} (Patient {insertResult.patient_id})
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2">
            <Input value={encounterId} onChange={(event) => setEncounterId(event.target.value)} placeholder="Encounter ID" />
            <Input value={primaryServiceId} onChange={(event) => setPrimaryServiceId(event.target.value)} placeholder="Primary Service ID (optional)" />
          </div>

          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <Input
              type="file"
              accept="audio/*"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
            <Button type="button" onClick={uploadAudio} disabled={!canUpload}>
              {isUploading ? "Uploading..." : "Upload Audio"}
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={transcribeAudio} disabled={!canTranscribe}>
              {isTranscribing ? "Transcribing..." : "Transcribe"}
            </Button>
            <Button type="button" variant="outline" onClick={() => generateDraft("SOAP")} disabled={!canGenerateDraft}>
              {isGeneratingDraft && draftType === "SOAP" ? "Generating..." : "Generate SOAP"}
            </Button>
            <Button type="button" variant="outline" onClick={() => generateDraft("DAP")} disabled={!canGenerateDraft}>
              {isGeneratingDraft && draftType === "DAP" ? "Generating..." : "Generate DAP"}
            </Button>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Transcript</label>
            <textarea
              className="min-h-[120px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700"
              value={transcript}
              readOnly
              placeholder="Transcript appears here after transcribe."
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Draft ({draftType || "N/A"})</label>
            <textarea
              className="min-h-[200px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700"
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              placeholder="Generated SOAP/DAP draft appears here for provider review."
            />
          </div>

          <div className="grid gap-3 md:grid-cols-[220px_auto_auto] md:items-center">
            <select
              className="h-9 rounded-md border border-slate-200 px-3 text-sm"
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as "clinical_only" | "legal_and_clinical")}
            >
              <option value="clinical_only">clinical_only</option>
              <option value="legal_and_clinical">legal_and_clinical</option>
            </select>
            <Button type="button" variant="outline" onClick={saveDraft} disabled={!canSaveDraft}>
              {isSavingDraft ? "Saving..." : "Save Draft"}
            </Button>
            <Button type="button" onClick={insertIntoChart} disabled={!canInsert}>
              {isInserting ? "Inserting..." : "Insert into Chart"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
