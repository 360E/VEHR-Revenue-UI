import { NextResponse } from "next/server";

import { proxyBackendResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    return await proxyBackendResponse("/api/v1/revenue/era-pdfs/upload", {
      method: "POST",
      body: await request.formData(),
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Unable to proxy ERA upload.",
      },
      { status: 502 },
    );
  }
}
