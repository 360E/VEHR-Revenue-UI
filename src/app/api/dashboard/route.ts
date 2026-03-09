import { NextResponse } from "next/server";

import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return await proxyBackendResponse("/api/v1/revenue/snapshots/latest");
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unable to proxy dashboard request.",
      },
      { status: 502 },
    );
  }
}
