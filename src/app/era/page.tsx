import Link from "next/link";

import { PageShell, SectionCard } from "@/components/page-shell";

import { EraUploadForm } from "./era-upload-form";

export const dynamic = "force-dynamic";

export default function EraPage() {
  return (
    <PageShell
      title="ERA Upload"
      description="Upload ERA PDFs through the UI's same-origin proxy route."
      footer="ERA uploads post to /api/era via the UI origin."
    >
      <SectionCard title="Upload ERA PDF">
        <div className="space-y-6 text-sm text-zinc-300">
          <EraUploadForm />

          <Link
            href="/"
            className="inline-flex rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
          >
            Back to home
          </Link>
        </div>
      </SectionCard>
    </PageShell>
  );
}
