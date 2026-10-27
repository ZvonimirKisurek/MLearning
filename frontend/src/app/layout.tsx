import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Activity } from "lucide-react";
import { NavLinks } from "@/components/nav-links";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "MLE-Sprint", template: "%s · MLE-Sprint" },
  description: "Personal AI/ML learning and market-intelligence dashboard",
};

/**
 * Root layout = a React Server Component and the *static shell*: it reads no request data, so Next can
 * prerender it once and serve it instantly; the data-dependent parts below it stream in via <Suspense>.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} dark h-full antialiased`}>
      <body className="min-h-full">
        <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
            <div className="flex items-center gap-2 font-mono text-sm font-semibold tracking-tight">
              <span className="grid size-6 place-items-center rounded-md bg-primary/15 text-primary">
                <Activity className="size-3.5" />
              </span>
              MLE-Sprint
            </div>
            <NavLinks />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
