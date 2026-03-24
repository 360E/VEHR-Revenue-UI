"use client";

import { BuilderComponent, builder, useIsPreviewing } from "@builder.io/react";

import { getBuilderPublicApiKey, type BuilderPageContent } from "@/lib/builder";

type BuilderPageRendererProps = {
  content: BuilderPageContent | null;
};

let initializedApiKey: string | null = null;

function initializeBuilder(): string | null {
  const apiKey = getBuilderPublicApiKey();

  if (!apiKey) {
    return null;
  }

  if (initializedApiKey !== apiKey) {
    builder.init(apiKey);
    initializedApiKey = apiKey;
  }

  return apiKey;
}

export function BuilderPageRenderer({ content }: BuilderPageRendererProps) {
  initializeBuilder();

  const isPreviewing = useIsPreviewing();

  if (!content && !isPreviewing) {
    return null;
  }

  return <BuilderComponent model="page" content={content ?? undefined} />;
}
