import SharePointBrowser from "@/app/components/sharepoint-browser";

export default function MicrosoftIntegrationPage() {
  return (
    <SharePointBrowser
      eyebrow="Integration Hub"
      title="Microsoft Graph"
      subtitle="Connected SharePoint browsing without iframe embedding."
    />
  );
}
