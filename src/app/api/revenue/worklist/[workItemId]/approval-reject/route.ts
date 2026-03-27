import { NextResponse } from "next/server";

import { proxyBackendResponse } from "@/lib/backend";
import { isFetchFailedMessage } from "@/lib/error-messages";
import { getAccessToken, withAccessToken } from "@/lib/auth";

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    workItemId: string;
  }>;
};

export async function POST(_: Request, context: RouteContext) {
  const { workItemId } = await context.params;

  try {
    return await proxyBackendResponse(`/api/v1/revenue/worklist/${workItemId}/approval-reject`, {
      method: "POST",
      headers: withAccessToken(
        {
          "content-type": "application/json",
        },
        await getAccessToken(),
      ),
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error && !isFetchFailedMessage(error.message)
            ? error.message
            : "Unable to reach the VEHR revenue approval rejection endpoint.",
      },
      { status: 502 },
    );
  }
}
