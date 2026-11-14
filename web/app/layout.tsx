import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Suspense } from "react";
import { AskProvider } from "@/components/AskDrawer";
import { HabitatBar } from "@/components/HabitatBar";
import { SiteNav } from "@/components/SiteNav";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Gravity Gap",
  description:
    "Partial-gravity fire prediction engine: bridging microgravity and Earth fire-safety data for Moon and Mars habitats.",
};

// Apply the saved theme before paint to avoid a flash of the wrong theme.
const themeScript = `try{var t=localStorage.getItem("gg-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={`${inter.variable} ${mono.variable} antialiased min-h-screen`}>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <AskProvider>
        <header className="border-b border-line bg-surface">
          <Suspense fallback={<div className="h-24" aria-hidden="true" />}>
            <SiteNav />
            <HabitatBar />
          </Suspense>
        </header>
        <main id="main" className="mx-auto max-w-6xl px-4 py-6">
          <Suspense fallback={<p className="text-muted">Loading…</p>}>{children}</Suspense>
        </main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 pt-4 text-xs text-muted">
          Gravity Gap · NASA Space Apps 2026 · All outputs are scaling-law estimates, not measurements.
        </footer>
        </AskProvider>
      </body>
    </html>
  );
}
