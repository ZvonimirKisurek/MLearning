"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Command Center" },
  { href: "/feed", label: "Intelligence Feed" },
  { href: "/calendar", label: "Calendar" },
];

// Client Component only because it needs usePathname() for the active state; everything else in the layout stays on the server.
export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-1 text-sm">
      {LINKS.map((l) => {
        // A past day (/day/2026-10-28) is part of the Calendar section, so the Calendar tab stays lit there.
        const active = l.href === "/" ? pathname === "/" : l.href === "/calendar" ? pathname.startsWith("/calendar") || pathname.startsWith("/day/") : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            aria-current={active ? "page" : undefined}
            className={cn("rounded-md px-3 py-1.5 transition-colors", active ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground")}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
