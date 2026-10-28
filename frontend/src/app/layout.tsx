import type { Metadata } from "next";
import { Suspense } from "react";
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";
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
    <html lang="en" className="dark h-full antialiased">
      <body className="min-h-full">
        <header className="sticky top-0 z-30 border-b border-white/[0.07] bg-[#07080c]/70 backdrop-blur-xl">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
            <div className="flex items-center gap-2 font-mono text-sm font-semibold tracking-tight">
              <span className="grid size-7 place-items-center rounded-lg bg-gradient-to-br from-emerald-400/30 to-sky-400/20 text-emerald-300 ring-1 ring-white/10">
                <Activity className="size-3.5" />
              </span>
              <span className="gradient-text">MLE-Sprint</span>
            </div>
            {/* usePathname() is request-time data on dynamic routes (/read/[taskId]) so it must stream behind Suspense */}
            <Suspense fallback={<div className="h-8 w-40" aria-hidden />}><NavLinks /></Suspense>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-10">{children}</main>
      </body>
    </html>
  );
}
