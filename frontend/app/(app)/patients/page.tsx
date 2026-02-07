import PatientsTable from "../_components/PatientsTable";
import { apiFetch } from "@/lib/api";

type Patient = {
  id: string;
  first_name: string;
  last_name: string;
  dob?: string | null;
  created_at?: string;
};

export default async function PatientsPage() {
  let patients: Patient[] = [];
  let error: string | null = null;

  try {
    patients = await apiFetch<Patient[]>("/api/v1/patients", {
      cache: "no-store",
    });
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load patients";
  }

  return <PatientsTable initialPatients={patients} initialError={error} />;
}
