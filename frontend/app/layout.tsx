import type { Metadata } from "next";
import "./tokens.css";
import "./globals.css";
import { BRANDING } from "@/lib/branding";

export const metadata: Metadata = {
  title: {
    default: BRANDING.fullName,
    template: `%s | ${BRANDING.name}`,
  },
  description: `${BRANDING.name} \u2014 ${BRANDING.tagline}.`,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-background text-foreground antialiased">{children}</body>
    </html>
  );
}
