# Cost and security sanity check

## Cost: estimate for one week (1 user)
Measured on this code with realistic article lengths: ~11,000 input tokens per weekly or daily generation (50 articles +
prompt + schema), ~180 per article for summaries. Prices (cached 2026-10-06; verify): Sonnet 5.5 $2 in / $10 out per MTok,
Haiku 5.5 $0.10 / $0.50, OpenAI text-embedding-3-small ~$0.02 per MTok (from memory). Thinking tokens bill as output and are the main unknown.

| Item | Volume / week | Assumption | Cost |
|---|---|---|---|
| Daily + weekly generation (Sonnet 5.5) | 8 calls | 11k in; ~1.5k JSON + 1.5-6k thinking out | $0.05-0.10 each => **$0.42-0.78** |
| Summaries (Haiku 5.5) | <= ~400/day | 10-article batches, ~2k in / ~1.5k out | <= $0.04/day => **<= $0.28** |
| Embeddings (OpenAI) | ~500 new items/day | ~120 tokens each | **~$0.01** |
| **Typical total** | | | **about $0.7-1.1 per week (~$3-5/month)** |
| Worst plausible (every generation needs 2 repairs) | | ~3x generation | ~$2-3 per week |

The first day adds ~$0.02 (first ingest embeds ~1,500 items; 120 summaries). After day 1 run `python -m app.cli usage` for real numbers;
if it is higher than expected, lower `LLM_EFFORT` to `low`.

## Spend limits (the app's request rate is tiny, so cap SPEND, not requests)
Peak load is one summary batch every few seconds for ~1 minute, a few times a day: tens of requests per hour. Provider-side:
1. **Anthropic Console:** create a separate workspace and key for this app. Set a monthly spend limit of ~$10, load a small prepaid balance
   (~$10-20) with auto-reload OFF (that balance is a hard ceiling), and turn on low-balance email alerts. If workspace rate limits are available, ~20-30 requests/min and ~50k input tokens/min is >2x the app's peak.
2. **OpenAI:** a dedicated project and key; a project monthly budget of ~$2; prepaid credits with auto-recharge OFF; if keys can be restricted by permission, allow only Embeddings.
Exact menu names change: look under Billing / Limits in each console.
3. **In the app (`LLM_DAILY_BUDGET_USD`, default $1.00):** every Claude call is logged to `llm_usage` and refused once the last 24h reach the cap, whatever
   triggered it (retry storm, stuck scheduler, double-running cron). It is an *estimate* from a price table (`curriculum/usage.py`), so keep the provider limits as the backstop.
   It does not track OpenAI embeddings (negligible). `python -m app.cli usage` shows where money went.
4. **Leaving the worker running:** every LLM path goes through the cap; retries are bounded (Celery max 3-4 with backoff, repair loop max 2); jobs are idempotent per day/week.
   Do not run Celery beat AND the GitHub cron: that doubles cost (never unbounded).

## Security before a public deployment
| Concern | State | You do |
|---|---|---|
| Strangers using the app / triggering LLM spend | Basic-auth gate in `frontend/src/proxy.ts`; API behind a bearer token | Set `BASIC_AUTH_*` to a long random password (20+ chars; Basic auth has no rate limit); HTTPS only |
| **Rotating `API_TOKEN` with no downtime** | API accepts comma-separated tokens | `openssl rand -hex 32`; API `API_TOKEN="NEW,OLD"`; set Vercel `API_TOKEN=NEW` and redeploy; then API `API_TOKEN=NEW`. Rotate every ~90 days or on suspicion |
| Public API docs | `ENABLE_DOCS=false` in the Docker image | Verify `/docs` returns 404 on the deployed API |
| Secrets in the repo | `.env*` git-ignored; `.env.example` holds no secrets | Use platform/GitHub secrets only; never `NEXT_PUBLIC_*` for a secret; separate keys per environment |
| Database access | RLS on every table, no policies (the anon key sees nothing); backend uses the DB role | Never put the Supabase anon/service key in the frontend; keep the DB password in secrets |
| **Backups** | Your progress (skills, history, briefings, tasks) is the only irreplaceable data; articles are re-fetchable | Weekly `export-progress` artifact (scheduled.yml; **repo must be private**). For a *restorable* copy also run `pg_dump "$DATABASE_URL" --data-only -t skills -t skill_history -t weekly_themes -t daily_briefings -t daily_tasks > progress.sql` (pg_dump must be >= the server's version). Check what your Supabase plan includes: do not assume free-tier backups |
| Prompt injection via scraped text | Escaped, closed-world ids, links from DB only, rendered as plain text | Nothing; knowing it exists is the point |
| SSRF in the scraper (a feed redirecting to an internal address) | Low risk: only curated YAML URLs; accepted | Prefer running ingestion on GitHub runners; do not give the API host cloud credentials |
| Dependencies | Dependabot weekly for pip, npm, Actions, Docker; CI on PRs | Review and merge the PRs |
