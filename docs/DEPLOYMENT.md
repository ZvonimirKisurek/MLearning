# Production deployment: Vercel + Render + Supabase + Upstash

Follow the checklist in order. Everything below was written against the repo as it is; the cloud dashboards change, so
where a menu name matters it is quoted, and prices are deliberately not quoted (check each pricing page).

## 1. Architecture

```
                  HTTPS + Basic auth                 HTTPS + Bearer API_TOKEN
 Browser  ─────────────────────────►  Vercel  ─────────────────────────────────►  Render: mle-sprint-api (FastAPI)
                                   (Next.js 16)                                        │            │
                                  Server Components,                                   │ SQL        │ enqueue (send_task)
                                  Server Actions,                                      ▼            ▼
                                  /api/feed proxy                                  Supabase      Upstash Redis (rediss://)
                                                                                  Postgres +          ▲        ▲
                                                                                  pgvector            │ pull   │ publish on schedule
                                                                       Render: mle-sprint-worker ─────┘        └── Render: mle-sprint-beat
                                                                       (executes tasks, calls OpenAI,                  (the clock; ONE instance)
                                                                        writes to Postgres)
```

* **The browser never talks to FastAPI.** Server Components, Server Actions and `/api/feed` run on Vercel and call Render
  server-to-server with the bearer token. So `API_TOKEN` never reaches a browser, and **CORS is not on the critical path**.
  `FRONTEND_URL` still feeds the CORS allow-list as a safety net (and for a future client-side fetch), but a wrong value
  will not break the app.
* **Basic auth** (`frontend/src/proxy.ts`) guards the whole Vercel site, including Server Actions that can spend LLM money.
  `API_TOKEN` guards Render. Two independent gates; both must be set.
* **Beat vs worker.** Beat only *publishes* a message ("run `generate_daily_briefing`") to Redis when a cron expression
  comes due; the worker *consumes* and executes it. They are separate processes and **beat must be a single instance**:
  two beats = every job enqueued twice (duplicate OpenAI spend). Never scale `mle-sprint-beat`, and never enable
  autoscaling on it.
* The schedule is interpreted in `TIMEZONE` (`06:30` daily, Sunday `22:00` weekly, ingestion every 6 h).

### Cloud quirks worth knowing before you click anything
1. **Upstash needs TLS and a certificate policy.** The URL must be `rediss://` (two s). Celery refuses a `rediss://` URL
   unless a `ssl_cert_reqs` policy is given; `app/celery_app.py` now sets `CERT_REQUIRED` automatically when the scheme is
   `rediss://`, so you paste the URL as-is.
2. **Idle Celery talks to Redis constantly, and Upstash can bill per command.** The Redis transport blocks on `BRPOP` in a
   loop; gossip, mingle, heartbeats and the remote-control channel add chatter. This repo already disables the avoidable
   parts (no result backend, `--without-gossip --without-mingle --without-heartbeat`, remote control off, events off).
   That *reduces* idle traffic; it does not make it zero. **After deploy, watch Upstash's command counter for a day**
   (step 6) and compare it with your plan's quota. If it is too high, the fixes are: an Upstash fixed-price plan, Render's
   own Key Value (Redis-compatible) instance, or dropping Celery for `TASK_BACKEND=inline` + the GitHub Actions cron
   described in `docs/DEPLOY.md` (zero always-on workers, zero Redis).
3. **Render workers are not free**, and a free web service sleeps when idle (cold start 30-60 s; the frontend's API
   timeout is 15 s, so the first page after a nap would show an error). This blueprint uses an always-on paid plan for
   all three services. A cheaper variant is to merge worker and beat into one service (`celery ... worker -B`), which is safe
   as long as that one service has exactly one instance; I kept them separate because you asked for that and it isolates
   failures. Check Render's pricing page for the total.
4. **Ephemeral disks.** Beat's schedule file is in `/tmp` and is lost on every deploy/restart. That is harmless: beat
   recomputes the next boundary on start. The only gap: a restart *across* 06:30 skips that day's tick (use Calendar or
   "Generate now" to backfill). Deploys of the beat service are therefore best done outside 06:20-06:40.
5. **Worker pool.** The worker runs `--pool=threads --concurrency=2`: lower RAM than prefork on a 512 MB instance, fine
   for I/O-bound jobs. (Locally on Python 3.14 the default prefork pool crashed every task; the Docker image uses
   Python 3.12 where it may be fine, but threads is the tested choice.) Thread pools cannot enforce hard task time limits.
6. **Region.** Put Render in the same region as Supabase (Frankfurt in the blueprint; change if yours differs). On Vercel set
   Settings > Functions > Function Region to the nearest one (e.g. `fra1`), otherwise every page pays a transatlantic
   hop to Render.
7. **Long Server Actions.** Hand-in grading takes 10-60 s. The practice page exports `maxDuration = 300` so Vercel does not
   kill the action. Your Vercel plan caps the maximum allowed duration; if deploy or runtime complains, lower it to your
   plan's limit (it must stay above the API's grading time).
8. **Time zone data.** The slim image has no OS tz database; `zoneinfo` gets it from the `tzdata` wheel that Celery's
   dependency `kombu` installs. Nothing to do, but it is why `TIMEZONE=Europe/Zagreb` works in the container.

## 2. Deployment checklist

### A. Accounts and secrets (5 min)
- [ ] Push this repo to GitHub (private). Merge the working branch to your default branch: Render and Vercel deploy from it.
- [ ] Generate the shared API secret and keep it in a password manager: `openssl rand -hex 32` (this is `API_TOKEN`).
- [ ] Choose `BASIC_AUTH_USER` and a long random `BASIC_AUTH_PASSWORD`.
- [ ] **Disable the GitHub Actions schedule** so jobs do not run twice: in the repo go to Actions > "Scheduled jobs" > "..." >
      *Disable workflow* (or delete `.github/workflows/scheduled.yml`). Beat replaces it.

### B. Supabase (database)
- [ ] Create a project; pick the region you chose for Render. Save the database password.
- [ ] Click **Connect** (top bar) > **Session pooler**. Copy the URI. It looks like
      `postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres`.
      Replace `[YOUR-PASSWORD]`, URL-encode special characters in the password (`@` → `%40`), and append `?sslmode=require`.
      This is `DATABASE_URL`. Why Session pooler: direct connections are IPv6-only; the pooler is IPv4. Session mode (5432)
      suits the long-lived connection pools in the API and workers. The code already disables prepared statements, so the
      transaction pooler (6543) also works, but there is no reason to prefer it here.
- [ ] Sanity-check from your Mac: `psql "$DATABASE_URL" -c "select version();"`
- [ ] Run the migrations. **They are not idempotent and migration 6 deletes briefings/themes, so run them exactly once on
      an empty database.** Either:
      ```bash
      # Option 1: plain psql (no extra tooling, easiest to reason about)
      export DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require'
      for f in supabase/migrations/*.sql; do echo "== $f"; psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f" || break; done
      ```
      ```bash
      # Option 2: Supabase CLI (records applied migrations, so re-running is safe)
      supabase login && supabase link --project-ref <project-ref> && supabase db push
      ```
      Migration 1 enables `pgvector` in the `extensions` schema; no dashboard toggle needed.
- [ ] Verify: `psql "$DATABASE_URL" -c "\dt public.*"` lists `articles`, `daily_briefings`, `daily_tasks`, `skills`, ... and
      `select count(*) from skills;` returns 7.
- [ ] This is a **fresh** database: skills start at 0 and old briefings are gone. To carry local progress over, `pg_dump
      --data-only -t skills -t skill_history` from the old database and load it after the migrations.
- [ ] Supabase's dashboard may flag tables with RLS enabled and no policies. That is intended: the app connects as the
      database owner via `DATABASE_URL` and never uses the public Supabase API; do not expose the `anon` key anywhere.

### C. Upstash (Redis)
- [ ] Create a Redis database in the region nearest Render. Enable TLS (default).
- [ ] Copy the **TLS** connection string (`rediss://default:<password>@<name>.upstash.io:6379`). This is `REDIS_URL`.
- [ ] Do not use the REST URL/token; Celery speaks the Redis protocol.
- [ ] Eviction: leave off. This Redis holds only the in-flight queue, so losing it loses nothing durable (jobs are
      idempotent and re-runnable).

### D. Render (API + worker + beat)
- [ ] Render dashboard > **New** > **Blueprint** > connect the GitHub repo > it finds `render.yaml` at the root.
- [ ] Review the three services and the `mle-sprint-shared` env group. Adjust `region`, `plan`, `TIMEZONE`, `USER_AGENT`.
- [ ] Fill the prompted secrets (`sync: false` values):
      | Variable | Where | Value |
      |---|---|---|
      | `DATABASE_URL` | shared group | Supabase session-pooler URI (step B) |
      | `REDIS_URL` | shared group | Upstash `rediss://` URL (step C) |
      | `OPENAI_API_KEY` | shared group | your key |
      | `ROADMAP_START` | shared group | the **Monday** you start, `YYYY-MM-DD`, or leave empty |
      | `API_TOKEN` | API service | the `openssl rand -hex 32` value |
      | `FRONTEND_URL` | API service | your Vercel URL; if unknown yet put `https://placeholder.invalid` and edit after step E |
- [ ] **Apply**. Render builds `backend/Dockerfile` three times (once per service, cached after the first).
- [ ] Verify the API: `curl https://mle-sprint-api.onrender.com/health` → `{"status":"ok"}` (no token needed; 503 means the
      database is unreachable: re-check `DATABASE_URL`).
- [ ] Verify auth is on: `curl -i https://mle-sprint-api.onrender.com/api/today` → `401`.
      With the token: `curl -H "Authorization: Bearer $API_TOKEN" https://mle-sprint-api.onrender.com/api/today` → JSON, `state: "pending"`.

### E. Vercel (frontend)
- [ ] **Add New > Project**, import the repo. Framework preset: Next.js (auto-detected).
- [ ] **Root Directory: `frontend`** (Settings > General > Root Directory). Leave build/output defaults.
- [ ] Settings > Environment Variables, scope **Production** (and Preview if you use it):
      | Variable | Value |
      |---|---|
      | `API_URL` | `https://mle-sprint-api.onrender.com` (https, no trailing slash) |
      | `API_TOKEN` | exactly the Render `API_TOKEN` |
      | `BASIC_AUTH_USER` | your chosen user |
      | `BASIC_AUTH_PASSWORD` | your long random password |
      These are server-side only (no `NEXT_PUBLIC_` prefix), so they are not exposed to browsers, and `lib/api.ts` is
      `server-only` so the build fails if a client component ever imports it.
- [ ] Settings > Functions > Function Region: the region nearest Render (e.g. Frankfurt `fra1`).
- [ ] **Deploy** (environment variables are read at runtime but a change needs a redeploy to take effect).
- [ ] Copy the production URL back into Render's `FRONTEND_URL` (API service) and redeploy that service (cosmetic, see §1).
- [ ] **Verify Basic auth is actually active** (it silently turns off if either variable is missing):
      ```bash
      curl -i https://<your-app>.vercel.app/                       # expect: HTTP 401 + WWW-Authenticate: Basic
      curl -i -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASSWORD" https://<your-app>.vercel.app/   # expect: HTTP 200
      ```
      Also check `/feed` and `/calendar` return 401 without credentials. Note that Vercel *Preview* deployment URLs are
      only gated if the variables are also set for the Preview scope.
- [ ] Open the site in a browser, enter the credentials: the Command Center should say the briefing is pending. If you
      see an "API problem" panel, `API_URL`/`API_TOKEN` is wrong (the panel says which).

### F. Verify Celery Beat and the worker
- [ ] Render > `mle-sprint-beat` > Logs. Expect:
      `beat: Starting...` then `Scheduler: Sending due task ...` only when a cron time hits. A healthy beat is *quiet*
      between ticks. The startup banner should show `timezone -> Europe/Zagreb` (your `TIMEZONE`) and the
      `redis://`/`rediss://` broker. There must be exactly **one** beat instance (Render > service > Scaling).
- [ ] Render > `mle-sprint-worker` > Logs. Expect `Connected to rediss://...`, `celery@... ready.`, and
      `concurrency: 2 (thread)` and the five tasks listed under `[tasks]`.
- [ ] If the worker prints SSL errors: confirm `REDIS_URL` starts with `rediss://`. If it prints
      `Connection refused`/timeouts: the Redis URL is wrong or the Upstash database is in another account/region.

### G. First run: trigger a daily generation manually
Run these from the Render **API** service's Shell (Dashboard > mle-sprint-api > Shell), or locally with `DATABASE_URL`
and `REDIS_URL` exported. Each step builds on the previous one:
```bash
python -m app.cli ingest                 # pull articles + embeddings (a minute or two)
python -m app.cli summarize --limit 120  # AI summaries for the feed
python -m app.cli generate-weekly        # this week's theme (needed by the daily briefing)
python -m app.cli generate-daily --force # chapter + hands-on lab + essay for today (~1-3 min, costs a few cents)
```
- [ ] Reload the Vercel site: the Command Center shows the three tasks; open the chapter; the Calendar shows today's dot.
- [ ] Test the queue path end to end (API → Upstash → worker): on the Command Center click **Generate now** when a briefing is
      pending, or: `curl -X POST -H "Authorization: Bearer $API_TOKEN" https://mle-sprint-api.onrender.com/api/briefing/generate`
      → `{"queued": true}`, and the worker log shows `Task app.tasks.generate_daily_briefing[...] received` then `succeeded`.
- [ ] Submit a lab for grading (takes 10-60 s) to confirm the long Server Action completes on Vercel.

### H. Prove the 06:30 cron works (don't trust it blindly)
- [ ] Next morning (after 06:30 `TIMEZONE`): beat log shows `Sending due task daily-briefing-morning`, the worker log shows
      the task succeeding, and the Calendar has a new dot. If you want proof sooner, temporarily set the
      `daily-briefing-morning` crontab to two minutes from now in `app/celery_app.py`, deploy, watch, then revert.
- [ ] Upstash dashboard: note the commands/day figure after a quiet day and compare with your plan's limit (§1, quirk 2).
- [ ] Set a Render notification (service > Settings > Notifications) for failed deploys, and glance at the worker log weekly.

## 3. Day-2 operations
| Task | How |
|---|---|
| Rotate `API_TOKEN` | Render API env: set `new,old` (comma-separated; both accepted) → set Vercel `API_TOKEN=new` and redeploy → remove `,old` from Render. No downtime. |
| Change schedule or `TIMEZONE` | Edit `app/celery_app.py` / env var, push. Restart **beat** (a deploy does this). |
| New migration | Add a file in `supabase/migrations/`, apply it with `supabase db push` (or `psql -f`) **before** deploying code that needs it. |
| Backfill a missed day | Not automatic. Use the Command Center "Generate now", or `python -m app.cli generate-daily --force` in the Render shell. |
| Spend control | `LLM_DAILY_BUDGET_USD` is enforced in code (rolling 24 h). Also set a monthly cap in the OpenAI dashboard. |
| Stop everything | Suspend `mle-sprint-beat` first (no new jobs), then the worker, then the API. |

## 4. Troubleshooting
| Symptom | Likely cause |
|---|---|
| Site asks for a password but rejects the right one | Vercel env was changed without redeploying; or special characters in the password mangled by `curl -u` quoting. |
| Site loads with no password prompt | `BASIC_AUTH_USER`/`PASSWORD` missing in that Vercel scope (gate is off when either is empty). |
| "Cannot reach the API" panel | `API_URL` wrong, or the Render service is asleep/crashed (check its logs and `/health`). |
| "The API rejected API_TOKEN" | Vercel and Render `API_TOKEN` differ (watch for trailing spaces/newlines). |
| `/health` returns 503 | `DATABASE_URL` wrong, password not URL-encoded, or missing `?sslmode=require`. |
| Worker: `ValueError: A rediss:// URL must have parameter ssl_cert_reqs` | You are on an old image without the `celery_app.py` TLS change; redeploy. |
| Jobs enqueue but never run | Worker down, or it and the API point at different Redis databases (check the shared env group). |
| Every job runs twice | Two beats are running, or the GitHub Actions schedule is still enabled (§2-A). |
| Briefing missing at 06:30 | Beat restarted across the tick, or `TIMEZONE` not set on the **beat** service (it must be in the shared group). |
