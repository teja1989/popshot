import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import type { ReactNode } from "react";

import { THEME_INIT_SCRIPT } from "@/lib/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: "Popshot",
  description: "Pickleball stats for the people you actually play with.",
  applicationName: "Popshot",
  appleWebApp: { capable: true, title: "Popshot", statusBarStyle: "default" },
  icons: { icon: "/icons/192", apple: "/icons/192" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f3f6f5" },
    { media: "(prefers-color-scheme: dark)", color: "#0a1520" },
  ],
  width: "device-width",
  initialScale: 1,
  // When the on-screen keyboard opens, shrink the page (and dvh) instead of covering it, so
  // full-height sheets keep their fields and buttons above the keyboard (Android Chrome).
  interactiveWidget: "resizes-content",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // The proxy puts this request's CSP nonce here; the theme script must carry it.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    // data-theme is set before hydration by the script below.
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* The one raw-HTML exception: a fixed string defined in lib/theme.ts with nothing
            user-controlled in it, allowed by this request's nonce. */}
        {/* eslint-disable-next-line no-restricted-syntax */}
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
