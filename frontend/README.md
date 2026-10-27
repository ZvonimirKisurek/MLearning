# MLE-Sprint frontend

Next.js 16 (App Router, Cache Components) · React 19 · Tailwind v4 · shadcn/ui-style components · Recharts.
See the repo-root README for the full architecture.

```bash
cp .env.example .env.local     # API_URL, API_TOKEN (server-side only)
npm install
npm run dev                    # http://localhost:3000 (needs the API on :8000, see below)
npm run build && npm start     # production
npx tsc --noEmit && npm run lint
```

No API keys / Docker? Run the real backend on throwaway seeded demo data:
`cd ../backend && python scripts/demo_server.py` (add `--no-briefing` to see the "not generated yet" state).
