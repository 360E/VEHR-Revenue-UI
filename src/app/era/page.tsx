import Link from "next/link";

export default function EraIntakePage() {
  return (
    <main className="min-h-screen bg-black text-white p-12">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/"
          className="text-sm text-zinc-400 hover:text-white underline"
        >
          Back to home
        </Link>

        <h1 className="text-3xl font-bold mt-6 mb-3">ERA Intake</h1>
        <p className="text-zinc-400 mb-6">
          Upload and process remittance files with validation and ledger sync.
        </p>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <p className="text-zinc-300">
            ERA ingestion workflows will be available from this page.
          </p>
        </div>
      </div>
    </main>
  );
}
