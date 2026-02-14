import { ExternalLink, Link2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AppLayoutPageConfig } from "@/lib/app-layout-config";

const SHAREPOINT_PORTAL_URL = "https://www.office.com/launch/sharepoint";

export default function SharePointPage() {
  return (
    <div className="flex flex-col gap-6">
      <AppLayoutPageConfig
        moduleLabel="SharePoint"
        pageTitle="Organization Information"
        subtitle="Open the organization SharePoint portal."
      />

      <Card className="max-w-3xl">
        <CardHeader className="border-b border-[color-mix(in_srgb,var(--neutral-border)_70%,white)]">
          <CardTitle className="flex items-center gap-2 text-base">
            <Link2 className="h-4 w-4 text-[var(--status-informational)]" aria-hidden="true" />
            SharePoint Portal
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="ui-type-body text-[var(--neutral-muted)]">
            Launch SharePoint in a new tab.
          </p>
          <Button asChild>
            <a href={SHAREPOINT_PORTAL_URL} target="_blank" rel="noopener noreferrer">
              Open SharePoint
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
