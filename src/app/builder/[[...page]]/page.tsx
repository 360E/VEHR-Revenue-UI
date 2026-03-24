import Link from "next/link";

import { BuilderPageRenderer } from "@/components/builder-page-renderer";
import { PageShell, SectionCard } from "@/components/page-shell";
import { getBuilderPageContent, getBuilderPublicApiKey } from "@/lib/builder";

export const revalidate = 5;

type BuilderRoutePageProps = {
  params: Promise<{
    page?: string[];
  }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function toUrlPath(page: string[] | undefined): string {
  return page && page.length > 0 ? `/${page.join("/")}` : "/";
}

function isBuilderPreviewRequest(searchParams: Record<string, string | string[] | undefined>): boolean {
  return ["builder.preview", "builder.space", "builder.cachebust", "__builder_editing__"].some(
    (key) => key in searchParams,
  );
}

function BuilderSetupState({ urlPath }: { urlPath: string }) {
  return (
    <PageShell
      title="Builder.io is ready to connect"
      description="Revenue-UI now has a dedicated Builder-powered route. Add your public API key, then point Builder preview to this local route."
      footer="Builder route base: /builder"
    >
      <SectionCard title="Required local environment">
        <div className="space-y-4 text-sm text-zinc-300">
          <p>Add the following to .env.local:</p>
          <pre className="overflow-x-auto rounded-lg border border-zinc-800 bg-black/40 p-4 text-xs text-zinc-200">
NEXT_PUBLIC_API_URL=https://api-staging.360-encompass.com{"\n"}
NEXT_PUBLIC_BUILDER_API_KEY=your_builder_public_api_key
          </pre>
          <p>
            Use <strong>http://localhost:3000/builder</strong> as the Builder Page model preview URL. A page with URL
            <strong> {urlPath}</strong> in Builder will render at <strong>http://localhost:3000/builder{urlPath === "/" ? "" : urlPath}</strong>.
          </p>
        </div>
      </SectionCard>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/"
          className="inline-flex rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
        >
          Back to home
        </Link>
      </div>
    </PageShell>
  );
}

function BuilderEmptyState({ urlPath }: { urlPath: string }) {
  return (
    <PageShell
      title="No Builder page found yet"
      description="The Builder integration is active, but there is no published page for this URL path yet."
      footer="Publish a page in Builder, or open the route from the Builder visual editor."
    >
      <SectionCard title="Current lookup">
        <div className="space-y-4 text-sm text-zinc-300">
          <p>Requested Builder page path: <strong>{urlPath}</strong></p>
          <p>Create or publish a Builder Page entry with that URL, then refresh this route.</p>
        </div>
      </SectionCard>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/builder"
          className="inline-flex rounded-md border border-white px-4 py-2 font-medium text-white transition hover:bg-white hover:text-black"
        >
          Open Builder root
        </Link>
        <Link
          href="/"
          className="inline-flex rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
        >
          Back to home
        </Link>
      </div>
    </PageShell>
  );
}

export default async function BuilderRoutePage({ params, searchParams }: BuilderRoutePageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const urlPath = toUrlPath(resolvedParams.page);

  if (!getBuilderPublicApiKey()) {
    return <BuilderSetupState urlPath={urlPath} />;
  }

  const content = await getBuilderPageContent(urlPath, isBuilderPreviewRequest(resolvedSearchParams));

  if (!content) {
    return <BuilderEmptyState urlPath={urlPath} />;
  }

  return <BuilderPageRenderer content={content} />;
}