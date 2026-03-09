import { NextResponse } from "next/server";

import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return await proxyBackendResponse("/api/v1/claims");
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unable to proxy claims request.",
      },
      { status: 502 },
    );
  }
}
