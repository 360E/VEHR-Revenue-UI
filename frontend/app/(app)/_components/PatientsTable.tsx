"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiFetch } from "@/lib/api";

type Patient = {
  id: string;
  first_name: string;
  last_name: string;
  dob?: string | null;
  created_at?: string;
};

type PatientsTableProps = {
  initialPatients: Patient[];
  initialError?: string | null;
};

export default function PatientsTable({
  initialPatients,
  initialError = null,
}: PatientsTableProps) {
  const [patients, setPatients] = useState<Patient[]>(initialPatients);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(initialError);
  const [isOpen, setIsOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    dob: "",
  });

  function closeDialog() {
    setIsOpen(false);
    setFormError(null);
    setForm({ first_name: "", last_name: "", dob: "" });
  }

  async function loadPatients() {
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiFetch<Patient[]>("/api/v1/patients", {
        cache: "no-store",
      });
      setPatients(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patients");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const first_name = form.first_name.trim();
    const last_name = form.last_name.trim();
    const dob = form.dob.trim();

    if (!first_name || !last_name || !dob) {
      return;
    }

    try {
      setIsSubmitting(true);
      setFormError(null);
      await apiFetch<Patient>("/api/v1/patients", {
        method: "POST",
        body: JSON.stringify({ first_name, last_name, dob }),
      });
      closeDialog();
      await loadPatients();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create patient");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
            Directory
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
            Patients
          </h1>
          <p className="text-sm text-slate-500">
            Intake-ready directory synced with the API.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => setIsOpen(true)}
          className="h-10 rounded-full px-5 text-sm"
        >
          New Patient
        </Button>
      </div>

      {error ? (
        <div
          className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          <span className="mt-1 h-2 w-2 rounded-full bg-destructive" />
          <span>{error}</span>
        </div>
      ) : null}

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/80">
          <div className="space-y-1">
            <CardTitle className="text-base font-semibold text-slate-900">
              Patient Directory
            </CardTitle>
            <p className="text-xs text-slate-500">
              Primary roster of active patient records.
            </p>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {isLoading ? (
            <div className="space-y-3 py-6">
              <div className="h-3 w-48 animate-pulse rounded bg-slate-200" />
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={`row-${index}`}
                    className="h-10 w-full animate-pulse rounded bg-slate-100"
                  />
                ))}
              </div>
            </div>
          ) : patients.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 px-6 py-10 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-900/5 text-slate-400">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                >
                  <circle cx="12" cy="7" r="4" />
                  <path d="M5 20a7 7 0 0 1 14 0" />
                </svg>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-slate-800">
                  No patients yet
                </p>
                <p className="text-xs text-slate-500">
                  Create a patient to start a new chart.
                </p>
              </div>
            </div>
          ) : (
            <Table className="text-[13px]">
              <TableHeader className="bg-slate-50/80">
                <TableRow className="border-slate-200/70">
                  <TableHead className="h-9 px-4 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    Patient
                  </TableHead>
                  <TableHead className="h-9 px-4 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    Date of Birth
                  </TableHead>
                  <TableHead className="h-9 px-4 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    Patient ID
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {patients.map((patient) => (
                  <TableRow
                    key={patient.id}
                    className="border-slate-200/70 hover:bg-slate-50/80"
                  >
                    <TableCell className="px-4 py-2.5 font-medium text-slate-900">
                      {patient.last_name}, {patient.first_name}
                    </TableCell>
                    <TableCell className="px-4 py-2.5 text-slate-600">
                      {patient.dob || "\u2014"}
                    </TableCell>
                    <TableCell className="px-4 py-2.5 font-mono text-[11px] text-slate-500">
                      {patient.id}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {isOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-3xl border border-slate-200/70 bg-white p-6 shadow-[0_30px_80px_rgba(15,23,42,0.2)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  New Patient
                </h2>
                <p className="text-sm text-slate-500">
                  Add a basic demographic stub.
                </p>
              </div>
              <Button type="button" variant="ghost" onClick={closeDialog}>
                Close
              </Button>
            </div>

            <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
              {formError ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              ) : null}
              <div className="grid gap-2">
                <label
                  className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500"
                  htmlFor="first_name"
                >
                  First name
                </label>
                <Input
                  id="first_name"
                  name="first_name"
                  value={form.first_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      first_name: event.target.value,
                    }))
                  }
                  placeholder="Casey"
                  required
                />
              </div>

              <div className="grid gap-2">
                <label
                  className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500"
                  htmlFor="last_name"
                >
                  Last name
                </label>
                <Input
                  id="last_name"
                  name="last_name"
                  value={form.last_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      last_name: event.target.value,
                    }))
                  }
                  placeholder="Morgan"
                  required
                />
              </div>

              <div className="grid gap-2">
                <label
                  className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500"
                  htmlFor="dob"
                >
                  Date of birth
                </label>
                <Input
                  id="dob"
                  name="dob"
                  type="date"
                  value={form.dob}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      dob: event.target.value,
                    }))
                  }
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={closeDialog}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Creating..." : "Create patient"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
