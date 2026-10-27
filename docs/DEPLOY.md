# Deployment

## Recommended stack (cheapest that is still robust)
| Piece | Service | Why |
|---|---|---|
| Frontend (Next 16) | **Vercel** (Hobby) | Built for Next; Server Components/Actions work out of the box; Git push deploys |
| Database | **Supabase** (free project) | You know it; pgvector included; this app only needs Postgres |
| API (FastAPI) | **One container on Fly.io, Render or Railway** | Any host that runs `backend/Dockerfile`; prefer one that auto-stops when idle and wakes fast |
| Recurring jobs | **GitHub Actions cron** (`.github/workflows/scheduled.yml`) | Free, no always-on worker, no Redis. This app has ~6 jobs/day: that is cron, not a queue |
| "Generate now" button | `TASK_BACKEND=inline` | Runs the job in a thread of the API process; no Redis |

**Why not Celery + Upstash Redis?** Celery's Redis transport polls continuously. On a Redis billed per command,
an idle worker plus beat can burn a free quota quickly (measure before relying on it). The Celery path is still
supported and tested: use `docker-compose.prod.yml` on one small VPS (own Redis container, no cold starts) if you prefer it.
Prices and free-tier limits change: check each provider's current pricing page before committing.

Capacity note: ~12 KB per canonical article (vector + index). A few hundred articles/day fills a 500 MB free database
in a couple of months, hence the weekly `prune` (`RETENTION_DAYS`, default 60).

## Step by step
1. **Supabase**: create a project. In *Connect* copy the **Session pooler** connection string (port 5432, user
   `postgres.<ref>`). It is IPv4-compatible, which GitHub runners need. Set `DATABASE_URL` to it.
2. **Migrations** (once; they are not idempotent):
   ```bash
   for f in supabase/migrations/*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"; done
   ```
3. **API container** (example: Fly.io; verify flags against `fly launch --help`):
   ```bash
   cd backend && fly launch --no-deploy --dockerfile Dockerfile --name mle-sprint-api
   fly secrets set DATABASE_URL=... OPENAI_API_KEY=... API_TOKEN=... TASK_BACKEND=inline TIMEZONE=Europe/Zagreb ROADMAP_START=2026-11-02
   fly deploy
   curl https://mle-sprint-api.fly.dev/health
   ```
   The image listens on `$PORT` (default 8000) and exposes `/health` for the platform health check. Set the health path
   to `/health`, and let the service auto-stop when idle if the platform supports it.
4. **GitHub**: repo *Settings > Secrets and variables > Actions*. Secrets: `DATABASE_URL`, `OPENAI_API_KEY`. Variables: `TIMEZONE`, `USER_AGENT`, `ROADMAP_START`, `MATCH_STRONG`, `MATCH_MODERATE`.
   Merge to the default branch (scheduled workflows only run there), then *Actions > Scheduled jobs > Run workflow*
   with `ingest`, then `summarize --limit 120`, `generate-weekly`, `generate-daily`.
5. **Vercel**: import the repo, set **Root Directory = `frontend`**. Environment variables: `API_URL=https://<your api host>`,
   `API_TOKEN` (same as the API), `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD` (the app has no accounts: this gate is what
   stops strangers from triggering LLM spend). Deploy.
6. **Verify**: open the Vercel URL (browser asks for the password), check `/` and `/feed`.

## Operating notes
- Do not run Celery beat AND the GitHub schedule: every job would run twice.
- GitHub pauses scheduled workflows after 60 days with no repository activity, and cron can start minutes late.
- Cron is UTC. `30 5 * * *` is 06:30 in winter Central Europe and 07:30 in summer: adjust to your morning.
- Rotate `API_TOKEN` by changing it on the API host and in Vercel together.
- Secrets live only in the platform/GitHub secret stores, never in the repo (`.env*` is git-ignored).
