import Link from "next/link";

export default function ClaimsPage() {
  return (
    <main className="min-h-screen bg-black text-white p-12">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/"
          className="text-sm text-zinc-400 hover:text-white underline"
        >
          Back to home
        </Link>

        <h1 className="text-3xl font-bold mt-6 mb-3">Claims</h1>
        <p className="text-zinc-400 mb-6">
          Track open, partial, denied, and paid claims alongside ledger status.
        </p>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <p className="text-zinc-300">
            Claims tracking and workflow actions will appear here.
          </p>
        </div>
      </div>
    </main>
  );
}
