export type BuilderPageContent = {
  data?: {
    title?: string;
    description?: string;
  };
} & Record<string, unknown>;

type BuilderContentApiResponse = {
  results?: BuilderPageContent[];
};

const BUILDER_CONTENT_API_ORIGIN = "https://cdn.builder.io";

export function getBuilderPublicApiKey(): string | null {
  const value = process.env.NEXT_PUBLIC_BUILDER_API_KEY?.trim();

  return value ? value : null;
}

function getBuilderPageContentUrl(apiKey: string, urlPath: string, includeUnpublished: boolean): string {
  const url = new URL(`${BUILDER_CONTENT_API_ORIGIN}/api/v3/content/page`);

  url.searchParams.set("apiKey", apiKey);
  url.searchParams.set("limit", "1");
  url.searchParams.set("includeRefs", "true");
  url.searchParams.set("userAttributes.urlPath", urlPath);

  if (includeUnpublished) {
    url.searchParams.set("includeUnpublished", "true");
    url.searchParams.set("cachebust", "true");
  }

  return url.toString();
}

export async function getBuilderPageContent(
  urlPath: string,
  includeUnpublished = false,
): Promise<BuilderPageContent | null> {
  const apiKey = getBuilderPublicApiKey();

  if (!apiKey) {
    return null;
  }

  const response = await fetch(getBuilderPageContentUrl(apiKey, urlPath, includeUnpublished), {
    cache: includeUnpublished ? "no-store" : "force-cache",
    next: includeUnpublished ? undefined : { revalidate: 5 },
  });

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as BuilderContentApiResponse;

  return data.results?.[0] ?? null;
}
