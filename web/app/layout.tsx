import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { Suspense } from "react";
import { AskProvider } from "@/components/AskDrawer";
import { FooterFrame, HabitatSlot, MainFrame } from "@/components/RouteFrame";
import { SiteNav } from "@/components/SiteNav";
import "./globals.css";

// Type (unslop/AUDIT.md): one family, IBM Plex Sans, for interface and headlines; IBM Plex Mono as its partner for figures.
const text = IBM_Plex_Sans({ variable: "--font-text", subsets: ["latin"], weight: ["400", "500", "600"], display: "swap" });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"], display: "swap" });

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
