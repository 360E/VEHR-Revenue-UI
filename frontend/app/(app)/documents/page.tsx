import SharePointBrowser from "@/app/components/sharepoint-browser";
import { BRANDING } from "@/lib/branding";

export default function DocumentsPage() {
  return (
    <SharePointBrowser
      eyebrow={BRANDING.name}
      title="Documents"
      subtitle="Internal clinic resources & policies."
    />
  );
}
