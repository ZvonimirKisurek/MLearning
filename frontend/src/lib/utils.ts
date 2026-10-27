import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Deterministic (UTC) so server and client render identical text - no hydration mismatch. */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(new Date(iso));
}

/** ISO weekday (1=Mon..7=Sun) of a YYYY-MM-DD string; pure function of its input (no "now"). */
export function isoWeekday(dateStr: string): number {
  const d = new Date(`${dateStr}T12:00:00Z`).getUTCDay();
  return d === 0 ? 7 : d;
}

export function longDate(dateStr: string): string {
  return new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" }).format(
    new Date(`${dateStr}T12:00:00Z`),
  );
}
