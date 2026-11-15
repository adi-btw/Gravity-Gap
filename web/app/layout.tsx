import type { Metadata } from "next";
import localFont from "next/font/local";
import { Suspense } from "react";
import { AskProvider } from "@/components/AskDrawer";
import { FooterFrame, HabitatSlot, MainFrame } from "@/components/RouteFrame";
import { SiteNav } from "@/components/SiteNav";
import "./globals.css";

// Type (unslop/AUDIT.md): one family, IBM Plex Sans, for interface and headlines; IBM Plex Mono as its partner for figures.
// Bundled (app/fonts/, latin subset from @fontsource 5.3.0, SIL OFL 1.1) instead of next/font/google, so builds never
// depend on downloading from Google Fonts (that download failed intermittently in CI).
const text = localFont({
  variable: "--font-text",
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
  src: [
    { path: "./fonts/ibm-plex-sans-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "./fonts/ibm-plex-sans-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/ibm-plex-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
});
const mono = localFont({
  variable: "--font-mono",
  display: "swap",
  fallback: ["ui-monospace", "monospace"],
  src: [
    { path: "./fonts/ibm-plex-mono-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "./fonts/ibm-plex-mono-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/ibm-plex-mono-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
});

export const metadata: Metadata = {
  title: "Gravity Gap",
  description:
    "Partial-gravity fire prediction engine: bridging microgravity and Earth fire-safety data for Moon and Mars habitats.",
};

// Apply the saved theme before paint to avoid a flash of the wrong theme. Paper ("light") is the default.
const themeScript = `try{var t=localStorage.getItem("gg-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={`${text.variable} ${mono.variable} antialiased min-h-screen`}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:border focus:border-line focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <AskProvider>
        <header className="border-b border-line bg-bg print:hidden">
          <Suspense fallback={<div className="h-24" aria-hidden="true" />}>
            <SiteNav />
            <HabitatSlot />
          </Suspense>
        </header>
        <MainFrame>
          <Suspense fallback={<p className="text-muted">Loading…</p>}>{children}</Suspense>
        </MainFrame>
        <FooterFrame>
          <span>Gravity Gap · NASA Space Apps 2026</span>
          <span>All outputs are scaling-law estimates, not measurements.</span>
        </FooterFrame>
        </AskProvider>
      </body>
    </html>
  );
}
