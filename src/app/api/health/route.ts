import { NextResponse } from "next/server";

import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return await proxyBackendResponse("/api/v1/health");
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unable to reach backend health endpoint.",
      },
      { status: 502 },
    );
  }
}
