import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Shared-password gate (HTTP Basic auth) for the whole app, including Server Actions and /api/feed.
 *
 * Why it exists: this app has no user accounts, but its Server Actions can mark tasks complete and trigger LLM
 * generation (which costs money). On the public internet that must not be open. Set BASIC_AUTH_USER and
 * BASIC_AUTH_PASSWORD in the host's environment; when they are unset (local dev) the gate is off.
 * Browsers cache the credentials per origin and re-send them on every request, so fetches and Server Actions
 * from the page keep working without extra code. Always serve over HTTPS (Vercel does): Basic auth is
 * base64, not encryption.
 */
const USER = process.env.BASIC_AUTH_USER;
const PASS = process.env.BASIC_AUTH_PASSWORD;

function safeEqual(a: string, b: string): boolean {
  // Constant-time-ish comparison: no early exit on the first differing character.
  let diff = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return diff === 0;
}

export function proxy(request: NextRequest) {
  if (!USER || !PASS) return NextResponse.next();
  const header = request.headers.get("authorization") ?? "";
  const [scheme, encoded] = header.split(" ");
  if (scheme === "Basic" && encoded) {
    try {
      const decoded = atob(encoded);
      const i = decoded.indexOf(":");
      if (i > -1 && safeEqual(decoded.slice(0, i), USER) && safeEqual(decoded.slice(i + 1), PASS)) return NextResponse.next();
    } catch {
      /* malformed header: fall through to 401 */
    }
  }
  return new NextResponse("Authentication required", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="MLE-Sprint", charset="UTF-8"' } });
}

export const config = {
  // Everything except Next's static assets (which contain no data).
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
